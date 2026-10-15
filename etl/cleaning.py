import pandas as pd


def clean_column_names(df):
    """Standardize column names."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def remove_duplicates(df):
    """Remove fully duplicated rows."""
    return df.drop_duplicates().reset_index(drop=True)


def standardize_dates(df, date_columns):
    """Convert specified columns to dates where present."""
    df = df.copy()

    for column in date_columns:
        if column in df.columns:
            df[column] = pd.to_datetime(
                df[column], errors="coerce"
            )

    return df
