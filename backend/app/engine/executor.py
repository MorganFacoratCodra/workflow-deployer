import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from time import perf_counter
from typing import Any

from app.database import db_session
from app.engine.nodes import NodeExecutionError, execute_node
from app.models import Execution, NodeRun, Workflow
from app.ws import socket_manager

TERMINAL_STATES = {"success", "failed", "skipped"}
logger = logging.getLogger(__name__)


class GraphValidationError(ValueError):
    pass


def validate_graph(graph: dict[str, Any]) -> None:
    if not isinstance(graph, dict):
        raise GraphValidationError("Le graphe doit être un objet JSON valide.")

    nodes = graph.get("nodes")
    edges = graph.get("edges")

    if not isinstance(nodes, list) or not nodes:
        raise GraphValidationError("Le graphe doit contenir une liste non vide de nœuds.")
    if not isinstance(edges, list):
        raise GraphValidationError("Le graphe doit contenir une liste d'arêtes.")

    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise GraphValidationError(f"Nœud invalide à l'index {index}.")
        node_id = node.get("id")
        node_type = node.get("type")
        if not isinstance(node_id, str) or not node_id.strip():
            raise GraphValidationError(f"Le nœud à l'index {index} n'a pas d'id valide.")
        if node_id in node_ids:
            raise GraphValidationError(f"Le nœud '{node_id}' est dupliqué.")
        if not isinstance(node_type, str) or not node_type.strip():
            raise GraphValidationError(f"Le nœud '{node_id}' n'a pas de type valide.")
        node_ids.add(node_id)

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise GraphValidationError(f"Arête invalide à l'index {index}.")
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids or target not in node_ids:
            raise GraphValidationError(
                f"L'arête à l'index {index} référence un nœud inexistant (source='{source}', target='{target}')."
            )

    topological_sort(nodes, edges)


