"""Executed as root by SSM. No credential is printed or passed in argv."""
import json
import os
import secrets
from pathlib import Path
import boto3
import psycopg
from psycopg import sql
from scripts.migrate import migrate

cfg=json.loads(Path('/etc/labshop/config.json').read_text())
sm=boto3.client('secretsmanager',region_name=cfg['region'])
master=json.loads(sm.get_secret_value(SecretId=cfg['master_secret_arn'])['SecretString'])
base=dict(host=cfg['db_host'],port=5432,dbname=cfg['db_name'],sslmode='verify-full',sslrootcert='/etc/labshop/rds-ca.pem')
# A separate session lock spans migration, password provisioning and grants, across AZs.
with psycopg.connect(**base,user=master['username'],password=master['password']) as lock:
    lock.execute('SELECT pg_advisory_lock(719382)')
    try:
        admin_path=Path('/etc/labshop/admin.tmp.json')
        fd=os.open(admin_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as out: json.dump(dict(base,user=master['username'],password=master['password']),out)
        os.environ['DB_CONFIG']=str(admin_path)
        migrate()
        try:
            runtime=json.loads(sm.get_secret_value(SecretId=cfg['runtime_secret_arn'])['SecretString'])
        except sm.exceptions.ResourceNotFoundException:
            runtime=dict(username='labshop_app',password=secrets.token_urlsafe(40))
            sm.put_secret_value(SecretId=cfg['runtime_secret_arn'],SecretString=json.dumps(runtime))
        if runtime['username']!='labshop_app': raise ValueError('Unexpected runtime database user')
        with psycopg.connect(**base,user=master['username'],password=master['password']) as db:
            if not db.execute("SELECT 1 FROM pg_roles WHERE rolname='labshop_app'").fetchone():
                db.execute('CREATE ROLE labshop_app LOGIN')
            db.execute(sql.SQL('ALTER ROLE labshop_app PASSWORD {}').format(sql.Literal(runtime['password'])))
            db.execute('GRANT USAGE ON SCHEMA public TO labshop_app')
            db.execute('GRANT SELECT ON users,products,orders,order_items,reviews,sessions TO labshop_app')
            db.execute('GRANT INSERT ON orders,order_items,reviews,sessions TO labshop_app')
            db.execute('GRANT UPDATE(stock) ON products TO labshop_app')
            db.execute('GRANT DELETE ON sessions TO labshop_app')
            db.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO labshop_app')
            db.execute("ALTER ROLE labshop_app SET statement_timeout='5s'")
        target=Path('/etc/labshop/db.json')
        tmp=target.with_suffix('.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as out: json.dump(dict(base,user=runtime['username'],password=runtime['password']),out)
        tmp.replace(target)
    finally:
        Path('/etc/labshop/admin.tmp.json').unlink(missing_ok=True)
        lock.execute('SELECT pg_advisory_unlock(719382)')
