#!/bin/bash
set -e

# Escreve tokens antes de qualquer import Python
if [ -n "$GARMINTOKENS_BASE64" ]; then
    mkdir -p /root/.garminconnect
    printf '%s' "$GARMINTOKENS_BASE64" | base64 -d > /root/.garminconnect/garmin_tokens.json
    echo "Tokens escritos com sucesso" >&2
    cat /root/.garminconnect/garmin_tokens.json | head -c 50 >&2
    echo "" >&2
fi

# Define variável de ambiente ANTES de qualquer import
export GARMINTOKENS=/root/.garminconnect

exec python - << 'PYEOF'
import os
import sys

# Garante que tokenstore aponta para o lugar certo
os.environ['GARMINTOKENS'] = '/root/.garminconnect'

# Agora importa o módulo
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
application.run(transport='sse', port=port)
PYEOF
