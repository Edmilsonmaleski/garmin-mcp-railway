#!/bin/bash
set -e

export GARMINTOKENS=/root/.garminconnect

exec python << 'PYEOF'
import os, sys
os.environ['GARMINTOKENS'] = '/root/.garminconnect'

from mcp.server.fastmcp import FastMCP
app = FastMCP('test')
print("Settings fields:", list(app.settings.model_fields.keys()), file=sys.stderr)
PYEOF
