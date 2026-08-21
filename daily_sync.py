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
    is_today = (d == date.today())

    sleep = garmin.get_sleep_data(ds)
    dto = (sleep or {}).get('dailySleepDTO', {}) or {}
    sleep_seconds = dto.get('sleepTimeSeconds')

    rhr = None
    try:
        stats = garmin.get_stats(ds)
        rhr = stats.get('restingHeartRate')
    except Exception:
        pass

    vo2max = None
    try:
        mm = garmin.get_max_metrics(ds)
        if mm:
            generic = (mm[0] or {}).get('generic') or {}
            vo2max = generic.get('vo2MaxValue')
    except Exception:
        pass

    # Training Readiness (usa a leitura da manha, logo apos acordar)
    readiness_level = readiness_score = readiness_sleep_score = None
    readiness_recovery_hours = readiness_acute_load = readiness_hrv_weekly_avg = None
    try:
        tr_list = garmin.get_training_readiness(ds)
        tr = None
        if tr_list:
            tr = next((t for t in tr_list if t.get('inputContext') == 'AFTER_WAKEUP_RESET'), tr_list[0])
        if tr:
            readiness_level = tr.get('level')
            readiness_score = tr.get('score')
            readiness_sleep_score = tr.get('sleepScore')
            recovery_min = tr.get('recoveryTime')
            readiness_recovery_hours = round(recovery_min / 60, 1) if recovery_min else None
            readiness_acute_load = tr.get('acuteLoad')
            readiness_hrv_weekly_avg = tr.get('hrvWeeklyAverage')
    except Exception as e:
        print(f"{ds}: sem training readiness ({e})", flush=True)

    # Previsao de provas (nao e por data, so faz sentido gravar no snapshot de hoje)
    pred_5k = pred_10k = pred_half = pred_marathon = None
    if is_today:
        try:
            rp = garmin.get_race_predictions()
            if rp:
                pred_5k = rp.get('time5K')
                pred_10k = rp.get('time10K')
                pred_half = rp.get('timeHalfMarathon')
                pred_marathon = rp.get('timeMarathon')
        except Exception as e:
            print(f"{ds}: sem previsao de prova ({e})", flush=True)

    if sleep_seconds:
        deep = dto.get('deepSleepSeconds') or 0
        light = dto.get('lightSleepSeconds') or 0
        rem = dto.get('remSleepSeconds') or 0
        awake = dto.get('awakeSleepSeconds') or 0
        total = sleep_seconds or 1
        cur.execute("""
            INSERT INTO daily_sleep (date, sleep_hours, sleep_seconds, deep_sleep_pct, light_sleep_pct, rem_sleep_pct, awake_seconds, resting_hr, vo2max,
                readiness_level, readiness_score, readiness_sleep_score, readiness_recovery_hours, readiness_acute_load, readiness_hrv_weekly_avg,
                pred_5k_seconds, pred_10k_seconds, pred_half_seconds, pred_marathon_seconds)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (date) DO UPDATE SET
                sleep_hours=EXCLUDED.sleep_hours, sleep_seconds=EXCLUDED.sleep_seconds,
                deep_sleep_pct=EXCLUDED.deep_sleep_pct, light_sleep_pct=EXCLUDED.light_sleep_pct,
                rem_sleep_pct=EXCLUDED.rem_sleep_pct, awake_seconds=EXCLUDED.awake_seconds,
                resting_hr=EXCLUDED.resting_hr, vo2max=EXCLUDED.vo2max,
                readiness_level=EXCLUDED.readiness_level, readiness_score=EXCLUDED.readiness_score,
                readiness_sleep_score=EXCLUDED.readiness_sleep_score, readiness_recovery_hours=EXCLUDED.readiness_recovery_hours,
                readiness_acute_load=EXCLUDED.readiness_acute_load, readiness_hrv_weekly_avg=EXCLUDED.readiness_hrv_weekly_avg,
                pred_5k_seconds=COALESCE(EXCLUDED.pred_5k_seconds, daily_sleep.pred_5k_seconds),
                pred_10k_seconds=COALESCE(EXCLUDED.pred_10k_seconds, daily_sleep.pred_10k_seconds),
                pred_half_seconds=COALESCE(EXCLUDED.pred_half_seconds, daily_sleep.pred_half_seconds),
                pred_marathon_seconds=COALESCE(EXCLUDED.pred_marathon_seconds, daily_sleep.pred_marathon_seconds)
        """, (ds, round(sleep_seconds/3600,2), sleep_seconds, round(deep/total*100,2), round(light/total*100,2), round(rem/total*100,2), awake, rhr, vo2max,
              readiness_level, readiness_score, readiness_sleep_score, readiness_recovery_hours, readiness_acute_load, readiness_hrv_weekly_avg,
              pred_5k, pred_10k, pred_half, pred_marathon))
        conn.commit()
        print(f"{ds}: sono OK ({sleep_seconds/3600:.1f}h, rhr={rhr}, readiness={readiness_level})", flush=True)
    else:
        if readiness_level or pred_marathon:
            cur.execute("""
                INSERT INTO daily_sleep (date, readiness_level, readiness_score, readiness_sleep_score, readiness_recovery_hours,
                    readiness_acute_load, readiness_hrv_weekly_avg, pred_5k_seconds, pred_10k_seconds, pred_half_seconds, pred_marathon_seconds)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (date) DO UPDATE SET
                    readiness_level=EXCLUDED.readiness_level, readiness_score=EXCLUDED.readiness_score,
                    readiness_sleep_score=EXCLUDED.readiness_sleep_score, readiness_recovery_hours=EXCLUDED.readiness_recovery_hours,
                    readiness_acute_load=EXCLUDED.readiness_acute_load, readiness_hrv_weekly_avg=EXCLUDED.readiness_hrv_weekly_avg,
                    pred_5k_seconds=COALESCE(EXCLUDED.pred_5k_seconds, daily_sleep.pred_5k_seconds),
                    pred_10k_seconds=COALESCE(EXCLUDED.pred_10k_seconds, daily_sleep.pred_10k_seconds),
                    pred_half_seconds=COALESCE(EXCLUDED.pred_half_seconds, daily_sleep.pred_half_seconds),
                    pred_marathon_seconds=COALESCE(EXCLUDED.pred_marathon_seconds, daily_sleep.pred_marathon_seconds)
            """, (ds, readiness_level, readiness_score, readiness_sleep_score, readiness_recovery_hours,
                  readiness_acute_load, readiness_hrv_weekly_avg, pred_5k, pred_10k, pred_half, pred_marathon))
            conn.commit()
        print(f"{ds}: sem dado de sono", flush=True)

    try:
        acts = garmin.get_activities_by_date(ds, ds)
    except Exception as e:
        print(f"Erro atividades {ds}: {e}", flush=True)
        acts = []

    for a in acts or []:
        avg_cadence = a.get('averageRunningCadenceInStepsPerMinute')
        max_cadence = a.get('maxRunningCadenceInStepsPerMinute')
        cur.execute("""
            INSERT INTO activities (activity_id, date, name, activity_type, start_time, distance_meters, duration_seconds, calories, avg_hr_bpm, max_hr_bpm, steps, elevation_gain_meters, elevation_loss_meters, avg_cadence, max_cadence)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (activity_id) DO UPDATE SET
                distance_meters=EXCLUDED.distance_meters, duration_seconds=EXCLUDED.duration_seconds,
                calories=EXCLUDED.calories, avg_hr_bpm=EXCLUDED.avg_hr_bpm, max_hr_bpm=EXCLUDED.max_hr_bpm,
                steps=EXCLUDED.steps, elevation_gain_meters=EXCLUDED.elevation_gain_meters,
                elevation_loss_meters=EXCLUDED.elevation_loss_meters,
                avg_cadence=EXCLUDED.avg_cadence, max_cadence=EXCLUDED.max_cadence
        """, (
            a.get('activityId'), ds, a.get('activityName'),
            a.get('activityType', {}).get('typeKey'), a.get('startTimeLocal'),
            a.get('distance'), a.get('duration'), a.get('calories'),
            a.get('averageHR'), a.get('maxHR'), a.get('steps'),
            a.get('elevationGain'), a.get('elevationLoss'),
            avg_cadence, max_cadence
        ))
    conn.commit()
    print(f"{ds}: FIM ({len(acts or [])} atividades)", flush=True)


# Sincroniza hoje (dados disponiveis ate o horario do cron) e ontem
# (reforco, caso o Garmin publique algo com atraso).
for offset in [1, 0]:
    sync_day(date.today() - timedelta(days=offset))

conn.close()
print("Sync completo.", flush=True)
