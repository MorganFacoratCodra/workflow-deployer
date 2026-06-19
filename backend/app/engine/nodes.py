import asyncio
import ast
import json
import operator
import re
from typing import Any

import httpx


class NodeExecutionError(RuntimeError):
    pass


COMPARATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
}


def _render_template(message: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = context
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    return re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace, message)


async def run_manual_trigger(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    return {"triggered": True}, "Manual trigger executed"


async def run_shell(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    command = node_data.get("command", "")
    if not command:
        raise NodeExecutionError("Missing 'command' parameter")
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
    except asyncio.TimeoutError as exc:
        process.kill()
        raise NodeExecutionError("Shell command timed out") from exc

    output = stdout.decode().strip()
    err = stderr.decode().strip()
    logs = f"$ {command}\n{output}"
    if err:
        logs += f"\n{err}"
    if process.returncode != 0:
        raise NodeExecutionError(f"Command failed ({process.returncode}): {logs}")

    return {"stdout": output, "stderr": err, "returncode": process.returncode}, logs.strip()


async def run_http_request(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    method = str(node_data.get("method", "GET")).upper()
    url = node_data.get("url")
    if not url:
        raise NodeExecutionError("Missing 'url' parameter")
    body = node_data.get("body")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(method, url, json=body)
    payload = {
        "status_code": response.status_code,
        "body": response.text,
        "headers": dict(response.headers),
    }
    logs = f"HTTP {method} {url} -> {response.status_code}"
    if response.status_code >= 400:
        raise NodeExecutionError(f"HTTP request failed: {logs}")
    return payload, logs


async def run_condition(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    expression = node_data.get("expression", "False")
    try:
        result = bool(_safe_eval(expression, context))
    except Exception as exc:
        raise NodeExecutionError(f"Invalid condition expression: {exc}") from exc
    route = "success" if result else "failure"
    return {"result": result, "route": route}, f"Condition evaluated to {result}"


async def run_notify(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    message = node_data.get("message", "")
    rendered = _render_template(message, context)
    return {"message": rendered}, f"Notification: {rendered}"


async def run_delay(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    seconds = float(node_data.get("seconds", 1))
    await asyncio.sleep(max(seconds, 0))
    return {"slept": seconds}, f"Delayed for {seconds} seconds"


NODE_RUNNERS = {
    "manualTrigger": run_manual_trigger,
    "shell": run_shell,
    "httpRequest": run_http_request,
    "condition": run_condition,
    "notify": run_notify,
    "delay": run_delay,
}


async def execute_node(node_type: str, node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    runner = NODE_RUNNERS.get(node_type)
    if runner is None:
        raise NodeExecutionError(f"Unsupported node type: {node_type}")
    return await runner(node_data, context)


def _safe_eval(expression: str, context: dict[str, Any]) -> Any:
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "context":
                return context
            if node.id in context:
                return context[node.id]
            raise ValueError(f"Unknown variable: {node.id}")
        if isinstance(node, ast.Subscript):
            value = _eval(node.value)
            key = _eval(node.slice)
            return value[key]
        if isinstance(node, ast.Index):  # pragma: no cover
            return _eval(node.value)
        if isinstance(node, ast.Attribute):
            value = _eval(node.value)
            if isinstance(value, dict):
                return value.get(node.attr)
            raise ValueError("Only dict attribute access is supported")
        if isinstance(node, ast.BoolOp):
            values = [_eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
            raise ValueError("Unsupported boolean operator")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not bool(_eval(node.operand))
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval(comparator)
                fn = COMPARATORS.get(type(op))
                if fn is None:
                    raise ValueError("Unsupported comparator")
                if not fn(left, right):
                    return False
                left = right
            return True
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return _eval(tree)
