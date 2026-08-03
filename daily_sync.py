import os
from datetime import date, timedelta
import psycopg2
from garminconnect import Garmin

os.environ['GARMINTOKENS'] = '/root/.garminconnect'
tokenstore = '/root/.garminconnect'

print("Autenticando no Garmin...", flush=True)
try:
    garmin = Garmin(is_cn=False)
    garmin.login(tokenstore)
    print("Login via token OK", flush=True)
except Exception as e:
    print(f"Token falhou ({e}), tentando login completo...", flush=True)
    email = os.environ["GARMIN_EMAIL"]
    password = os.environ["GARMIN_PASSWORD"]
    garmin = Garmin(email=email, password=password, is_cn=False)
    garmin.login()
    garmin.client.dump(tokenstore)
    print("Login completo OK, token renovado", flush=True)

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()


def sync_day(d):
    ds = d.isoformat()

    sleep = garmin.get_sleep_data(ds)
    dto = (sleep or {}).get('dailySleepDTO', {}) or {}
    sleep_seconds = dto.get('sleepTimeSeconds')
    if sleep_seconds:
        deep = dto.get('deepSleepSeconds') or 0
        light = dto.get('lightSleepSeconds') or 0
        rem = dto.get('remSleepSeconds') or 0
        awake = dto.get('awakeSleepSeconds') or 0
        total = sleep_seconds or 1
        rhr = None
        try:
            stats = garmin.get_stats(ds)
            rhr = stats.get('restingHeartRate')
        except Exception:
            pass
        cur.execute("""
            INSERT INTO daily_sleep (date, sleep_hours, sleep_seconds, deep_sleep_pct, light_sleep_pct, rem_sleep_pct, awake_seconds, resting_hr)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (date) DO UPDATE SET
                sleep_hours=EXCLUDED.sleep_hours, sleep_seconds=EXCLUDED.sleep_seconds,
                deep_sleep_pct=EXCLUDED.deep_sleep_pct, light_sleep_pct=EXCLUDED.light_sleep_pct,
                rem_sleep_pct=EXCLUDED.rem_sleep_pct, awake_seconds=EXCLUDED.awake_seconds,
                resting_hr=EXCLUDED.resting_hr
        """, (ds, round(sleep_seconds/3600,2), sleep_seconds, round(deep/total*100,2), round(light/total*100,2), round(rem/total*100,2), awake, rhr))
        conn.commit()
        print(f"{ds}: sono OK ({sleep_seconds/3600:.1f}h, rhr={rhr})", flush=True)
    else:
        print(f"{ds}: sem dado de sono", flush=True)

    try:
        acts = garmin.get_activities_by_date(ds, ds, "running")
    except Exception as e:
        print(f"Erro atividades {ds}: {e}", flush=True)
        acts = []

    for a in acts or []:
        cur.execute("""
            INSERT INTO activities (activity_id, date, name, activity_type, start_time, distance_meters, duration_seconds, calories, avg_hr_bpm, max_hr_bpm, steps, elevation_gain_meters, elevation_loss_meters)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (activity_id) DO UPDATE SET
                distance_meters=EXCLUDED.distance_meters, duration_seconds=EXCLUDED.duration_seconds,
                calories=EXCLUDED.calories, avg_hr_bpm=EXCLUDED.avg_hr_bpm, max_hr_bpm=EXCLUDED.max_hr_bpm,
                steps=EXCLUDED.steps, elevation_gain_meters=EXCLUDED.elevation_gain_meters,
                elevation_loss_meters=EXCLUDED.elevation_loss_meters
        """, (
            a.get('activityId'), ds, a.get('activityName'),
            a.get('activityType', {}).get('typeKey'), a.get('startTimeLocal'),
            a.get('distance'), a.get('duration'), a.get('calories'),
            a.get('averageHR'), a.get('maxHR'), a.get('steps'),
            a.get('elevationGain'), a.get('elevationLoss')
        ))
    conn.commit()
    print(f"{ds}: FIM ({len(acts or [])} atividades)", flush=True)


# Sincroniza hoje (dados disponiveis ate o horario do cron) e ontem
# (reforco, caso o Garmin publique algo com atraso).
for offset in [1, 0]:
    sync_day(date.today() - timedelta(days=offset))

conn.close()
print("Sync completo.", flush=True)
