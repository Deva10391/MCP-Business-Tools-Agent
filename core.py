import json, os, sqlite3, functools, datetime as dt

DB = os.getenv("BIZ_DB", "biz.db")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, client TEXT, amount REAL, due TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT, owner TEXT, due TEXT, done INTEGER);
        CREATE TABLE IF NOT EXISTS pending(id INTEGER PRIMARY KEY, tool TEXT, args TEXT, status TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, actor TEXT, tool TEXT, args TEXT, result TEXT);
        CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, to_addr TEXT, subject TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, title TEXT, start TEXT);
        """)
        if c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0:
            t = dt.date.today()
            d = lambda n: (t + dt.timedelta(days=n)).isoformat()
            c.executemany("INSERT INTO invoices(client,amount,due,status) VALUES(?,?,?,?)", [
                ("Acme", 1200, d(-3), "open"), ("Globex", 560, d(-10), "open"),
                ("Initech", 980, d(5), "open"), ("Umbrella", 2300, d(-1), "open"),
                ("Hooli", 450, d(-20), "paid")])
            c.executemany("INSERT INTO tasks(title,owner,due,done) VALUES(?,?,?,?)", [
                ("Send Q3 report", "asha", d(-2), 0), ("Renew domain", "ravi", d(3), 0),
                ("Update pricing page", "asha", d(7), 0)])

def audit(actor, tool, args, result):
    with conn() as c:
        c.execute("INSERT INTO audit(ts,actor,tool,args,result) VALUES(?,?,?,?,?)",
                  (dt.datetime.utcnow().isoformat(), actor, tool,
                   json.dumps(args, default=str), json.dumps(result, default=str)[:500]))

def logged(fn):
    """Every agent tool call lands in the audit log."""
    @functools.wraps(fn)
    def w(**kw):
        r = fn(**kw)
        audit("agent", fn.__name__, kw, r)
        return r
    return w

# ---- write side: allow-list of executors, run ONLY by human approval ----
def _mark_paid(invoice_id: int):
    with conn() as c:
        c.execute("UPDATE invoices SET status='paid' WHERE id=?", (invoice_id,))
    return {"invoice_id": invoice_id, "status": "paid"}

def _draft_email(to: str, subject: str, body: str):
    with conn() as c:
        c.execute("INSERT INTO outbox(to_addr,subject,body) VALUES(?,?,?)", (to, subject, body))
    return {"saved_as_draft": True, "to": to}   # draft-only stub, never sends

def _create_event(title: str, start: str):
    with conn() as c:
        c.execute("INSERT INTO events(title,start) VALUES(?,?)", (title, start))
    return {"event": title, "start": start}

EXEC = {"mark_invoice_paid": _mark_paid, "draft_email": _draft_email, "create_event": _create_event}

def queue_write(tool: str, args: dict):
    if tool not in EXEC:
        raise ValueError("tool not in allow-list")
    with conn() as c:
        cur = c.execute("INSERT INTO pending(tool,args,status,ts) VALUES(?,?,'pending',?)",
                        (tool, json.dumps(args), dt.datetime.utcnow().isoformat()))
        pid = cur.lastrowid
    return {"status": "pending", "pending_id": pid, "note": "waiting for human approval"}

def approve(pid: int, approver: str = "human"):
    with conn() as c:
        r = c.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone()
        if not r or r["status"] != "pending":
            raise ValueError("not pending")
        c.execute("UPDATE pending SET status='approved' WHERE id=?", (pid,))
    args = json.loads(r["args"])
    res = EXEC[r["tool"]](**args)
    audit(approver, "approve:" + r["tool"], args, res)
    return res

def reject(pid: int, approver: str = "human"):
    with conn() as c:
        c.execute("UPDATE pending SET status='rejected' WHERE id=? AND status='pending'", (pid,))
    audit(approver, "reject", {"id": pid}, "rejected")
    return {"id": pid, "status": "rejected"}
