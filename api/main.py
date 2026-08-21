"""
API REST publica (somente leitura) para o dashboard estatico no GitHub Pages.
Espelha as mesmas consultas do dashboard.py (MCP), mas como endpoints HTTP simples.
Sem autenticacao por escolha do usuario (dados nao sensiveis, uso pessoal).
"""
import os
from decimal import Decimal
from datetime import date, datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


def get_db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def clean_row(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/daily-timeseries")
def daily_timeseries():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT s.date, s.sleep_hours, s.resting_hr, s.deep_sleep_pct, s.rem_sleep_pct, s.vo2max,
               s.readiness_level, s.readiness_score, s.readiness_sleep_score, s.readiness_recovery_hours,
               s.readiness_acute_load, s.readiness_hrv_weekly_avg,
               s.pred_5k_seconds, s.pred_10k_seconds, s.pred_half_seconds, s.pred_marathon_seconds,
               COALESCE(a.total_km, 0) AS distance_km,
               a.avg_hr_bpm
        FROM daily_sleep s
        LEFT JOIN (
            SELECT date, SUM(distance_meters)/1000 AS total_km, AVG(avg_hr_bpm) AS avg_hr_bpm
            FROM activities GROUP BY date
        ) a ON a.date = s.date
        WHERE s.date BETWEEN %s AND %s
        ORDER BY s.date
        """,
        (start_date, end_date),
    )
    rows = [clean_row(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"days": rows})


@app.get("/api/sleep-performance-correlation")
def sleep_performance_correlation():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT s.date, s.sleep_hours, s.deep_sleep_pct, s.rem_sleep_pct, s.resting_hr,
               a.distance_meters, a.duration_seconds, a.avg_hr_bpm, a.activity_type
        FROM daily_sleep s
        JOIN activities a ON a.date = s.date
        WHERE s.date BETWEEN %s AND %s
              AND a.distance_meters IS NOT NULL AND a.duration_seconds IS NOT NULL
        ORDER BY s.date
        """,
        (start_date, end_date),
    )
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        pace_min_km = None
        if r["distance_meters"] and r["duration_seconds"]:
            km = float(r["distance_meters"]) / 1000
            if km > 0:
                pace_min_km = round((float(r["duration_seconds"]) / 60) / km, 2)
        result.append(
            {
                "date": r["date"].isoformat(),
                "sleep_hours": float(r["sleep_hours"]) if r["sleep_hours"] is not None else None,
                "deep_sleep_pct": float(r["deep_sleep_pct"]) if r["deep_sleep_pct"] is not None else None,
                "rem_sleep_pct": float(r["rem_sleep_pct"]) if r["rem_sleep_pct"] is not None else None,
                "resting_hr": r["resting_hr"],
                "avg_hr_bpm": r["avg_hr_bpm"],
                "pace_min_per_km": pace_min_km,
                "distance_meters": float(r["distance_meters"]) if r["distance_meters"] is not None else None,
                "duration_seconds": float(r["duration_seconds"]) if r["duration_seconds"] is not None else None,
                "activity_type": r["activity_type"],
            }
        )
    return jsonify({"pairs": result})


@app.get("/api/activities-raw")
def activities_raw():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT date, activity_type, name, distance_meters, duration_seconds, avg_hr_bpm, calories, steps, avg_cadence, max_cadence
        FROM activities
        WHERE date BETWEEN %s AND %s
        ORDER BY date
        """,
        (start_date, end_date),
    )
    rows = [clean_row(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"activities": rows})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
