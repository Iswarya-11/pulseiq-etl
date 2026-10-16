
from datetime import datetime
import logging

import pandas as pd
import pandera.pandas as pa

from etl.config import (
    CLEAN_DIR,
    REJECTED_DIR,
    LOG_DIR,
    MASTER_WORKBOOK,
    PYTHON_EXPORT_WORKBOOK,
    SHEETS_TO_PROCESS,
    PYTHON_EXPORT_SHEETS,
)
from etl.cleaning import clean_column_names, remove_duplicates
from etl.validation import validate_date_order


DATE_COLUMNS = [
    "date_of_birth",
    "hire_date",
    "exit_date",
    "resignation_date",
    "created_at",
    "period_start",
    "period_end",
    "attendance_date",
    "start_date",
    "end_date",
    "applied_on",
    "decided_on",
    "effective_from",
    "effective_to",
    "observation_date",
]

NONNEGATIVE_COLUMNS = {
    "payroll_items": [
        "monthly_fixed_gross",
        "gross_pay",
        "net_pay",
        "total_deductions",
        "employer_cost",
    ],
    "salary_structures": ["monthly_amount"],
    "attendance": ["hours_worked", "overtime_hours"],
    "leave_requests": ["days"],
    "payroll_monthly_features": [
        "monthly_fixed_gross",
        "overtime_pay",
        "variable_pay",
        "gross_pay",
        "net_pay",
        "total_deductions",
    ],
    "attendance_monthly_features": [
        "scheduled_days",
        "present_days",
        "overtime_hours",
    ],
}


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=LOG_DIR / "etl.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True,
    )


def save_rejected(name, rejected):
    if rejected.empty:
        return

    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    path = REJECTED_DIR / f"{name}.csv"
    rejected.to_csv(path, index=False)


def add_helpers(df):
    df = df.copy()

    date_source = None

    for candidate in ("attendance_date", "period_start", "month"):
        if candidate in df.columns:
            date_source = candidate
            break

    if date_source:
        dates = pd.to_datetime(df[date_source], errors="coerce")
        df["month_number"] = dates.dt.month
        df["year"] = dates.dt.year

    if "hire_date" in df.columns:
        hire = pd.to_datetime(df["hire_date"], errors="coerce")

        if "exit_date" in df.columns:
            end = pd.to_datetime(df["exit_date"], errors="coerce")
        else:
            end = pd.Series(pd.NaT, index=df.index)

        # Use today's date for employees who have not exited.
        end = end.fillna(pd.Timestamp.today().normalize())

        df["tenure_days"] = (end - hire).dt.days.clip(lower=0)

    return df


def pandera_check(df, name):
    checks = []

    if name == "employees" and "employee_id" in df.columns:
        checks.append(
            pa.Check(
                lambda frame: frame["employee_id"].is_unique,
                error="employee_id values must be unique",
            )
        )

    for column in NONNEGATIVE_COLUMNS.get(name, []):
        if column in df.columns:
            checks.append(
                pa.Check(
                    lambda frame, col=column: (
                        pd.to_numeric(frame[col], errors="coerce")
                        .dropna()
                        .ge(0)
                        .all()
                    ),
                    error=f"{column} must be nonnegative",
                )
            )

    if checks:
        schema = pa.DataFrameSchema(
            checks=checks,
            strict=False,
        )
        schema.validate(df, lazy=True)

    return df


def process_sheet(
    workbook,
    sheet_name,
    employee_ids=None,
    check_employee_refs=False,
):
    df = pd.read_excel(workbook, sheet_name=sheet_name)
    input_rows = len(df)

    df = clean_column_names(df)
    df = remove_duplicates(df)

    rejected_frames = []

    def reject_rows(mask, reason):
        nonlocal df

        mask = mask.fillna(False)

        if mask.any():
            bad = df.loc[mask].copy()
            bad["rejection_reason"] = reason
            rejected_frames.append(bad)
            df = df.loc[~mask].copy()

    # Reject missing employee IDs.
    if "employee_id" in df.columns:
        reject_rows(
            df["employee_id"].isna(),
            "missing employee_id",
        )

    # Reject duplicate employee IDs in the employee master.
    if sheet_name == "employees" and "employee_id" in df.columns:
        reject_rows(
            df["employee_id"].duplicated(keep="first"),
            "duplicate employee_id",
        )

    # Check employee references in master workbook tables.
    if (
        check_employee_refs
        and sheet_name != "employees"
        and employee_ids is not None
        and "employee_id" in df.columns
    ):
        reject_rows(
            ~df["employee_id"].isin(employee_ids),
            "employee_id not found in employees",
        )

    # Validate date values.
    for column in DATE_COLUMNS:
        if column in df.columns:
            original = df[column]
            converted = pd.to_datetime(original, errors="coerce")

            invalid = original.notna() & converted.isna()

            reject_rows(
                invalid,
                f"invalid date in {column}",
            )

            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
            )

    # Reject invalid date ranges.
    for start_col, end_col in [
        ("hire_date", "exit_date"),
        ("start_date", "end_date"),
    ]:
        if start_col in df.columns and end_col in df.columns:
            df, bad = validate_date_order(
                df,
                joining_column=start_col,
                leaving_column=end_col,
            )

            if not bad.empty:
                rejected_frames.append(bad)

    # Reject negative values in relevant columns.
    for column in NONNEGATIVE_COLUMNS.get(sheet_name, []):
        if column in df.columns:
            values = pd.to_numeric(
                df[column],
                errors="coerce",
            )

            reject_rows(
                values.notna() & (values < 0),
                f"negative value in {column}",
            )

    # Validate accepted rows using Pandera.
    pandera_check(df, sheet_name)

    df = add_helpers(df)

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        CLEAN_DIR / f"{sheet_name}.csv",
        index=False,
    )

    rejected_all = (
        pd.concat(rejected_frames, ignore_index=True)
        if rejected_frames
        else pd.DataFrame()
    )

    save_rejected(sheet_name, rejected_all)

    logging.info(
        "%s | input=%s | output=%s | rejected=%s",
        sheet_name,
        input_rows,
        len(df),
        len(rejected_all),
    )

    print(
        f"{sheet_name}: input={input_rows}, "
        f"output={len(df)}, rejected={len(rejected_all)}"
    )

    return df


def main():
    setup_logging()

    started = datetime.now()

    logging.info(
        "ETL run started at %s",
        started.isoformat(),
    )

    for workbook in (MASTER_WORKBOOK, PYTHON_EXPORT_WORKBOOK):
        if not workbook.exists():
            raise FileNotFoundError(
                f"Workbook not found: {workbook}"
            )

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Remove previous CSV outputs to avoid stale files.
    for folder in (CLEAN_DIR, REJECTED_DIR):
        for old_file in folder.glob("*.csv"):
            old_file.unlink()

    employee_ids = None

    # Process the master workbook.
    for sheet_name in SHEETS_TO_PROCESS:
        cleaned = process_sheet(
            MASTER_WORKBOOK,
            sheet_name,
            employee_ids=employee_ids,
            check_employee_refs=True,
        )

        if sheet_name == "employees":
            employee_ids = set(
                cleaned["employee_id"].dropna()
            )

    # Process selected Python export workbook sheets.
    for sheet_name in PYTHON_EXPORT_SHEETS:
        process_sheet(
            PYTHON_EXPORT_WORKBOOK,
            sheet_name,
        )

    logging.info(
        "ETL run completed at %s",
        datetime.now().isoformat(),
    )


if __name__ == "__main__":
    main()
