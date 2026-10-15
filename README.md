# PulseIQ ETL Pipeline

A Dockerized Python ETL pipeline for loading, cleaning, validating, and exporting workforce and payroll datasets using Pandas.

## Project Overview

This project processes workforce data from master datasets and Python team's export files. It standardizes data, validates records, separates rejected rows, and generates cleaned CSV outputs for downstream analytics.

## Tech Stack

- Python 3.11
- Pandas
- Pandera
- pytest
- Docker and Docker Compose
- Excel input files and CSV output files

## Project Structure

```text
pulseiq-etl/
├── etl/
│   ├── config.py
│   ├── cleaning.py
│   ├── validation.py
│   └── pipeline.py
├── tests/
│   └── test_cleaning.py
├── docs/
│   └── metric_dictionary.md
├── raw/                 # Local input files; not committed
├── clean/               # Generated clean CSV files
├── rejected/            # Generated rejected records
├── logs/                # Generated ETL logs
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── README.md
```

## Input Datasets

Place the following Excel workbooks inside the local `raw/` directory:

1. `01_LedgerForge_Python_Master_Dataset.xlsx`
2. `02_CortexHR_AI_ML_Dataset.xlsx`
3. `03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx`

**Note:** The raw Excel workbooks are not included in this repository. Obtain them from the assignment-provided source files and place them in `raw/` before running the pipeline.

## How to Run

### Prerequisites

Install Docker Desktop and ensure Docker is running.

### 1. Clone the repository

```bash
git clone https://github.com/Iswarya-11/pulseiq-etl.git
cd pulseiq-etl
git checkout task-1-etl-pipeline
```

### 2. Add input datasets

Create a `raw/` directory if it does not exist and copy the three required Excel workbooks into it.

### 3. Run the ETL pipeline

```bash
docker compose run --rm etl python -m etl.pipeline
```

The pipeline reads the input workbooks, processes the configured datasets, validates records, and writes generated files to the `clean/`, `rejected/`, and `logs/` directories.

### 4. Run automated tests

```bash
docker compose run --rm etl python -m pytest tests/ -v
```

## Data Quality and Validation

The pipeline includes data-cleaning and validation functionality such as:

- Standardizing column names and date values.
- Removing duplicate records where configured.
- Validating records against configured rules.
- Separating rejected records from accepted records.
- Recording processing counts for each dataset.

Records that fail validation are written to the rejected output so that data-quality issues can be reviewed rather than silently accepted.

## Latest Verification

The pipeline was executed successfully in the development environment with the assignment-provided datasets.

| Dataset | Input rows | Output rows | Rejected rows |
|---|---:|---:|---:|
| employees | 745 | 745 | 0 |
| payroll_items | 7,340 | 7,340 | 0 |
| attendance | 150,155 | 150,155 | 0 |
| leave_requests | 3,441 | 3,441 | 0 |
| salary_structures | 12,295 | 12,295 | 0 |
| attrition_dataset | 2,389 | 2,389 | 0 |
| attendance_monthly_features | 7,339 | 7,339 | 0 |
| payroll_monthly_features | 7,355 | 7,347 | 8 |
| monthly_headcount_history | 972 | 972 | 0 |
| workforce_events | 9 | 9 | 0 |

Eight payroll records were rejected because their `net_pay` values were negative. These records should be reviewed against the source data.

Automated test result: **6 tests passed**.

## Metric Documentation

See [`docs/metric_dictionary.md`](docs/metric_dictionary.md) for the documented metric definitions.

## Generated Files and Data Privacy

Generated CSV files and logs are local outputs. Raw input workbooks, generated outputs, caches, and environment files are excluded from version control through `.gitignore`.

## Branch

Task 1 implementation: [`task-1-etl-pipeline`](https://github.com/Iswarya-11/pulseiq-etl/tree/task-1-etl-pipeline)
