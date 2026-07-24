"""
Dashboard aggregation tools - queries Postgres for historical trends.
"""
import os
import psycopg2
import psycopg2.extras


def get_db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def register_tools(app):

    @app.tool()
    def get_monthly_trends(months: int = 6) -> dict:
        """Get monthly aggregated trends: total distance, avg sleep, avg RHR, avg deep/REM sleep %, activity count.
        Args:
            months: how many recent months to include (default 6)
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                to_char(date_trunc('month', date), 'YYYY-MM') AS month,
                ROUND(AVG(sleep_hours)::numeric, 2) AS avg_sleep_hours,
                ROUND(AVG(resting_hr)::numeric, 1) AS avg_resting_hr,
                ROUND(AVG(deep_sleep_pct)::numeric, 1) AS avg_deep_pct,
                ROUND(AVG(rem_sleep_pct)::numeric, 1) AS avg_rem_pct,
                COUNT(*) AS days_with_data
            FROM daily_sleep
            WHERE date >= (CURRENT_DATE - (%s || ' months')::interval)
            GROUP BY 1 ORDER BY 1
        """, (months,))
        sleep_rows = cur.fetchall()

        cur.execute("""
            SELECT
                to_char(date_trunc('month', date), 'YYYY-MM') AS month,
                ROUND((SUM(distance_meters)/1000)::numeric, 1) AS total_km,
                COUNT(*) AS num_activities,
                ROUND(AVG(avg_hr_bpm)::numeric, 1) AS avg_hr
            FROM activities
            WHERE date >= (CURRENT_DATE - (%s || ' months')::interval)
            GROUP BY 1 ORDER BY 1
        """, (months,))
        activity_rows = cur.fetchall()
        conn.close()

        merged = {}
        for r in sleep_rows:
            merged[r['month']] = dict(r)
        for r in activity_rows:
            merged.setdefault(r['month'], {'month': r['month']}).update(r)

        return {"months": list(merged.values())}

    @app.tool()
    def get_daily_timeseries(days: int = 180) -> dict:
        """Get raw daily sleep + activity data for charting, most recent N days.
        Args:
            days: how many recent days to include (default 180)
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT s.date, s.sleep_hours, s.resting_hr, s.deep_sleep_pct, s.rem_sleep_pct,
                   COALESCE(a.total_km, 0) AS distance_km,
                   a.avg_hr_bpm
            FROM daily_sleep s
            LEFT JOIN (
                SELECT date, SUM(distance_meters)/1000 AS total_km, AVG(avg_hr_bpm) AS avg_hr_bpm
                FROM activities GROUP BY date
            ) a ON a.date = s.date
            WHERE s.date >= (CURRENT_DATE - (%s || ' days')::interval)
            ORDER BY s.date
        """, (days,))
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            r['date'] = r['date'].isoformat()
        return {"days": rows}

    @app.tool()
    def get_sleep_performance_correlation(days: int = 180) -> dict:
        """Get paired data of prior-night sleep vs same-day running performance (avg HR, pace),
        for correlation analysis. Args: days: lookback window (default 180)
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT s.date, s.sleep_hours, s.deep_sleep_pct, s.rem_sleep_pct, s.resting_hr,
                   a.distance_meters, a.duration_seconds, a.avg_hr_bpm
            FROM daily_sleep s
            JOIN activities a ON a.date = s.date
            WHERE s.date >= (CURRENT_DATE - (%s || ' days')::interval)
              AND a.distance_meters IS NOT NULL AND a.duration_seconds IS NOT NULL
            ORDER BY s.date
        """, (days,))
        rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            pace_min_km = None
            if r['distance_meters'] and r['duration_seconds']:
                km = r['distance_meters'] / 1000
                if km > 0:
                    pace_min_km = round((r['duration_seconds'] / 60) / km, 2)
            result.append({
                "date": r['date'].isoformat(),
                "sleep_hours": float(r['sleep_hours']) if r['sleep_hours'] is not None else None,
                "deep_sleep_pct": float(r['deep_sleep_pct']) if r['deep_sleep_pct'] is not None else None,
                "rem_sleep_pct": float(r['rem_sleep_pct']) if r['rem_sleep_pct'] is not None else None,
                "resting_hr": r['resting_hr'],
                "avg_hr_bpm": r['avg_hr_bpm'],
                "pace_min_per_km": pace_min_km,
            })
        return {"pairs": result}

    return app
