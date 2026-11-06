"""Small read-only smoke check against YOUR lab URL, no scanning or load generation."""
import argparse
import json
import urllib.request
import urllib.parse
p=argparse.ArgumentParser()
p.add_argument('base_url',help='Example: http://localhost:8080')
p.add_argument('--sqli',action='store_true',help='Test the synthetic hidden product demonstration')
a=p.parse_args()
for path in ['/api/health','/api/config','/api/products']+(['/api/products?q='+urllib.parse.quote("' OR 1=1 -- ")] if a.sqli else []):
    try:
        with urllib.request.urlopen(a.base_url.rstrip('/')+path,timeout=10) as r:
            data=json.load(r)
            print(path,r.status,json.dumps(data,ensure_ascii=False))
    except Exception as e:
        print(path,type(e).__name__,str(e))
        raise SystemExit(1)
