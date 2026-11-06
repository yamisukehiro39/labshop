import ipaddress
import json
from pathlib import Path
c=json.loads(Path('/etc/labshop/config.json').read_text())
servers='\n'.join('server '+str(ipaddress.IPv4Address(ip))+':8000 max_fails=3 fail_timeout=10s;' for ip in c['upstreams'])
assert servers
# CSP intentionally allows inline event handlers only when demonstrating stored XSS.
csp="default-src 'self'; script-src 'self'"+(" 'unsafe-inline'" if c['mode']=='vulnerable' else '')+"; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
text=Path(__file__).with_name('nginx.conf.template').read_text().replace('__UPSTREAMS__',servers).replace('__CSP__',csp)
Path('/etc/nginx/nginx.conf').write_text(text)
