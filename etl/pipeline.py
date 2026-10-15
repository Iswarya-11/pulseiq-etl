from pathlib import Path
import pandas as pd

from etl.cleaning import clean_column_names, remove_duplicates


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "clean"
REJECTED_DIR = ROOT / "rejected"


def process_file(file_path):
    """Read, clean, and save one Excel or CSV file."""
    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    input_rows = len(df)

    df = clean_column_names(df)
    df = remove_duplicates(df)

    output_path = CLEAN_DIR / f"{file_path.stem}.csv"
    df.to_csv(output_path, index=False)

    print(
        f"{file_path.name}: "
        f"input={input_rows}, output={len(df)}"
    )


def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Create {RAW_DIR} and place the source datasets there."
        )

    files = [
        path for path in RAW_DIR.iterdir()
        if path.suffix.lower() in {".xlsx", ".csv"}
        and not path.name.startswith("~$")
    ]

    if not files:
        raise FileNotFoundError(
            "No Excel or CSV files found in data/raw."
        )

    for file_path in files:
        process_file(file_path)


if __name__ == "__main__":
    main()
