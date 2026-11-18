"""No LLM needed: proves 'zero unapproved writes'. Run: pytest -q"""
import os
os.environ["BIZ_DB"] = "test.db"
if os.path.exists("test.db"):
    os.remove("test.db")
import pytest
import core
core.init()

def count(t):
    with core.conn() as c:
        return c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

def paid():
    with core.conn() as c:
        return c.execute("SELECT COUNT(*) FROM invoices WHERE status='paid'").fetchone()[0]

def test_writes_only_queue():
    p0 = paid()
    core.queue_write("draft_email", {"to": "a@b.c", "subject": "s", "body": "b"})
    core.queue_write("create_event", {"title": "t", "start": "2026-11-20T10:00"})
    core.queue_write("mark_invoice_paid", {"invoice_id": 1})
    assert count("outbox") == 0 and count("events") == 0 and paid() == p0

def test_approve_executes_once():
    pid = core.queue_write("mark_invoice_paid", {"invoice_id": 2})["pending_id"]
    p0 = paid()
    core.approve(pid)
    assert paid() == p0 + 1
    with pytest.raises(ValueError):
        core.approve(pid)

def test_unknown_tool_blocked():
    with pytest.raises(ValueError):
        core.queue_write("drop_table", {})

def test_audit_written():
    assert count("audit") > 0
