import asyncio
import ast
import io
import json
import operator
import os
import re
from typing import Any

import httpx
import paramiko


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


async def _run_git_command(
    repo_path: str,
    args: list[str],
    timeout_seconds: int,
    logs: list[str],
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    command = "$ git " + " ".join(args)
    logs.append(command)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        process.kill()
        logs.append(f"Commande expirée après {timeout_seconds}s")
        raise NodeExecutionError("\n".join(logs)) from exc

    output = stdout.decode().strip()
    error = stderr.decode().strip()
    if output:
        logs.append(output)
    if error:
        logs.append(error)
    return process.returncode, output, error


async def run_git_commit(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    del context
    repo_path = str(node_data.get("repoPath", "")).strip()
    if not repo_path:
        raise NodeExecutionError("Paramètre manquant: repoPath")
    if not os.path.isdir(repo_path):
        raise NodeExecutionError(f"Le chemin du dépôt est introuvable: {repo_path}")

    add_all = bool(node_data.get("addAll", True))
    should_commit = bool(node_data.get("commit", True))
    should_push = bool(node_data.get("push", False))
    message = str(node_data.get("message", "")).strip()
    remote = str(node_data.get("remote", "origin")).strip() or "origin"
    branch = str(node_data.get("branch", "")).strip()

    if should_commit and not message:
        raise NodeExecutionError("Paramètre manquant: message (requis quand commit=true)")

    logs: list[str] = []
    committed = False
    pushed = False

    if add_all:
        returncode, _, _ = await _run_git_command(repo_path, ["add", "-A"], 30, logs)
        if returncode != 0:
            raise NodeExecutionError("\n".join(logs))

    if should_commit:
        returncode, output, error = await _run_git_command(repo_path, ["commit", "-m", message], 30, logs)
        commit_output = f"{output}\n{error}".lower()
        if returncode != 0:
            if "nothing to commit" in commit_output or "nothing added to commit" in commit_output:
                logs.append("Aucun changement à commit (considéré comme succès)")
            else:
                raise NodeExecutionError("\n".join(logs))
        else:
            committed = True

    if should_push:
        push_args = ["push", remote]
        if branch:
            push_args.append(branch)
        returncode, _, _ = await _run_git_command(repo_path, push_args, 60, logs)
        if returncode != 0:
            raise NodeExecutionError("\n".join(logs))
        pushed = True

    hash_code, commit_hash, _ = await _run_git_command(repo_path, ["rev-parse", "HEAD"], 30, logs)
    if hash_code != 0:
        raise NodeExecutionError("\n".join(logs))

    branch_code, current_branch, _ = await _run_git_command(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"], 30, logs)
    if branch_code != 0:
        raise NodeExecutionError("\n".join(logs))

    return {
        "commitHash": commit_hash,
        "branch": current_branch,
        "committed": committed,
        "pushed": pushed,
    }, "\n".join(logs)


def _load_private_key(private_key_value: str, passphrase: str | None) -> paramiko.PKey:
    key_text: str
    if os.path.exists(private_key_value):
        with open(private_key_value, encoding="utf-8") as key_file:
            key_text = key_file.read()
    else:
        key_text = private_key_value

    for key_cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
        key_stream = io.StringIO(key_text)
        try:
            return key_cls.from_private_key(key_stream, **{"password": passphrase})
        except Exception:
            continue

    raise NodeExecutionError("Clé privée SSH invalide ou format non supporté")


def _run_ssh_command_sync(
    host: str,
    port: int,
    username: str,
    command: str,
    password: str | None,
    private_key_value: str | None,
    passphrase: str | None,
    timeout: int,
) -> tuple[dict[str, Any], str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    logs = [f"ssh {username}@{host}:{port} $ {command}"]
    pkey = _load_private_key(private_key_value, passphrase) if private_key_value else None

    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            **{"password": password or None},
            pkey=pkey,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
        )
        _, stdout_stream, stderr_stream = client.exec_command(command, timeout=timeout)
        stdout = stdout_stream.read().decode().strip()
        stderr = stderr_stream.read().decode().strip()
        exit_status = stdout_stream.channel.recv_exit_status()

        if stdout:
            logs.append(stdout)
        if stderr:
            logs.append(stderr)

        payload = {"stdout": stdout, "stderr": stderr, "exit_status": exit_status}
        if exit_status != 0:
            raise NodeExecutionError("\n".join(logs))
        return payload, "\n".join(logs)
    finally:
        client.close()


async def run_ssh_command(node_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    del context
    host = str(node_data.get("host", "")).strip()
    username = str(node_data.get("username", "")).strip()
    command = str(node_data.get("command", "")).strip()
    port = int(node_data.get("port", 22))
    timeout = int(node_data.get("timeout", 30))
    password = str(node_data.get("password", "")).strip() or None
    private_key_value = str(node_data.get("privateKey", "")).strip() or None
    passphrase = str(node_data.get("passphrase", "")).strip() or None

    if not host:
        raise NodeExecutionError("Paramètre manquant: host")
    if not username:
        raise NodeExecutionError("Paramètre manquant: username")
    if not command:
        raise NodeExecutionError("Paramètre manquant: command")

    try:
        return await asyncio.to_thread(
            _run_ssh_command_sync,
            host,
            port,
            username,
            command,
            password,
            private_key_value,
            passphrase,
            timeout,
        )
    except NodeExecutionError:
        raise
    except (
        paramiko.AuthenticationException,
        paramiko.BadHostKeyException,
        paramiko.SSHException,
        OSError,
        TimeoutError,
    ) as exc:
        raise NodeExecutionError(f"Connexion SSH impossible: {exc}") from exc


NODE_RUNNERS = {
    "manualTrigger": run_manual_trigger,
    "shell": run_shell,
    "httpRequest": run_http_request,
    "condition": run_condition,
    "notify": run_notify,
    "delay": run_delay,
    "gitCommit": run_git_commit,
    "sshCommand": run_ssh_command,
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
