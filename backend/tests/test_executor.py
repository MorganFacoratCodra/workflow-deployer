import pytest

from app.engine.executor import execute_graph_in_memory, topological_sort


@pytest.mark.asyncio
async def test_topological_sort_linear_graph():
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    edges = [
        {"id": "e1", "source": "a", "target": "b"},
        {"id": "e2", "source": "b", "target": "c"},
    ]

    assert topological_sort(nodes, edges) == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_execute_simple_workflow_success():
    graph = {
        "nodes": [
            {"id": "trigger", "type": "manualTrigger", "data": {}},
            {"id": "notify", "type": "notify", "data": {"message": "Hello {{ trigger.triggered }}"}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "target": "notify"}],
    }

    statuses, outputs = await execute_graph_in_memory(graph)

    assert statuses["trigger"] == "success"
    assert statuses["notify"] == "success"
    assert outputs["notify"]["message"] == "Hello True"


@pytest.mark.asyncio
async def test_failure_marks_downstream_skipped():
    graph = {
        "nodes": [
            {"id": "trigger", "type": "manualTrigger", "data": {}},
            {"id": "shell", "type": "shell", "data": {"command": "exit 1"}},
            {"id": "notify", "type": "notify", "data": {"message": "Should not run"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "shell"},
            {"id": "e2", "source": "shell", "target": "notify"},
        ],
    }

    statuses, _ = await execute_graph_in_memory(graph)

    assert statuses["trigger"] == "success"
    assert statuses["shell"] == "failed"
    assert statuses["notify"] == "skipped"
