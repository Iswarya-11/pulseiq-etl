import pandas as pd


def validate_date_order(
    df,
    joining_column="hire_date",
    leaving_column="exit_date",
):
    """Reject employees whose exit date is before their hire date."""
    df = df.copy()

    if joining_column not in df.columns:
        return df, pd.DataFrame()

    if leaving_column not in df.columns:
        return df, pd.DataFrame()

    joining = pd.to_datetime(
        df[joining_column], errors="coerce"
    )
    leaving = pd.to_datetime(
        df[leaving_column], errors="coerce"
    )

    invalid = (
        joining.notna()
        & leaving.notna()
        & (leaving < joining)
    )

    rejected = df.loc[invalid].copy()
    rejected["rejection_reason"] = "dates out of order"

    accepted = df.loc[~invalid].copy()

    return accepted, rejected


def validate_nonnegative(df, column):
    """Reject rows with negative numeric values."""
    df = df.copy()

    if column not in df.columns:
        return df, pd.DataFrame()

    values = pd.to_numeric(df[column], errors="coerce")
    invalid = values.notna() & (values < 0)

    rejected = df.loc[invalid].copy()
    rejected["rejection_reason"] = (
        f"negative value in {column}"
    )

    accepted = df.loc[~invalid].copy()

    return accepted, rejected
