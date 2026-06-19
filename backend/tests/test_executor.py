import pytest
import asyncio

from app.engine import nodes as node_module
from app.engine.executor import GraphValidationError, execute_graph_in_memory, topological_sort, validate_graph
from app.engine.nodes import NodeExecutionError, execute_node


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


def test_validate_graph_accepts_valid_graph():
    graph = {
        "nodes": [
            {"id": "trigger", "type": "manualTrigger", "data": {}},
            {"id": "notify", "type": "notify", "data": {"message": "ok"}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "target": "notify"}],
    }

    validate_graph(graph)


@pytest.mark.parametrize(
    ("graph", "expected"),
    [
        (
            {"nodes": [{"type": "manualTrigger"}], "edges": []},
            "n'a pas d'id valide",
        ),
        (
            {
                "nodes": [{"id": "a", "type": "manualTrigger"}],
                "edges": [{"id": "e1", "source": "a", "target": "missing"}],
            },
            "référence un nœud inexistant",
        ),
        (
            {
                "nodes": [
                    {"id": "a", "type": "manualTrigger"},
                    {"id": "b", "type": "notify"},
                ],
                "edges": [
                    {"id": "e1", "source": "a", "target": "b"},
                    {"id": "e2", "source": "b", "target": "a"},
                ],
            },
            "contient un cycle",
        ),
    ],
)
def test_validate_graph_rejects_invalid_graphs(graph, expected):
    with pytest.raises(GraphValidationError, match=expected):
        validate_graph(graph)


@pytest.mark.asyncio
async def test_git_commit_node_creates_commit(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    async def run(*args):
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(repo_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()
        return stdout.decode().strip()

    await run("git", "init")
    await run("git", "config", "user.email", "tests@example.com")
    await run("git", "config", "user.name", "Test Runner")

    test_file = repo_path / "hello.txt"
    test_file.write_text("hello\n", encoding="utf-8")

    output, logs = await execute_node(
        "gitCommit",
        {
            "repoPath": str(repo_path),
            "message": "feat: add hello file",
            "push": False,
        },
        {},
    )

    assert output["committed"] is True
    assert output["pushed"] is False
    assert output["commitHash"]
    assert output["branch"]
    assert "$ git commit -m feat: add hello file" in logs


@pytest.mark.asyncio
async def test_ssh_command_node_wraps_connection_errors(monkeypatch):
    class FakeSshClient:
        def set_missing_host_key_policy(self, policy):
            self.policy = policy

        def connect(self, **kwargs):
            raise OSError("Network is unreachable")

        def close(self):
            return None

    monkeypatch.setattr(node_module.paramiko, "SSHClient", FakeSshClient)

    with pytest.raises(NodeExecutionError, match="Connexion SSH impossible"):
        await execute_node(
            "sshCommand",
            {"host": "127.0.0.1", "port": 22, "username": "user", "command": "echo ok", "timeout": 1},
            {},
        )
