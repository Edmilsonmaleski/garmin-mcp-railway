#!/bin/bash
set -e

echo "=== Verificando tokens ===" >&2
ls -la /root/.garminconnect/ >&2

export GARMINTOKENS=/root/.garminconnect

exec python << 'PYEOF'
import os
import sys

os.environ['GARMINTOKENS'] = '/root/.garminconnect'

import garmin_mcp as gm
from mcp.server.fastmcp import FastMCP
import inspect
print("FastMCP.run signature:", inspect.signature(FastMCP.run), file=sys.stderr)
PYEOF
