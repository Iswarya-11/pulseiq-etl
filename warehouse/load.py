
import os
import glob
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


RAW = "/app/raw"

MASTER = os.path.join(RAW, "01_LedgerForge_Python_Master_Dataset.xlsx")
CORTEX = os.path.join(RAW, "02_CortexHR_AI_ML_Dataset.xlsx")
STAR = os.path.join(RAW, "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx")


def clean(value):
    """Convert pandas/numpy values into PostgreSQL-compatible values."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, pd.Timestamp):
        return value.date()

    if hasattr(value, "item"):
        value = value.item()

    return value


def truth(value):
    """Convert common Y/N and boolean values to Python booleans."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    value = str(value).strip().upper()

    if value in ("Y", "YES", "TRUE", "1"):
        return True
    if value in ("N", "NO", "FALSE", "0"):
        return False

    return None


def records(df, columns):
    """Return cleaned tuples in the specified column order."""
    return [
        tuple(clean(row[column]) for column in columns)
        for _, row in df.iterrows()
    ]


def upsert(cur, table, columns, rows, conflict, updates):
    """Insert rows and update existing rows without creating duplicates."""
    if not rows:
        return

    names = ", ".join(columns)
    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in updates
    )

    sql = f"""
        INSERT INTO {table} ({names})
        VALUES %s
        ON CONFLICT ({conflict})
        DO UPDATE SET {update_sql}
    """

    execute_values(cur, sql, rows, page_size=500)


def date_key_map(cur):
    cur.execute("SELECT full_date, date_key FROM dw.dim_date")
    return {row[0]: row[1] for row in cur.fetchall()}


def employee_key_for(cur, employee_id, on_date):
    """Find the employee version valid on the requested date."""
    cur.execute(
        """
        SELECT employee_key
        FROM dw.dim_employee
        WHERE employee_id = %s
          AND valid_from <= %s
          AND (valid_to IS NULL OR valid_to >= %s)
        ORDER BY valid_from DESC
        LIMIT 1
        """,
        (employee_id, on_date, on_date),
    )
    result = cur.fetchone()
    return result[0] if result else None


def load_dimensions(cur):
    print("Loading dimensions...")

    # Department dimension: use the star-schema reference.
    departments = pd.read_excel(STAR, sheet_name="dim_department")
    departments = departments[
        [
            "department_id", "department_name", "cost_center",
            "description", "is_leadership"
        ]
    ].copy()
    departments["is_leadership"] = departments["is_leadership"].map(truth)

    upsert(
        cur,
        "dw.dim_department",
        [
            "department_id", "department_name", "cost_center",
            "description", "is_leadership"
        ],
        records(departments, [
            "department_id", "department_name", "cost_center",
            "description", "is_leadership"
        ]),
        "department_id",
        [
            "department_name", "cost_center", "description",
            "is_leadership"
        ],
    )

    # Role dimension.
    roles = pd.read_excel(STAR, sheet_name="dim_role")
    roles = roles.rename(columns={"band_reference_year": "band_reference_year"})
    role_columns = [
        "role_id", "department_id", "role_title", "level", "grade",
        "band_min_annual", "band_mid_annual", "band_max_annual",
        "overtime_eligible", "band_reference_year"
    ]
    roles["overtime_eligible"] = roles["overtime_eligible"].map(truth)

    upsert(
        cur,
        "dw.dim_role",
        role_columns,
        records(roles, role_columns),
        "role_id",
        role_columns[1:],
    )

    # Date dimension.
    dates = pd.read_excel(STAR, sheet_name="dim_date")
    dates = dates.rename(columns={"date": "full_date"})

    for column in ["is_weekend", "is_holiday", "is_working_day", "is_month_end"]:
        dates[column] = dates[column].map(truth)

    date_columns = [
        "date_key", "full_date", "year", "quarter", "month_number",
        "month_name", "year_month", "week_of_year", "day_of_week",
        "is_weekend", "is_holiday", "is_working_day", "financial_year",
        "fiscal_quarter", "fiscal_month_number", "is_month_end",
        "month_start_date", "month_end_date"
    ]

    upsert(
        cur,
        "dw.dim_date",
        date_columns,
        records(dates, date_columns),
        "date_key",
        date_columns[1:],
    )

    # Leave type dimension.
    leave_types = pd.read_excel(MASTER, sheet_name="leave_types")
    for column in ["prorated_for_joiners", "carry_forward_allowed"]:
        leave_types[column] = leave_types[column].map(truth)

    leave_columns = [
        "leave_type_code", "leave_type_name", "pay_type",
        "annual_quota_days", "prorated_for_joiners",
        "carry_forward_allowed", "max_carry_forward_days", "policy_note"
    ]

    upsert(
        cur,
        "dw.dim_leave_type",
        leave_columns,
        records(leave_types, leave_columns),
        "leave_type_code",
        leave_columns[1:],
    )

    # Employee dimension: one row per assignment version.
    employees = pd.read_excel(MASTER, sheet_name="employees")
    assignments = pd.read_excel(MASTER, sheet_name="employee_assignments")

    employee_columns = [
        "employee_id", "full_name", "gender", "date_of_birth",
        "hire_date", "exit_date", "employment_status", "employment_type",
        "department_id", "role_id", "manager_id", "work_location",
        "work_mode", "highest_education"
    ]

    employee_lookup = employees.set_index("employee_id")
    employee_rows = []

    for _, assignment in assignments.iterrows():
        employee_id = assignment["employee_id"]

        if employee_id not in employee_lookup.index:
            continue

        employee = employee_lookup.loc[employee_id]
        effective_from = clean(assignment["effective_from"])
        effective_to = clean(assignment["effective_to"])

        values = {
            "employee_id": employee_id,
            "full_name": employee["full_name"],
            "gender": employee["gender"],
            "date_of_birth": employee["date_of_birth"],
            "hire_date": employee["hire_date"],
            "exit_date": employee["exit_date"],
            "employment_status": employee["employment_status"],
            "employment_type": employee["employment_type"],
            "department_id": assignment["department_id"],
            "role_id": assignment["role_id"],
            "manager_id": assignment["manager_id"],
            "work_location": employee["work_location"],
            "work_mode": employee["work_mode"],
            "highest_education": employee["highest_education"],
            "valid_from": effective_from,
            "valid_to": effective_to,
            "is_current": effective_to is None,
            "change_reason": assignment["change_reason"],
        }

        employee_rows.append(
            tuple(clean(values[column]) for column in employee_columns)
            + (
                effective_from,
                effective_to,
                effective_to is None,
                clean(assignment["change_reason"]),
            )
        )

    employee_insert_columns = employee_columns + [
        "valid_from", "valid_to", "is_current", "change_reason"
    ]

    upsert(
        cur,
        "dw.dim_employee",
        employee_insert_columns,
        employee_rows,
        "employee_id, valid_from",
        employee_columns[1:] + ["valid_to", "is_current", "change_reason"],
    )

    print("Dimensions loaded.")


