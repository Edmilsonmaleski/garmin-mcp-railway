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

port = int(os.environ.get('PORT', 8080))

# Inspeciona transport_security antes de modificar
from mcp.server.fastmcp import FastMCP
application = FastMCP('Garmin Connect v1.0')
application.settings.host = '0.0.0.0'
application.settings.port = port
print(f"transport_security type: {type(application.settings.transport_security)}", file=sys.stderr)
print(f"transport_security value: {application.settings.transport_security}", file=sys.stderr)
print(f"transport_security fields: {list(application.settings.transport_security.model_fields.keys()) if hasattr(application.settings.transport_security, 'model_fields') else 'N/A'}", file=sys.stderr)
PYEOF
