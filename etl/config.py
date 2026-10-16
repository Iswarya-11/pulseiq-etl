
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "raw"
CLEAN_DIR = PROJECT_ROOT / "clean"
REJECTED_DIR = PROJECT_ROOT / "rejected"
LOG_DIR = PROJECT_ROOT / "logs"

MASTER_WORKBOOK = (
    RAW_DIR / "01_LedgerForge_Python_Master_Dataset.xlsx"
)

PYTHON_EXPORT_WORKBOOK = (
    RAW_DIR / "02_CortexHR_AI_ML_Dataset.xlsx"
)

SHEETS_TO_PROCESS = [
    "employees",
    "payroll_items",
    "attendance",
    "leave_requests",
    "salary_structures",
]

PYTHON_EXPORT_SHEETS = [
    "attrition_dataset",
    "attendance_monthly_features",
    "payroll_monthly_features",
    "monthly_headcount_history",
    "workforce_events",
]