def load_attendance(cur):
    print("Loading monthly attendance...")

    df = pd.read_excel(
        CORTEX, sheet_name="attendance_monthly_features"
    )

    keys = date_key_map(cur)
    rows = []

    for _, row in df.iterrows():
        month = clean(row["month"])
        period_end = pd.Timestamp(month) + pd.offsets.MonthEnd(0)
        period_end = period_end.date()

        employee_key = employee_key_for(
            cur, row["employee_id"], period_end
        )

        rows.append((
            clean(row["employee_id"]),
            employee_key,
            keys.get(period_end),
            period_end,
            clean(row["department_id"]),
            clean(row["scheduled_days"]),
            clean(row["present_days"]),
            clean(row["wfh_days"]),
            clean(row["half_days_unpaid"]),
            clean(row["paid_leave_days"]),
            clean(row["unpaid_absence_days"]),
            clean(row["late_arrivals"]),
            clean(row["avg_hours_worked"]),
            clean(row["overtime_hours"]),
            clean(row["attendance_rate"]),
        ))

    columns = [
        "employee_id", "employee_key", "date_key", "period_end_date",
        "department_id", "scheduled_days", "present_days", "wfh_days",
        "half_days_unpaid", "paid_leave_days", "unpaid_absence_days",
        "late_arrivals", "avg_hours_worked", "overtime_hours",
        "attendance_rate"
    ]

    upsert(
        cur, "dw.fact_attendance_monthly", columns, rows,
        "employee_id, period_end_date", columns[1:]
    )

    print(f"Attendance rows processed: {len(rows)}")


