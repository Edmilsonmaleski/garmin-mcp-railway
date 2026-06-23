#!/bin/bash
set -e

echo "=== Verificando tokens ===" >&2
ls -la /root/.garminconnect/ >&2

export GARMINTOKENS=/root/.garminconnect

exec python << 'PYEOF'
import os
import sys

os.environ['GARMINTOKENS'] = '/root/.garminconnect'

from mcp.server.fastmcp import FastMCP
app = FastMCP('test')

# Lista todos os atributos disponíveis
attrs = [a for a in dir(app) if not a.startswith('_')]
print("Atributos FastMCP:", attrs, file=sys.stderr)
PYEOF
