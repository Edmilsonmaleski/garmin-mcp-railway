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
    def get_daily_timeseries(days: int = 180, start_date: str = "", end_date: str = "") -> dict:
        """Get raw daily sleep + activity data for charting.
        Args:
            days: how many recent days to include, used when start_date/end_date are not given (default 180)
            start_date: optional explicit range start, format YYYY-MM-DD
            end_date: optional explicit range end, format YYYY-MM-DD
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_query = """
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
        """
        if start_date and end_date:
            cur.execute(base_query + " WHERE s.date BETWEEN %s AND %s ORDER BY s.date", (start_date, end_date))
        else:
            cur.execute(base_query + " WHERE s.date >= (CURRENT_DATE - (%s || ' days')::interval) ORDER BY s.date", (days,))
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            r['date'] = r['date'].isoformat()
        return {"days": rows}

    @app.tool()
    def get_sleep_performance_correlation(days: int = 180, start_date: str = "", end_date: str = "") -> dict:
        """Get paired data of prior-night sleep vs same-day running performance (avg HR, pace), for correlation analysis.
        Args:
            days: lookback window, used when start_date/end_date are not given (default 180)
            start_date: optional explicit range start, format YYYY-MM-DD
            end_date: optional explicit range end, format YYYY-MM-DD
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_query = """
            SELECT s.date, s.sleep_hours, s.deep_sleep_pct, s.rem_sleep_pct, s.resting_hr,
                   a.distance_meters, a.duration_seconds, a.avg_hr_bpm, a.activity_type
            FROM daily_sleep s
            JOIN activities a ON a.date = s.date
        """
        if start_date and end_date:
            cur.execute(base_query + " WHERE s.date BETWEEN %s AND %s AND a.distance_meters IS NOT NULL AND a.duration_seconds IS NOT NULL ORDER BY s.date", (start_date, end_date))
        else:
            cur.execute(base_query + " WHERE s.date >= (CURRENT_DATE - (%s || ' days')::interval) AND a.distance_meters IS NOT NULL AND a.duration_seconds IS NOT NULL ORDER BY s.date", (days,))
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
                "distance_meters": float(r['distance_meters']) if r['distance_meters'] is not None else None,
                "duration_seconds": float(r['duration_seconds']) if r['duration_seconds'] is not None else None,
                "activity_type": r['activity_type'],
            })
        return {"pairs": result}

    @app.tool()
    def get_activities_raw(days: int = 540, start_date: str = "", end_date: str = "") -> dict:
        """Get individual (non-aggregated) activities with their type, for client-side filtering/aggregation.
        Args:
            days: how many recent days to include, used when start_date/end_date are not given (default 540)
            start_date: optional explicit range start, format YYYY-MM-DD
            end_date: optional explicit range end, format YYYY-MM-DD
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_query = """
            SELECT date, activity_type, name, distance_meters, duration_seconds, avg_hr_bpm, calories, steps, avg_cadence, max_cadence
            FROM activities
        """
        if start_date and end_date:
            cur.execute(base_query + " WHERE date BETWEEN %s AND %s ORDER BY date", (start_date, end_date))
        else:
            cur.execute(base_query + " WHERE date >= (CURRENT_DATE - (%s || ' days')::interval) ORDER BY date", (days,))
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            r['date'] = r['date'].isoformat()
            r['distance_meters'] = float(r['distance_meters']) if r['distance_meters'] is not None else None
            r['duration_seconds'] = float(r['duration_seconds']) if r['duration_seconds'] is not None else None
            r['avg_cadence'] = float(r['avg_cadence']) if r['avg_cadence'] is not None else None
            r['max_cadence'] = float(r['max_cadence']) if r['max_cadence'] is not None else None
        return {"activities": rows}

    @app.tool()
    def get_range_summary(start_date: str, end_date: str) -> dict:
        """Get aggregated KPIs (sleep, RHR, distance, activities, pace) for an arbitrary date range.
        Useful for comparing two custom periods (e.g. this month vs last month).
        Args:
            start_date: range start, format YYYY-MM-DD
            end_date: range end, format YYYY-MM-DD
        """
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                ROUND(AVG(sleep_hours)::numeric, 2) AS avg_sleep_hours,
                ROUND(AVG(resting_hr)::numeric, 1) AS avg_resting_hr,
                ROUND(AVG(deep_sleep_pct)::numeric, 1) AS avg_deep_pct,
                ROUND(AVG(rem_sleep_pct)::numeric, 1) AS avg_rem_pct,
                COUNT(*) AS days_with_data
            FROM daily_sleep
            WHERE date BETWEEN %s AND %s
        """, (start_date, end_date))
        sleep_row = cur.fetchone() or {}

        cur.execute("""
            SELECT
                ROUND((SUM(distance_meters)/1000)::numeric, 1) AS total_km,
                COUNT(*) AS num_activities,
                ROUND(AVG(avg_hr_bpm)::numeric, 1) AS avg_hr,
                SUM(distance_meters) AS total_distance_m,
                SUM(duration_seconds) AS total_duration_s
            FROM activities
            WHERE date BETWEEN %s AND %s
        """, (start_date, end_date))
        act_row = cur.fetchone() or {}
        conn.close()

        avg_pace = None
        if act_row.get('total_distance_m') and act_row.get('total_duration_s'):
            km = float(act_row['total_distance_m']) / 1000
            if km > 0:
                avg_pace = round((float(act_row['total_duration_s']) / 60) / km, 2)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "avg_sleep_hours": sleep_row.get('avg_sleep_hours'),
            "avg_resting_hr": sleep_row.get('avg_resting_hr'),
            "avg_deep_pct": sleep_row.get('avg_deep_pct'),
            "avg_rem_pct": sleep_row.get('avg_rem_pct'),
            "days_with_data": sleep_row.get('days_with_data'),
            "total_km": act_row.get('total_km'),
            "num_activities": act_row.get('num_activities'),
            "avg_hr": act_row.get('avg_hr'),
            "avg_pace_min_per_km": avg_pace,
        }

    return app
