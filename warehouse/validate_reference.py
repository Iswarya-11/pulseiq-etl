
import pandas as pd
import psycopg2

REFERENCE_FILE = (
    "/app/raw/03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)
MASTER_FILE = (
    "/app/raw/01_LedgerForge_Python_Master_Dataset.xlsx"
)

conn = psycopg2.connect(
    host="db",
    port=5432,
    dbname="pulseiq",
    user="pulseiq",
    password="pulseiq_dev_password",
)

try:
    reference = pd.read_excel(
        REFERENCE_FILE,
        sheet_name="reference_summary_dept_month",
    )
    reference["month"] = (
        pd.to_datetime(reference["month"]).dt.to_period("M")
    )

    # 1. PAYROLL VALIDATION
    payroll = pd.read_sql_query(
        """
        SELECT
            department_id,
            DATE_TRUNC('month', period_start)::date AS month,
            ROUND(SUM(employer_cost)::numeric, 2) AS employer_cost,
            ROUND(SUM(gross_pay)::numeric, 2) AS gross_pay,
            ROUND(SUM(overtime_pay)::numeric, 2) AS overtime_pay,
            COUNT(DISTINCT employee_id) AS employees_paid,
            ROUND(SUM(overtime_hours_paid)::numeric, 2)
                AS overtime_hours
        FROM dw.fact_payroll
        GROUP BY
            department_id,
            DATE_TRUNC('month', period_start)::date
        """,
        conn,
    )
    payroll["month"] = (
        pd.to_datetime(payroll["month"]).dt.to_period("M")
    )

    # 2. ATTENDANCE VALIDATION
    # Calculate attendance from daily master records.
    # This allows comparison with the reference summary's
    # daily-record-based attendance calculations.
    daily = pd.read_excel(
        MASTER_FILE,
        sheet_name="attendance",
    )

    daily["month"] = (
        pd.to_datetime(daily["attendance_date"]).dt.to_period("M")
    )

    daily["_late"] = daily["late_flag"].eq("Y").astype(int)

    daily["_attendance_credit"] = daily["status"].map({
        "PRESENT": 1.0,
        "WFH": 1.0,
        "HALF_DAY_UNPAID": 0.5,
    }).fillna(0.0)

    attendance = (
        daily.groupby(["department_id", "month"])
        .agg(
            late_arrivals=("_late", "sum"),
            attendance_credit=("_attendance_credit", "sum"),
            total_records=("attendance_id", "count"),
        )
        .reset_index()
    )

    attendance["attendance_rate"] = (
        attendance["attendance_credit"]
        / attendance["total_records"]
    )

    # 3. HEADCOUNT VALIDATION
    headcount = pd.read_sql_query(
        """
        SELECT
            department_id,
            month_start_date AS month,
            headcount_end,
            hires,
            exits,
            attrition_rate_monthly_pct
        FROM dw.fact_headcount_monthly
        """,
        conn,
    )
    headcount["month"] = (
        pd.to_datetime(headcount["month"]).dt.to_period("M")
    )

    # 4. COMPARE RESULTS WITH THE REFERENCE SUMMARY
    checks = [
        (
            "PAYROLL",
            payroll,
            [
                "employer_cost",
                "gross_pay",
                "overtime_pay",
                "employees_paid",
                "overtime_hours",
            ],
        ),
        (
            "ATTENDANCE - DAILY MASTER SOURCE",
            attendance,
            ["late_arrivals", "attendance_rate"],
        ),
        (
            "HEADCOUNT",
            headcount,
            [
                "headcount_end",
                "hires",
                "exits",
                "attrition_rate_monthly_pct",
            ],
        ),
    ]

    for label, actual, metrics in checks:
        merged = reference.merge(
            actual,
            on=["department_id", "month"],
            how="left",
            suffixes=("_ref", "_actual"),
            indicator=True,
        )

        print(f"\n--- {label} VALIDATION ---")
        print("Reference rows:", len(reference))
        print(
            "Matched rows:",
            int((merged["_merge"] == "both").sum()),
        )
        print(
            "Unmatched rows:",
            int((merged["_merge"] != "both").sum()),
        )

        for metric in metrics:
            left = pd.to_numeric(
                merged[f"{metric}_ref"],
                errors="coerce",
            )
            right = pd.to_numeric(
                merged[f"{metric}_actual"],
                errors="coerce",
            )

            valid = left.notna() & right.notna()
            difference = (left[valid] - right[valid]).abs()

            tolerance = (
                0.02
                if metric in {
                    "employer_cost",
                    "gross_pay",
                    "overtime_pay",
                }
                else 0.0001
            )

            mismatch_mask = valid & (
                (left - right).abs() > tolerance
            )
            mismatches = int(mismatch_mask.sum())

            max_difference = (
                difference.max() if len(difference) else "N/A"
            )

            print(
                f"{metric}: compared={int(valid.sum())}, "
                f"mismatches={mismatches}, "
                f"max_difference={max_difference}"
            )

            if mismatches:
                details = merged.loc[
                    mismatch_mask,
                    ["department_id", "month"],
                ].copy()

                details["reference"] = left[mismatch_mask]
                details["actual"] = right[mismatch_mask]
                details["absolute_difference"] = (
                    left[mismatch_mask] - right[mismatch_mask]
                ).abs()

                print("First mismatches:")
                print(details.head(5).to_string(index=False))

    print(
        "\nNote: Attendance is calculated from the daily master "
        "workbook here. The warehouse attendance fact is loaded "
        "from the separate Cortex monthly features source, so "
        "these two sources should not be assumed identical."
    )

finally:
    conn.close()