def topological_sort(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    node_ids: list[str] = []
    for index, node in enumerate(nodes):
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise GraphValidationError(f"Le nœud à l'index {index} n'a pas d'id valide.")
        node_ids.append(node_id)
    in_degree = {node_id: 0 for node_id in node_ids}
    graph = defaultdict(list)

    for index, edge in enumerate(edges):
        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise GraphValidationError(f"L'arête à l'index {index} est invalide.")
        if source not in in_degree or target not in in_degree:
            raise GraphValidationError(
                f"L'arête à l'index {index} référence un nœud inexistant (source='{source}', target='{target}')."
            )
        graph[source].append(target)
        in_degree[target] += 1

    queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
    ordered: list[str] = []

    while queue:
        current = queue.popleft()
        ordered.append(current)
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(node_ids):
        raise GraphValidationError("Le graphe du workflow contient un cycle.")
    return ordered


def _edge_allows(edge: dict[str, Any], source_status: str, source_output: dict[str, Any], source_type: str) -> bool:
    condition = edge.get("on")
    if source_type == "condition" and source_status == "success":
        route = source_output.get("route", "success")
        if condition in {"success", "failure"}:
            return condition == route
        return route == "success"

    if source_status == "success":
        return condition in (None, "", "success")
    if source_status == "failed":
        return condition == "failure"
    return False


def _should_execute(
    node_id: str,
    incoming_edges: dict[str, list[dict[str, Any]]],
    statuses: dict[str, str],
    outputs: dict[str, dict[str, Any]],
    node_types: dict[str, str],
) -> bool:
    edges = incoming_edges.get(node_id, [])
    if not edges:
        return True
    for edge in edges:
        source = edge.get("source")
        if not isinstance(source, str):
            continue
        if _edge_allows(edge, statuses.get(source, "pending"), outputs.get(source, {}), node_types.get(source, "")):
            return True
    return False


async def execute_graph_in_memory(graph: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    validate_graph(graph)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_map = {node["id"]: node for node in nodes}
    node_types = {node["id"]: node.get("type", "") for node in nodes}
    incoming_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        incoming_edges[edge["target"]].append(edge)

    order = topological_sort(nodes, edges)
    statuses = {node_id: "pending" for node_id in node_map}
    outputs: dict[str, dict[str, Any]] = {}
    context: dict[str, Any] = {}

    for node_id in order:
        node = node_map[node_id]
        if not _should_execute(node_id, incoming_edges, statuses, outputs, node_types):
            statuses[node_id] = "skipped"
            continue
        try:
            statuses[node_id] = "running"
            output, _ = await execute_node(node["type"], node.get("data", {}), context)
            statuses[node_id] = "success"
            outputs[node_id] = output
            context[node_id] = output
        except Exception:
            statuses[node_id] = "failed"

    for node_id, status in statuses.items():
        if status == "pending":
            statuses[node_id] = "skipped"

    return statuses, outputs


async def _publish(execution_id: int, payload: dict[str, Any]) -> None:
    try:
        await socket_manager.broadcast(execution_id, payload)
    except Exception:
        logger.exception("Erreur WebSocket lors du broadcast (execution_id=%s).", execution_id)


async def _mark_execution_failed(execution_id: int, message: str) -> None:
    with db_session() as db:
        execution = db.get(Execution, execution_id)
        if execution is not None:
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
    await _publish(
        execution_id,
        {"type": "execution", "execution_id": execution_id, "status": "failed", "logs": message},
    )


async def run_execution(execution_id: int) -> None:
    try:
        with db_session() as db:
            execution = db.get(Execution, execution_id)
            if execution is None:
                return
            workflow = db.get(Workflow, execution.workflow_id)
            if workflow is None:
                execution.status = "failed"
                execution.finished_at = datetime.utcnow()
                return

            graph = workflow.graph
            validate_graph(graph)
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])
            node_map = {node["id"]: node for node in nodes}
            node_types = {node["id"]: node.get("type", "") for node in nodes}
            incoming_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for edge in edges:
                incoming_edges[edge["target"]].append(edge)

            order = topological_sort(nodes, edges)

            execution.status = "running"
            db.flush()

            for node_id in node_map:
                db.add(NodeRun(execution_id=execution.id, node_id=node_id, status="pending", logs=""))
            db.flush()

        await _publish(execution_id, {"type": "execution", "execution_id": execution_id, "status": "running"})

        outputs: dict[str, dict[str, Any]] = {}
        context: dict[str, Any] = {}
        statuses: dict[str, str] = {node_id: "pending" for node_id in node_map}
        execution_failed = False

        for node_id in order:
            node = node_map[node_id]
            with db_session() as db:
                node_run = db.query(NodeRun).filter_by(execution_id=execution_id, node_id=node_id).one()
                if not _should_execute(node_id, incoming_edges, statuses, outputs, node_types):
                    node_run.status = "skipped"
                    node_run.logs = "Node skipped (upstream conditions not met)"
                    statuses[node_id] = "skipped"
                    await _publish(
                        execution_id,
                        {
                            "type": "node",
                            "node_id": node_id,
                            "status": "skipped",
                            "logs": node_run.logs,
                        },
                    )
                    continue

                started = perf_counter()
                node_run.status = "running"
                statuses[node_id] = "running"
                await _publish(execution_id, {"type": "node", "node_id": node_id, "status": "running", "logs": ""})

                try:
                    output, logs = await execute_node(node["type"], node.get("data", {}), context)
                    duration_ms = int((perf_counter() - started) * 1000)
                    node_run.status = "success"
                    node_run.duration_ms = duration_ms
                    node_run.logs = logs
                    statuses[node_id] = "success"
                    outputs[node_id] = output
                    context[node_id] = output
                    await _publish(
                        execution_id,
                        {
                            "type": "node",
                            "node_id": node_id,
                            "status": "success",
                            "logs": logs,
                            "duration_ms": duration_ms,
                        },
                    )
                except Exception as exc:
                    duration_ms = int((perf_counter() - started) * 1000)
                    node_run.status = "failed"
                    node_run.duration_ms = duration_ms
                    node_run.logs = str(exc)
                    statuses[node_id] = "failed"
                    execution_failed = True
                    await _publish(
                        execution_id,
                        {
                            "type": "node",
                            "node_id": node_id,
                            "status": "failed",
                            "logs": str(exc),
                            "duration_ms": duration_ms,
                        },
                    )

        with db_session() as db:
            execution = db.get(Execution, execution_id)
            if execution is None:
                return

            for node_id in node_map:
                node_run = db.query(NodeRun).filter_by(execution_id=execution_id, node_id=node_id).one()
                if node_run.status == "pending":
                    node_run.status = "skipped"
                    node_run.logs = "Node skipped"

            execution.status = "failed" if execution_failed else "success"
            execution.finished_at = datetime.utcnow()

        await _publish(
            execution_id,
            {"type": "execution", "execution_id": execution_id, "status": "failed" if execution_failed else "success"},
        )
    except Exception as exc:
        logger.exception("Erreur inattendue pendant l'exécution %s", execution_id)
        await _mark_execution_failed(execution_id, str(exc))


async def run_execution_background(execution_id: int) -> None:
    try:
        await run_execution(execution_id)
    except Exception as exc:
        logger.exception("Erreur non gérée dans run_execution_background pour %s", execution_id)
        await _mark_execution_failed(execution_id, str(exc))
