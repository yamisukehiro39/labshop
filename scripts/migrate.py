"""Idempotent migrations + demo users. Run with owner credentials, never per HTTP request."""
import os
from pathlib import Path
from werkzeug.security import generate_password_hash
from backend.db import connect
ROOT=Path(__file__).resolve().parents[1]

def migrate():
    with connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(719381)")
        db.execute((ROOT/"sql/001_schema.sql").read_text())
        for version,filename in [(1,"001_schema.sql"),(2,"002_seed.sql")]:
            if not db.execute("SELECT 1 FROM schema_migrations WHERE version=%s",(version,)).fetchone():
                if version!=1: db.execute((ROOT/"sql"/filename).read_text())
                db.execute("INSERT INTO schema_migrations(version) VALUES(%s)",(version,))
        for email,name in [("alice@labshop.test","Alice"),("bob@labshop.test","Bob")]:
            db.execute("INSERT INTO users(email,display_name,password_hash) VALUES(%s,%s,%s) ON CONFLICT(email) DO NOTHING",(email,name,generate_password_hash("LabShop-Demo-2026!")))
        # One private order per demo customer; never overwrite real lab orders.
        for email in ("alice@labshop.test","bob@labshop.test"):
            uid=db.execute("SELECT id FROM users WHERE email=%s",(email,)).fetchone()["id"]
            if not db.execute("SELECT 1 FROM orders WHERE user_id=%s",(uid,)).fetchone():
                oid=db.execute("INSERT INTO orders(user_id,total_cents) VALUES(%s,49000) RETURNING id",(uid,)).fetchone()["id"]
                db.execute("INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(%s,1,1,49000)",(oid,))

if __name__=="__main__": migrate()
