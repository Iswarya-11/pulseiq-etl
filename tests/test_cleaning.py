import pandas as pd

from etl.cleaning import (
    clean_column_names,
    remove_duplicates,
    standardize_dates,
)


def test_clean_column_names():
    df = pd.DataFrame({"Employee Name": ["A"]})
    result = clean_column_names(df)
    assert "employee_name" in result.columns


def test_remove_duplicates():
    df = pd.DataFrame({"id": [1, 1, 2]})
    result = remove_duplicates(df)
    assert len(result) == 2


def test_standardize_dates():
    df = pd.DataFrame({"joining_date": ["2025-01-01"]})
    result = standardize_dates(df, ["joining_date"])
    assert pd.api.types.is_datetime64_any_dtype(
        result["joining_date"]
    )
