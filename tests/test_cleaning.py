
import pandas as pd

from etl.cleaning import (
    clean_column_names,
    remove_duplicates,
    standardize_dates,
)
from etl.validation import validate_date_order


def test_clean_column_names():
    df = pd.DataFrame({" Employee Name ": ["A"]})
    result = clean_column_names(df)
    assert "employee_name" in result.columns


def test_remove_duplicates():
    df = pd.DataFrame({"id": [1, 1, 2]})
    result = remove_duplicates(df)
    assert len(result) == 2
    assert result["id"].tolist() == [1, 2]


def test_standardize_dates():
    df = pd.DataFrame({"joining_date": ["2025-01-01"]})
    result = standardize_dates(df, ["joining_date"])
    assert pd.api.types.is_datetime64_any_dtype(
        result["joining_date"]
    )


def test_standardize_dates_invalid_value_becomes_missing():
    df = pd.DataFrame({"joining_date": ["not-a-date"]})
    result = standardize_dates(df, ["joining_date"])
    assert pd.isna(result.loc[0, "joining_date"])


def test_standardize_dates_leaves_missing_column_unchanged():
    df = pd.DataFrame({"employee_id": ["EMP-001"]})
    result = standardize_dates(df, ["joining_date"])
    assert result.equals(df)


def test_validate_date_order_rejects_exit_before_hire():
    df = pd.DataFrame({
        "hire_date": pd.to_datetime(["2025-05-10", "2025-01-01"]),
        "exit_date": pd.to_datetime(["2025-05-01", "2025-03-01"]),
    })

    cleaned, rejected = validate_date_order(
        df,
        joining_column="hire_date",
        leaving_column="exit_date",
    )

    assert len(cleaned) == 1
    assert len(rejected) == 1
    assert cleaned.iloc[0]["hire_date"] == pd.Timestamp("2025-01-01")
