# Workflow Deployer (MVP)

Application MVP de création/exécution de workflows de déploiement (inspirée de n8n) avec éditeur visuel React Flow et backend FastAPI.

## Architecture

```text
+-------------------+          REST/WebSocket          +-------------------+
| Frontend (Vite)   | <------------------------------> | Backend (FastAPI) |
| React + ReactFlow |                                   | Engine + API      |
+---------+---------+                                   +---------+---------+
          |                                                       |
          | docker-compose                                        | SQLAlchemy
          v                                                       v
                                +-------------------+
                                | PostgreSQL (db)   |
                                +-------------------+
```

## Stack
- Frontend: React + TypeScript + `@xyflow/react` + Vite
- Backend: FastAPI + SQLAlchemy
- DB: PostgreSQL (par défaut), fallback SQLite en local
- Temps réel: WebSocket (`/ws/executions/{execution_id}`)
- Conteneurisation: Docker + Docker Compose

## Prérequis
- Docker + Docker Compose
- (Optionnel local) Python 3.12+, Node 22+

## Lancement en une commande
```bash
docker compose up --build
```

## URLs
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

## Lancement manuel (dev)

> Les commandes ci-dessous sont à exécuter depuis la racine du dépôt cloné.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

> Sous Windows (PowerShell), activez l'environnement virtuel avec `.\.venv\Scripts\Activate.ps1`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Format JSON d'un workflow

Structure:
- `name`: nom du workflow
- `version`: version entière
- `graph.nodes[]`: nœuds (`id`, `type`, `position`, `data`)
- `graph.edges[]`: connexions (`id`, `source`, `target`, `on` optionnel: `success`/`failure`)

Exemple complet (4 nœuds: `manualTrigger → shell → condition → notify`) disponible dans:
- `examples/sample-workflow.json`

## Types de nœuds MVP
- `manualTrigger`: démarre le workflow
- `shell`: exécute `command` via subprocess (timeout 15s) et capture stdout/stderr
- `gitCommit`: opérations Git locales sur `repoPath` (`addAll`, `commit`, `message`, `push`, `remote`, `branch`) et expose `commitHash`
- `sshCommand`: exécute une commande distante (`host`, `port`, `username`, `command`, `password` ou `privateKey`, `passphrase`, `timeout`)
- `httpRequest`: requête HTTP (`method`, `url`, `body`)
- `condition`: évalue `expression` sur `context`
- `notify`: log message (`message`) avec variables `{{ nodeId.field }}`
- `delay`: attend `seconds`

## Éditeur visuel
- Glisser-déposer depuis la palette pour créer des nœuds.
- Clic droit sur un nœud pour ouvrir le menu contextuel:
  - `Modifier` (sélectionne le nœud pour éditer ses propriétés)
  - `Dupliquer` (copie le nœud avec un décalage de position)
  - `Supprimer` (retire le nœud et ses arêtes entrantes/sortantes)

## Endpoints principaux
- Workflows: `POST/GET/PUT/DELETE /api/workflows`
- Import/Export: `POST /api/workflows/import`, `GET /api/workflows/{id}/export`
- Exécution: `POST /api/workflows/{id}/run`, `GET /api/executions`, `GET /api/executions/{id}`
- WebSocket: `/ws/executions/{execution_id}`

## Tests backend
```bash
cd backend
pytest
```

## Limitations & next steps
- Authentification, RBAC, multi-tenant
- Gestion chiffrée des secrets
- Nodes avancés (Docker/Kubernetes/Slack)
- Versionnage avancé des workflows
- Exécution distribuée/workers

## Notes sécurité MVP
Le nœud `shell` exécute des commandes système (`subprocess`). Ce comportement est utile pour le MVP mais potentiellement risqué en production (sandboxing/allowlist requis).

- `sshCommand` utilise `paramiko.AutoAddPolicy()` pour un usage local simplifié : cela accepte automatiquement les clés d'hôte et expose à un risque MITM si utilisé hors environnement local de confiance.
- Les credentials SSH (`password`, `privateKey`, `passphrase`) sont stockés en clair dans le JSON du workflow. Ceci est acceptable uniquement pour un usage local; ne pas utiliser en production.
- `gitCommit` peut appeler `git push` si activé: des credentials Git doivent déjà être configurés sur la machine (SSH agent, helper, token, etc.).

## Exemple JSON (git + ssh)
```json
{
  "name": "Git and SSH demo",
  "version": 1,
  "graph": {
    "nodes": [
      { "id": "trigger", "type": "manualTrigger", "position": { "x": 40, "y": 80 }, "data": { "label": "Start" } },
      {
        "id": "git",
        "type": "gitCommit",
        "position": { "x": 280, "y": 80 },
        "data": {
          "label": "Commit",
          "repoPath": "./",
          "message": "chore: automated workflow commit",
          "addAll": true,
          "commit": true,
          "push": false
        }
      },
      {
        "id": "ssh",
        "type": "sshCommand",
        "position": { "x": 520, "y": 80 },
        "data": {
          "label": "Remote check",
          "host": "127.0.0.1",
          "port": 22,
          "username": "user",
          "command": "echo ready",
          "timeout": 10
        }
      }
    ],
    "edges": [
      { "id": "e1", "source": "trigger", "target": "git" },
      { "id": "e2", "source": "git", "target": "ssh" }
    ]
  }
}
```
