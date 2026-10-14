# Coach-PFE

Backend **FastAPI** + **Google Gemini** pour accompagner la rédaction de mémoires PFE.

## Pipeline (`POST /analyze`)

1. Memory (session optionnelle)
2. Analyseur (Gemini)
3. RAG (`data/rag/*.md`)
4. Merge context
5. Planificateur (Gemini)
6. Writer + Reviewer (1 appel Gemini)
7. Anti-hallucination (Gemini)
8. Export PDF / DOCX (`exports/{job_id}/`)

Modèles : `GEMINI_MODEL` + `GEMINI_MODEL_FALLBACKS` (défaut `gemini-2.5-flash`).

## Installation

```powershell
cd C:\chemin\vers\coach-pfe
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Éditez .env : GEMINI_API_KEY=...
.\venv\Scripts\uvicorn.exe main:app --reload --host 127.0.0.1 --port 8000
```

- API : http://127.0.0.1:8000/docs
- UI : http://127.0.0.1:8000/ui/
- Santé : http://127.0.0.1:8000/ (affiche `gemini_model_chain`)

## Endpoints

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/` | Statut + modèles Gemini actifs |
| POST | `/analyze` | Pipeline complet |
| GET | `/exports/{job_id}/{filename}` | Télécharger PDF ou DOCX |

Corps `POST /analyze` :

```json
{
  "topic": "Votre sujet de PFE",
  "session_id": "optionnel"
}
```

## Quota Gemini (429)

- Évitez `gemini-2.0-flash` en gratuit (`limit: 0`).
- Utilisez `.env.example` comme modèle de configuration.
- Attendez 1–2 min entre deux analyses (~6 appels par requête).
- Consultez https://ai.dev/rate-limit

## Serveur MCP (Cursor / clients MCP)

Le projet expose un **serveur MCP** (stdio) avec outils et ressources RAG.

### Installation

```powershell
pip install -r requirements.txt
```

### Configuration Cursor

Le fichier `.cursor/mcp.json` est déjà présent. Redémarrez Cursor ou rechargez les serveurs MCP (**Settings → MCP**).

### Outils MCP

| Outil | Description |
|-------|-------------|
| `health_check` | Clé Gemini, modèles actifs |
| `analyze_pfe` | Pipeline complet (2–5 min) |
| `rag_search` | Recherche RAG sans Gemini |
| `list_rag_documents` | Liste des `.md` dans `data/rag/` |

### Ressources MCP

- `rag://methodologie_pfe.md` — contenu d’un fichier RAG
- `coach-pfe://config` — configuration Gemini

### Lancement manuel

```powershell
.\venv\Scripts\python.exe run_mcp.py
```

---

## Structure

```
coach-pfe/
├── agents/
│   ├── analyzer_agent.py
│   ├── planner_agent.py
│   ├── writer_reviewer_agent.py
│   ├── anti_hallucination_agent.py
│   ├── gemini_runner.py
│   └── text_utils.py
├── data/rag/
├── routes/
├── services/
├── models/
├── static/index.html
├── mcp_server/server.py
├── run_mcp.py
├── .cursor/mcp.json
├── exports/          (gitignored)
├── main.py
└── requirements.txt
```
