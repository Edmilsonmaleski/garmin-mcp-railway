#!/bin/bash
set -e

echo "=== Iniciando setup ===" >&2

# Escreve token ANTES de qualquer import Python
if [ -n "$GARMINTOKENS_BASE64" ]; then
    mkdir -p /root/.garminconnect
    echo "$GARMINTOKENS_BASE64" | base64 -d > /root/.garminconnect/garmin_tokens.json
    echo "=== Token escrito: $(wc -c < /root/.garminconnect/garmin_tokens.json) bytes ===" >&2
else
    echo "=== ERRO: GARMINTOKENS_BASE64 não definida! ===" >&2
    exit 1
fi

export GARMINTOKENS=/root/.garminconnect

echo "=== Iniciando servidor Python ===" >&2

exec python << 'PYEOF'
import os
import sys

os.environ['GARMINTOKENS'] = '/root/.garminconnect'

# Verifica se o arquivo existe antes de importar
import json
token_path = '/root/.garminconnect/garmin_tokens.json'
if not os.path.exists(token_path):
    print(f"ERRO: Token não encontrado em {token_path}", file=sys.stderr)
    sys.exit(1)

print(f"Token encontrado: {os.path.getsize(token_path)} bytes", file=sys.stderr)

import garmin_mcp as gm
from mcp.server.fastmcp import FastMCP
from garmin_mcp import (activity_management, health_wellness, user_profile,
    devices, gear_management, weight_management, challenges, training,
    workouts, workout_templates, data_management, womens_health, nutrition,
    workout_builders, courses, activity_analysis)

garmin_client = gm.init_api(gm.email, gm.password)
if not garmin_client:
    sys.exit(1)

for mod in [activity_management, health_wellness, user_profile, devices,
            gear_management, weight_management, challenges, training, workouts,
            data_management, womens_health, nutrition, workout_builders,
            courses, activity_analysis]:
    mod.configure(garmin_client)

application = FastMCP('Garmin Connect v1.0')
for mod in [activity_management, health_wellness, user_profile, devices,
            gear_management, weight_management, challenges, training, workouts,
            data_management, womens_health, nutrition, workout_builders,
            courses, activity_analysis]:
    application = mod.register_tools(application)
application = workout_templates.register_resources(application)

port = int(os.environ.get('PORT', 8000))
print(f"Iniciando servidor SSE na porta {port}", file=sys.stderr)
application.run(transport='sse', port=port)
PYEOF
