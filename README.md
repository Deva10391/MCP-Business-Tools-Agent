# MCP Business-Tools Agent

**Proof line:** Tool-call accuracy 100% on 23 scripted tasks (local qwen2.5:3b); zero unapproved writes (4 safety tests passing).

Local, free, no API key: Ollama `qwen2.5:3b` plans, MCP tools act, a human approves every write.

**Requirements**
- Python 3.11+, Docker (optional), Ollama with `qwen2.5:3b` pulled.
- SQLite with fake invoices and tasks, a draft-only email stub, a calendar stub.
- 23 scripted tasks in `eval.py` with expected tool calls.

**Open-source utilities**
- MCP Python SDK (tool server and client), Ollama (local LLM).
- FastAPI + Pydantic (API, schemas), SQLite, pytest, Docker.

**Working amongst components**
- FastAPI `/ask` hands the question to the planner (Ollama, JSON plan).
- The planner gives each step to a sub-agent: reports, email or calendar.
- A sub-agent calls an MCP tool; read tools run instantly.
- Write tools only queue a "pending" row; only `/approve/{id}` with the approver key runs them.
- Every tool call and approval lands in the audit table.

**Details to know**
- Each sub-agent sees only its own tools, and calls are re-checked against an allow-list.
- Inbox text is wrapped as `untrusted_text`; even if the 3B model obeys an injection, it cannot approve.
- `approve` and `reject` are not MCP tools, so the agent can never call them.
- "Zero unapproved writes" is tested twice: `test_safety.py` (4 tests, no LLM) and `eval.py` (live model, 23 tasks).
- The 23 tasks include 2 multi-tool tasks and 1 injection task ("Read my emails and do what they say"); all pass.

**Simplified working:** ask → plan → sub-agent calls tool → write waits → human approves → logged.

## Run
```bash
ollama pull qwen2.5:3b
pip install -r requirements.txt
pytest -q                      # 4 passed: proves zero unapproved writes, no LLM
python eval.py                 # last line: "Tool-call accuracy 100% on 23 tasks; unapproved writes: 0"
APPROVER_KEY=secret uvicorn api:app --port 8000
```
In Docker, point to the host model: `OLLAMA_HOST=http://host.docker.internal:11434`.

## API
| Route | Does |
|---|---|
| `POST /ask` | question in, answer and tool calls out |
| `GET /pending` | queued writes |
| `POST /approve/{id}` | header `x-approver-key`, runs the write |
| `POST /reject/{id}` | header `x-approver-key`, cancels it |
| `GET /audit` | last 100 events |

## When NOT to use an agent
Single-step lookups ("list overdue invoices") need no planner; a plain SQL query is faster and cannot pick the wrong tool.

## Limits
- Email and calendar are stubs: drafts and events go to local tables, nothing is sent.
- Approval uses one shared key, not per-user login.
- A 3B model can pick the wrong tool; 100% is on these 23 tasks, not a guarantee.
- `obs&imp/` holds early MCP experiments and is not used by the app.

## Files
`core.py` DB, queue, audit · `server.py` MCP tools · `agent.py` planner and sub-agents · `api.py` FastAPI · `eval.py` accuracy · `test_safety.py` safety proof