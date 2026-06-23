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

port = int(os.environ.get('PORT', 8080))
host = '0.0.0.0'
print(f"Iniciando servidor SSE na porta {port}", file=sys.stderr)
os.environ['FASTMCP_PORT'] = str(port)
os.environ['FASTMCP_HOST'] = host
application.run(transport='sse')
PYEOF
