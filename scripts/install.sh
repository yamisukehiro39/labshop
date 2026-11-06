#!/bin/bash
# Called by the SSM bootstrap after checkout. Amazon Linux 2023 x86_64.
set -euo pipefail
umask 027
ROLE="$1"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
exec 9>/var/lock/labshop-install.lock
flock -w 600 9
if [[ "$ROLE" == app ]]; then
  dnf install -y python3 python3-pip
  id labshop >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /sbin/nologin labshop
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install --disable-pip-version-check -r "$ROOT/requirements.txt"
  curl --fail --silent --show-error --retry 5 --proto '=https' --tlsv1.2 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /etc/labshop/rds-ca.pem
  chmod 644 /etc/labshop/rds-ca.pem
  cd "$ROOT"
  "$ROOT/.venv/bin/python" -m scripts.bootstrap_aws
  chown root:labshop /etc/labshop/db.json
  chmod 640 /etc/labshop/db.json
  python3 - <<'CONFIG'
import json
from pathlib import Path
c=json.loads(Path('/etc/labshop/config.json').read_text())
assert c['mode'] in ('secure','vulnerable')
Path('/etc/labshop/service.env').write_text('LAB_MODE='+c['mode']+'\nCOOKIE_SECURE='+str(c['cookie_secure']).lower()+'\n')
CONFIG
  cp "$ROOT/scripts/labshop.service" /etc/systemd/system/labshop.service
  # Code is root-owned, readable by service. Runtime cannot modify deployed source.
  chmod -R a+rX "$ROOT"
  ln -sfn "$ROOT" /opt/labshop/current.next
  mv -Tf /opt/labshop/current.next /opt/labshop/current
  systemctl daemon-reload
  systemctl enable labshop
  systemctl restart labshop
  for attempt in {1..30}; do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null; then echo 'LabShop API ready'; exit 0; fi
    sleep 2
  done
  echo 'API readiness failed; inspect journalctl -u labshop' >&2
  exit 1
elif [[ "$ROLE" == web ]]; then
  dnf install -y nginx
  install -d -m 755 /usr/share/nginx/labshop
  cp "$ROOT"/frontend/* /usr/share/nginx/labshop/
  chmod -R a+rX /usr/share/nginx/labshop
  python3 "$ROOT/scripts/configure_nginx.py"
  nginx -t
  systemctl enable nginx
  systemctl restart nginx
  curl --retry 10 --retry-all-errors --retry-delay 3 -fsS http://127.0.0.1/api/health >/dev/null
  echo 'LabShop web ready'
else
  echo 'Role must be app or web' >&2; exit 2
fi
