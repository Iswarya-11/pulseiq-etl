from datetime import datetime
import logging

import pandas as pd

from etl.config import (
    RAW_DIR,
    CLEAN_DIR,
    REJECTED_DIR,
    LOG_DIR,
    MASTER_WORKBOOK,
    SHEETS_TO_PROCESS,
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
}


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / "etl.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True,
    )


def save_rejected(sheet_name, rejected):
    if rejected.empty:
        return

    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    output = REJECTED_DIR / f"{sheet_name}.csv"

    if output.exists():
        previous = pd.read_csv(output)
        rejected = pd.concat(
            [previous, rejected], ignore_index=True
        )

    rejected.to_csv(output, index=False)


def add_date_helpers(df):
    df = df.copy()

    if "attendance_date" in df.columns:
        dates = pd.to_datetime(
            df["attendance_date"], errors="coerce"
        )
        df["month"] = dates.dt.month
        df["year"] = dates.dt.year

    elif "period_start" in df.columns:
        dates = pd.to_datetime(
            df["period_start"], errors="coerce"
        )
        df["month"] = dates.dt.month
        df["year"] = dates.dt.year

    if "hire_date" in df.columns:
        hire = pd.to_datetime(
            df["hire_date"], errors="coerce"
        )
        end = pd.to_datetime(
            df.get("exit_date", pd.Series(
                pd.NaT, index=df.index
            )),
            errors="coerce",
        )
        end = end.fillna(pd.Timestamp.today().normalize())

        df["tenure_days"] = (end - hire).dt.days.clip(lower=0)

    return df


def process_sheet(sheet_name, employee_ids=None):
    df = pd.read_excel(
        MASTER_WORKBOOK,
        sheet_name=sheet_name,
    )
    input_rows = len(df)

    df = clean_column_names(df)
    df = remove_duplicates(df)

    rejected_frames = []

    # Reject rows with missing employee IDs.
    if "employee_id" in df.columns:
        missing_id = df["employee_id"].isna()
        if missing_id.any():
            rejected = df.loc[missing_id].copy()
            rejected["rejection_reason"] = "missing employee_id"
            rejected_frames.append(rejected)
            df = df.loc[~missing_id].copy()

    # Employee IDs must be unique in the employee master.
    if sheet_name == "employees" and "employee_id" in df.columns:
        duplicate_id = df["employee_id"].duplicated(keep="first")
        if duplicate_id.any():
            rejected = df.loc[duplicate_id].copy()
            rejected["rejection_reason"] = (
                "duplicate employee_id"
            )
            rejected_frames.append(rejected)
            df = df.loc[~duplicate_id].copy()

    # Fact records must refer to a known employee.
    if (
        sheet_name != "employees"
        and employee_ids is not None
        and "employee_id" in df.columns
    ):
        unknown_id = ~df["employee_id"].isin(employee_ids)
        if unknown_id.any():
            rejected = df.loc[unknown_id].copy()
            rejected["rejection_reason"] = (
                "employee_id not found in employees"
            )
            rejected_frames.append(rejected)
            df = df.loc[~unknown_id].copy()

    # Convert recognized date columns.
    for column in DATE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_datetime(
                df[column], errors="coerce"
            )

    # Reject invalid hire/exit or start/end date order.
    date_pairs = [
        ("hire_date", "exit_date"),
        ("start_date", "end_date"),
    ]

    for start_col, end_col in date_pairs:
        if start_col in df.columns and end_col in df.columns:
            df, rejected = validate_date_order(
                df,
                joining_column=start_col,
                leaving_column=end_col,
            )
            if not rejected.empty:
                rejected_frames.append(rejected)

    # Reject rows with negative values in specified measures.
    for column in NONNEGATIVE_COLUMNS.get(sheet_name, []):
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce")
            invalid = values.notna() & (values < 0)

            if invalid.any():
                rejected = df.loc[invalid].copy()
                rejected["rejection_reason"] = (
                    f"negative value in {column}"
                )
                rejected_frames.append(rejected)
                df = df.loc[~invalid].copy()

    df = add_date_helpers(df)

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_DIR / f"{sheet_name}.csv", index=False)

    if rejected_frames:
        rejected_all = pd.concat(
            rejected_frames, ignore_index=True
        )
        save_rejected(sheet_name, rejected_all)
    else:
        rejected_all = pd.DataFrame()

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
    start_time = datetime.now()

    logging.info("ETL run started at %s", start_time.isoformat())

    if not MASTER_WORKBOOK.exists():
        raise FileNotFoundError(
            f"Master workbook not found: {MASTER_WORKBOOK}"
        )

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    # Clear previous outputs so repeated runs are reproducible.
    for folder in (CLEAN_DIR, REJECTED_DIR):
        for old_file in folder.glob("*.csv"):
            old_file.unlink()

    employee_ids = None

    for sheet_name in SHEETS_TO_PROCESS:
        cleaned = process_sheet(
            sheet_name,
            employee_ids=employee_ids,
        )

        if sheet_name == "employees":
            employee_ids = set(cleaned["employee_id"].dropna())

    logging.info(
        "ETL run completed at %s",
        datetime.now().isoformat(),
    )


if __name__ == "__main__":
    main()
