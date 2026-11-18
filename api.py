import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import core
from agent import run

core.init()
app = FastAPI(title="MCP Business-Tools Agent")
KEY = os.getenv("APPROVER_KEY", "")

class Ask(BaseModel):
    q: str

def _auth(k):
    if not KEY or k != KEY:
        raise HTTPException(401, "bad approver key")

@app.post("/ask")
async def ask(a: Ask):
    text, calls = await run(a.q)
    return {"answer": text, "tool_calls": calls}

@app.get("/pending")
def pending():
    with core.conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM pending WHERE status='pending'")]

@app.post("/approve/{pid}")
def approve(pid: int, x_approver_key: str = Header("")):
    _auth(x_approver_key)
    try:
        return core.approve(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/reject/{pid}")
def reject(pid: int, x_approver_key: str = Header("")):
    _auth(x_approver_key)
    return core.reject(pid)

@app.get("/audit")
def audit():
    with core.conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")]
