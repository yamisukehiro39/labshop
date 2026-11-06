"""Integration tests against real PostgreSQL; database must be disposable."""
import os
import pytest
from backend.app import create_app
from backend.db import connect
from scripts.migrate import migrate
H={"X-LabShop-Client":"web"}

@pytest.fixture(scope="session",autouse=True)
def database():
    if not os.getenv('DATABASE_URL'): pytest.skip('Set DATABASE_URL to a disposable PostgreSQL database')
    migrate()
    migrate()  # repeated installation must preserve schema/data

@pytest.fixture(params=['secure','vulnerable'])
def client(request):
    app=create_app({'TESTING':True,'LAB_MODE':request.param,'COOKIE_SECURE':False})
    c=app.test_client()
    c.mode=request.param
    return c

def login(client,email='alice@labshop.test'):
    r=client.post('/auth/login',json={'email':email,'password':'LabShop-Demo-2026!'},headers=H)
    assert r.status_code==200
    # API paths are internally unprefixed; browser uses /api/ via Nginx.
    cookie=client.get_cookie('labshop_session',path='/api/')
    client.set_cookie('labshop_session',cookie.value,path='/')
    return r.json

def test_health_and_catalogue(client):
    assert client.get('/health').status_code==200
    products=client.get('/products').json
    assert len(products)==6
    assert all(p['id']!=7 for p in products)

def test_sqli_differential(client):
    r=client.get('/products',query_string={'q':"' OR 1=1 -- "})
    assert r.status_code==200
    ids=[x['id'] for x in r.json]
    assert (7 in ids)==(client.mode=='vulnerable')

def test_auth_and_idor(client):
    assert client.get('/orders').status_code==401
    alice=login(client)
    with connect() as db:
        own=db.execute('SELECT id FROM orders WHERE user_id=%s LIMIT 1',(alice['id'],)).fetchone()['id']
        other=db.execute('SELECT id FROM orders WHERE user_id<>%s LIMIT 1',(alice['id'],)).fetchone()['id']
    assert client.get(f'/orders/{own}').status_code==200
    assert client.get(f'/orders/{other}').status_code==(200 if client.mode=='vulnerable' else 403)

def test_checkout_price_stock_and_validation(client):
    login(client)
    with connect() as db: before=db.execute('SELECT stock,price_cents FROM products WHERE id=1').fetchone()
    r=client.post('/orders',json={'items':[{'product_id':1,'quantity':1,'price_cents':1}]},headers=H)
    assert r.status_code==201
    assert r.json['total_cents']==before['price_cents']
    with connect() as db: assert db.execute('SELECT stock FROM products WHERE id=1').fetchone()['stock']==before['stock']-1
    for items in [[],[{'product_id':1,'quantity':-1}],[{'product_id':7,'quantity':1}],[{'product_id':1,'quantity':True}],[{'product_id':1,'quantity':1}]*2]:
        assert client.post('/orders',json={'items':items},headers=H).status_code==400

def test_review_persistence(client):
    login(client)
    marker='<img src=x onerror="alert(1)">'
    r=client.post('/products/1/reviews',json={'body':marker},headers=H)
    assert r.status_code==201
    assert any(x['body']==marker for x in client.get('/products/1/reviews').json)
    assert client.post('/products/99999/reviews',json={'body':'test'},headers=H).status_code==404

def test_request_limits(client):
    assert client.post('/auth/login',json={}).status_code==403
    assert client.post('/auth/login',json=[],headers=H).status_code==400
    assert client.post('/auth/login',json={'email':'a','password':'x'*20000},headers=H).status_code==413
    assert client.get('/unknown').status_code==404
    assert client.post('/auth/login',json={'email':"' OR 1=1 --",'password':'x'},headers=H).status_code==401

def test_session_survives_app_recreation(client):
    login(client)
    token=client.get_cookie('labshop_session',path='/').value
    other=create_app({'TESTING':True,'COOKIE_SECURE':False}).test_client()
    other.set_cookie('labshop_session',token,path='/')
    assert other.get('/me').status_code==200
    assert other.post('/auth/logout',json={},headers=H).status_code==200
    assert client.get('/me').status_code==401

def test_insufficient_stock_is_atomic(client):
    login(client)
    with connect() as db:
        original=db.execute('SELECT stock FROM products WHERE id=2').fetchone()['stock']
        db.execute('UPDATE products SET stock=0 WHERE id=2')
        count=db.execute('SELECT count(*) AS n FROM orders').fetchone()['n']
    try:
        r=client.post('/orders',json={'items':[{'product_id':2,'quantity':1}]},headers=H)
        assert r.status_code==409
        with connect() as db: assert db.execute('SELECT count(*) AS n FROM orders').fetchone()['n']==count
    finally:
        with connect() as db: db.execute('UPDATE products SET stock=%s WHERE id=2',(original,))