def load_payroll(cur):
    print("Loading payroll...")

    df = pd.read_excel(MASTER, sheet_name="payroll_items")
    keys = date_key_map(cur)
    rows = []

    numeric_columns = [
        "payable_days", "lop_days", "overtime_hours_paid",
        "monthly_fixed_gross", "basic", "hra", "conveyance", "medical",
        "special_allowance", "earned_fixed_pay", "overtime_pay",
        "variable_pay", "gross_pay", "pf_employee", "esi_employee",
        "professional_tax", "tds", "other_deductions",
        "total_deductions", "net_pay", "pf_employer", "esi_employer",
        "employer_cost"
    ]

    for _, row in df.iterrows():
        period_start = clean(row["period_start"])
        period_end = clean(row["period_end"])
        employee_key = employee_key_for(
            cur, row["employee_id"], period_end
        )

        rows.append((
            clean(row["payroll_item_id"]),
            clean(row["run_id"]),
            clean(row["employee_id"]),
            employee_key,
            keys.get(period_end),
            period_start,
            period_end,
            clean(row["department_id"]),
            clean(row["role_id"]),
            *[clean(row[column]) for column in numeric_columns[:3]],
            *[clean(row[column]) for column in numeric_columns[3:]],
            clean(row.get("headcount_flag")),
        ))

    columns = [
        "payroll_item_id", "run_id", "employee_id", "employee_key",
        "date_key", "period_start", "period_end_date", "department_id",
        "role_id", "payable_days", "lop_days", "overtime_hours_paid",
        "monthly_fixed_gross", "basic", "hra", "conveyance", "medical",
        "special_allowance", "earned_fixed_pay", "overtime_pay",
        "variable_pay", "gross_pay", "pf_employee", "esi_employee",
        "professional_tax", "tds", "other_deductions", "total_deductions",
        "net_pay", "pf_employer", "esi_employer", "employer_cost",
        "headcount_flag"
    ]

    # headcount_flag is optional in the source workbook.
    upsert(
        cur, "dw.fact_payroll", columns, rows,
        "payroll_item_id", columns[1:]
    )

    print(f"Payroll rows processed: {len(rows)}")


def load_leave(cur):
    print("Loading leave requests...")

    df = pd.read_excel(MASTER, sheet_name="leave_requests")
    keys = date_key_map(cur)
    rows = []

    for _, row in df.iterrows():
        start_date = clean(row["start_date"])
        end_date = clean(row["end_date"])

        rows.append((
            clean(row["leave_request_id"]),
            clean(row["employee_id"]),
            employee_key_for(cur, row["employee_id"], start_date),
            clean(row["leave_type_code"]),
            keys.get(start_date),
            keys.get(end_date),
            start_date,
            end_date,
            clean(row["days"]),
            clean(row["status"]),
            clean(row["applied_on"]),
            clean(row["decided_on"]),
            clean(row["approver_id"]),
            clean(row["reason"]),
        ))

    columns = [
        "leave_request_id", "employee_id", "employee_key",
        "leave_type_code", "start_date_key", "end_date_key",
        "start_date", "end_date", "days", "status", "applied_on",
        "decided_on", "approver_id", "reason"
    ]

    upsert(
        cur, "dw.fact_leave", columns, rows,
        "leave_request_id", columns[1:]
    )

    print(f"Leave rows processed: {len(rows)}")


def load_headcount(cur):
    print("Loading monthly headcount...")

    df = pd.read_excel(CORTEX, sheet_name="monthly_headcount_history")

    # The ALL row is a company-wide total, not a department.
    df = df[df["department_id"] != "ALL"].copy()
    keys = date_key_map(cur)
    rows = []

    for _, row in df.iterrows():
        month = clean(row["month"])
        month_start = pd.Timestamp(month).date()
        date_key = keys.get(month_start)

        rows.append((
            date_key,
            month_start,
            clean(row["department_id"]),
            clean(row["headcount_start"]),
            clean(row["hires"]),
            clean(row["exits"]),
            clean(row["voluntary_exits"]),
            clean(row["transfers_in"]),
            clean(row["transfers_out"]),
            clean(row["headcount_end"]),
            clean(row["attrition_rate_monthly_pct"]),
        ))

    columns = [
        "date_key", "month_start_date", "department_id",
        "headcount_start", "hires", "exits", "voluntary_exits",
        "transfers_in", "transfers_out", "headcount_end",
        "attrition_rate_monthly_pct"
    ]

    upsert(
        cur, "dw.fact_headcount_monthly", columns, rows,
        "month_start_date, department_id", columns[2:]
    )

    print(f"Headcount rows processed: {len(rows)}")


def main():
    if not all(os.path.exists(path) for path in [MASTER, CORTEX, STAR]):
        raise FileNotFoundError(
            "One or more required Excel workbooks are missing from /app/raw."
        )

    connection = psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "pulseiq"),
        user=os.getenv("POSTGRES_USER", "pulseiq"),
        password=os.getenv("POSTGRES_PASSWORD", "pulseiq_dev_password"),
    )

    try:
        with connection:
            with connection.cursor() as cur:
                load_dimensions(cur)
                load_attendance(cur)
                load_payroll(cur)
                load_leave(cur)
                load_headcount(cur)

                cur.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM dw.dim_employee),
                        (SELECT COUNT(*) FROM dw.fact_attendance_monthly),
                        (SELECT COUNT(*) FROM dw.fact_payroll),
                        (SELECT COUNT(*) FROM dw.fact_leave),
                        (SELECT COUNT(*) FROM dw.fact_headcount_monthly)
                """)
                print("Warehouse row counts:", cur.fetchone())

        print("Warehouse load completed successfully.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
