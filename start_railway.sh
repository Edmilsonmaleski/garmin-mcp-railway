#!/bin/bash
set -e

# Escreve token base64 para arquivo se variável existir
if [ -n "$GARMINTOKENS_BASE64" ]; then
    mkdir -p /root/.garminconnect
    echo "$GARMINTOKENS_BASE64" | base64 -d > /root/.garminconnect/garmin_tokens.json
    echo "Tokens escritos com sucesso." >&2
fi

# Inicia o servidor em modo SSE na porta do Railway
exec python -c "
from garmin_mcp import main, app
import os

# Re-run main but with SSE transport
from garmin_mcp import *
import garmin_mcp as gm

# Initialize and run with SSE
garmin_client = gm.init_api(gm.email, gm.password)
if not garmin_client:
    exit(1)

from mcp.server.fastmcp import FastMCP
from garmin_mcp import activity_management, health_wellness, user_profile, devices, gear_management, weight_management, challenges, training, workouts, workout_templates, data_management, womens_health, nutrition, workout_builders, courses, activity_analysis

for mod in [activity_management, health_wellness, user_profile, devices, gear_management, weight_management, challenges, training, workouts, data_management, womens_health, nutrition, workout_builders, courses, activity_analysis]:
    mod.configure(garmin_client)

application = FastMCP('Garmin Connect v1.0')
for mod in [activity_management, health_wellness, user_profile, devices, gear_management, weight_management, challenges, training, workouts, data_management, womens_health, nutrition, workout_builders, courses, activity_analysis]:
    application = mod.register_tools(application)
application = workout_templates.register_resources(application)

port = int(os.environ.get('PORT', 8000))
application.run(transport='sse', port=port)
"
