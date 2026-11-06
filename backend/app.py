import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from functools import wraps
from flask import Flask, request, jsonify, g, abort
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash
from backend.db import connect

log = logging.getLogger("labshop")
logging.basicConfig(level=logging.INFO, format="%(message)s")

def create_app(overrides=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=16384, LAB_MODE=os.getenv("LAB_MODE", "secure"),
                      COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true")
    if overrides:
        app.config.update(overrides)
    if app.config["LAB_MODE"] not in ("secure", "vulnerable"):
        raise ValueError("LAB_MODE must be secure or vulnerable")

    def vulnerable():
        return app.config["LAB_MODE"] == "vulnerable"

    def login_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            token = request.cookies.get("labshop_session", "")
            digest = hashlib.sha256(token.encode()).hexdigest()
            with connect() as db:
                user = db.execute("SELECT u.id,u.email,u.display_name FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>now()", (digest,)).fetchone()
            if not user:
                abort(401, "Connexion requise")
            g.user = user
            return fn(*args, **kwargs)
        return wrapped

    @app.before_request
    def begin():
        g.start = time.monotonic()
        g.request_id = str(uuid.uuid4())
        # JSON plus a custom header and no CORS prevent ordinary cross-origin form requests.
        if request.method in ("POST", "PUT", "DELETE"):
            if request.headers.get("X-LabShop-Client") != "web":
                abort(403, "En-tête client requis")
            if request.method != "DELETE" and not request.is_json:
                abort(415, "JSON requis")

    @app.after_request
    def finish(response):
        response.headers["X-Request-ID"] = g.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        log.info(json.dumps({"event":"request", "request_id":g.request_id,
            "method":request.method, "path":request.path, "status":response.status_code,
            "duration_ms":round((time.monotonic()-g.start)*1000), "mode":app.config["LAB_MODE"]}))
        return response

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.description, request_id=getattr(g,"request_id",None)), e.code

    @app.errorhandler(Exception)
    def unexpected(e):
        log.error(json.dumps({"event":"error", "type":type(e).__name__, "request_id":getattr(g,"request_id",None)}))
        return jsonify(error="Erreur interne", request_id=getattr(g,"request_id",None)), 500

    def body():
        data = request.get_json()
        if not isinstance(data, dict):
            abort(400, "Objet JSON requis")
        return data

    @app.get("/health")
    def health():
        try:
            with connect() as db:
                db.execute("SELECT 1 FROM products LIMIT 1")
            return jsonify(status="ok")
        except Exception:
            return jsonify(status="unavailable"),503

    @app.get("/config")
    def config():
        return jsonify(mode=app.config["LAB_MODE"], version="1.0.0")

    @app.get("/products")
    def products():
        q = request.args.get("q", "")[:200]
        with connect() as db:
            # INTENTIONAL SQLi: read-only transaction contains the demonstration.
            db.execute("SET TRANSACTION READ ONLY")
            db.execute("SET LOCAL statement_timeout = '2s'")
            if vulnerable():
                rows = db.execute("SELECT id,name,description,price_cents,stock,icon FROM products WHERE visible=true AND name ILIKE '%" + q + "%' ORDER BY id").fetchall()
            else:
                rows = db.execute("SELECT id,name,description,price_cents,stock,icon FROM products WHERE visible=true AND name ILIKE %s ORDER BY id", ("%"+q+"%",)).fetchall()
        return jsonify(rows)

    @app.post("/auth/login")
    def login():
        data = body()
        email, password = data.get("email"), data.get("password")
        if not isinstance(email,str) or not isinstance(password,str) or len(password)>200:
            abort(400,"Identifiants invalides")
        with connect() as db:
            user = db.execute("SELECT * FROM users WHERE email=%s", (email,)).fetchone()
            if not user or not check_password_hash(user["password_hash"], password):
                abort(401,"Identifiants invalides")
            token = secrets.token_urlsafe(32)
            db.execute("DELETE FROM sessions WHERE expires_at<now()")
            db.execute("INSERT INTO sessions(token_hash,user_id) VALUES (%s,%s)", (hashlib.sha256(token.encode()).hexdigest(),user["id"]))
        response = jsonify(id=user["id"], display_name=user["display_name"])
        response.set_cookie("labshop_session",token,httponly=True,secure=app.config["COOKIE_SECURE"],samesite="Lax",max_age=28800,path="/api/")
        return response

    @app.post("/auth/logout")
    def logout():
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=%s", (hashlib.sha256(request.cookies.get("labshop_session", "").encode()).hexdigest(),))
        response = jsonify(ok=True)
        response.delete_cookie("labshop_session",path="/api/")
        return response

    @app.get("/me")
    @login_required
    def me():
        return jsonify(g.user)

    @app.get("/orders")
    @login_required
    def orders():
        with connect() as db:
            rows=db.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY id DESC",(g.user["id"],)).fetchall()
        return jsonify(rows)

    @app.get("/orders/<int:order_id>")
    @login_required
    def order(order_id):
        with connect() as db:
            row=db.execute("SELECT * FROM orders WHERE id=%s",(order_id,)).fetchone()
            if not row: abort(404,"Commande inconnue")
            # INTENTIONAL IDOR: infrastructure filtering does not repair missing ownership.
            if not vulnerable() and row["user_id"] != g.user["id"]: abort(403,"Commande privée")
            row["items"]=db.execute("SELECT i.*,p.name FROM order_items i JOIN products p ON p.id=i.product_id WHERE order_id=%s",(order_id,)).fetchall()
        return jsonify(row)

    @app.post("/orders")
    @login_required
    def checkout():
        items=body().get("items")
        if not isinstance(items,list) or not 1<=len(items)<=20: abort(400,"Panier invalide")
        selected={}
        for item in items:
            if not isinstance(item,dict): abort(400,"Article invalide")
            pid,qty=item.get("product_id"),item.get("quantity")
            if type(pid) is not int or type(qty) is not int or not 1<=qty<=10 or pid in selected: abort(400,"Quantité ou produit invalide")
            selected[pid]=qty
        with connect() as db:
            rows=db.execute("SELECT * FROM products WHERE id=ANY(%s) AND visible=true ORDER BY id FOR UPDATE",(list(selected),)).fetchall()
            if len(rows)!=len(selected): abort(400,"Produit indisponible")
            if any(p["stock"]<selected[p["id"]] for p in rows): abort(409,"Stock insuffisant")
            total=sum(p["price_cents"]*selected[p["id"]] for p in rows)
            oid=db.execute("INSERT INTO orders(user_id,total_cents) VALUES(%s,%s) RETURNING id",(g.user["id"],total)).fetchone()["id"]
            for p in rows:
                qty=selected[p["id"]]
                db.execute("INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(%s,%s,%s,%s)",(oid,p["id"],qty,p["price_cents"]))
                db.execute("UPDATE products SET stock=stock-%s WHERE id=%s",(qty,p["id"]))
        return jsonify(id=oid,total_cents=total),201

    @app.get("/products/<int:pid>/reviews")
    def reviews(pid):
        with connect() as db:
            rows=db.execute("SELECT r.id,r.body,u.display_name FROM reviews r JOIN users u ON u.id=r.user_id WHERE product_id=%s ORDER BY r.id DESC LIMIT 50",(pid,)).fetchall()
        return jsonify(rows)

    @app.post("/products/<int:pid>/reviews")
    @login_required
    def review(pid):
        text=body().get("body")
        if not isinstance(text,str) or not 1<=len(text)<=500: abort(400,"Avis de 1 à 500 caractères requis")
        with connect() as db:
            if not db.execute("SELECT id FROM products WHERE id=%s AND visible=true",(pid,)).fetchone(): abort(404,"Produit inconnu")
            rid=db.execute("INSERT INTO reviews(product_id,user_id,body) VALUES(%s,%s,%s) RETURNING id",(pid,g.user["id"],text)).fetchone()["id"]
        return jsonify(id=rid),201

    return app

app = create_app()
