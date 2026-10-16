
CREATE SCHEMA IF NOT EXISTS dw;

CREATE TABLE IF NOT EXISTS dw.dim_department (
    department_id TEXT PRIMARY KEY,
    department_name TEXT NOT NULL,
    cost_center TEXT,
    description TEXT,
    is_leadership BOOLEAN
);

CREATE TABLE IF NOT EXISTS dw.dim_role (
    role_id TEXT PRIMARY KEY,
    department_id TEXT,
    role_title TEXT,
    level TEXT,
    grade TEXT,
    band_min_annual NUMERIC(14,2),
    band_mid_annual NUMERIC(14,2),
    band_max_annual NUMERIC(14,2),
    overtime_eligible BOOLEAN,
    band_reference_year INTEGER
);

CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INTEGER,
    quarter INTEGER,
    month_number INTEGER,
    month_name TEXT,
    year_month TEXT,
    week_of_year INTEGER,
    day_of_week TEXT,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    is_working_day BOOLEAN,
    financial_year TEXT,
    fiscal_quarter TEXT,
    fiscal_month_number INTEGER,
    is_month_end BOOLEAN,
    month_start_date DATE,
    month_end_date DATE
);

CREATE TABLE IF NOT EXISTS dw.dim_leave_type (
    leave_type_code TEXT PRIMARY KEY,
    leave_type_name TEXT,
    pay_type TEXT,
    annual_quota_days NUMERIC(8,2),
    prorated_for_joiners BOOLEAN,
    carry_forward_allowed BOOLEAN,
    max_carry_forward_days NUMERIC(8,2),
    policy_note TEXT
);

CREATE TABLE IF NOT EXISTS dw.dim_employee (
    employee_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id TEXT NOT NULL,
    full_name TEXT,
    gender TEXT,
    date_of_birth DATE,
    hire_date DATE,
    exit_date DATE,
    employment_status TEXT,
    employment_type TEXT,
    department_id TEXT,
    role_id TEXT,
    manager_id TEXT,
    work_location TEXT,
    work_mode TEXT,
    highest_education TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    change_reason TEXT,
    CONSTRAINT uq_employee_version
        UNIQUE (employee_id, valid_from),
    CONSTRAINT ck_employee_valid_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

-- Daily attendance: one row per employee per day.
CREATE TABLE IF NOT EXISTS dw.fact_attendance (
    attendance_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    employee_key BIGINT REFERENCES dw.dim_employee(employee_key),
    date_key INTEGER REFERENCES dw.dim_date(date_key),
    attendance_date DATE NOT NULL,
    department_id TEXT,
    weekday TEXT,
    status TEXT,
    leave_type_code TEXT REFERENCES dw.dim_leave_type(leave_type_code),
    check_in TEXT,
    check_out TEXT,
    hours_worked NUMERIC(8,2),
    overtime_hours NUMERIC(8,2),
    late_flag TEXT,
    source TEXT,
    data_quality_flag TEXT,
    CONSTRAINT uq_attendance_employee_day
        UNIQUE (employee_id, attendance_date)
);

-- Retained monthly attendance summary for existing analytics.
CREATE TABLE IF NOT EXISTS dw.fact_attendance_monthly (
    attendance_fact_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id TEXT NOT NULL,
    employee_key BIGINT REFERENCES dw.dim_employee(employee_key),
    date_key INTEGER REFERENCES dw.dim_date(date_key),
    period_end_date DATE NOT NULL,
    department_id TEXT,
    scheduled_days NUMERIC(8,2),
    present_days NUMERIC(8,2),
    wfh_days NUMERIC(8,2),
    half_days_unpaid NUMERIC(8,2),
    paid_leave_days NUMERIC(8,2),
    unpaid_absence_days NUMERIC(8,2),
    late_arrivals INTEGER,
    avg_hours_worked NUMERIC(8,2),
    overtime_hours NUMERIC(8,2),
    attendance_rate NUMERIC(8,4),
    CONSTRAINT uq_attendance_employee_month
        UNIQUE (employee_id, period_end_date)
);

-- Payroll: one row per employee per payroll month.
CREATE TABLE IF NOT EXISTS dw.fact_payroll (
    payroll_item_id TEXT PRIMARY KEY,
    run_id TEXT,
    employee_id TEXT NOT NULL,
    employee_key BIGINT REFERENCES dw.dim_employee(employee_key),
    date_key INTEGER REFERENCES dw.dim_date(date_key),
    period_start DATE,
    period_end_date DATE,
    department_id TEXT,
    role_id TEXT,
    payable_days NUMERIC(8,2),
    lop_days NUMERIC(8,2),
    overtime_hours_paid NUMERIC(8,2),
    monthly_fixed_gross NUMERIC(14,2),
    basic NUMERIC(14,2),
    hra NUMERIC(14,2),
    conveyance NUMERIC(14,2),
    medical NUMERIC(14,2),
    special_allowance NUMERIC(14,2),
    earned_fixed_pay NUMERIC(14,2),
    overtime_pay NUMERIC(14,2),
    variable_pay NUMERIC(14,2),
    gross_pay NUMERIC(14,2),
    pf_employee NUMERIC(14,2),
    esi_employee NUMERIC(14,2),
    professional_tax NUMERIC(14,2),
    tds NUMERIC(14,2),
    other_deductions NUMERIC(14,2),
    total_deductions NUMERIC(14,2),
    net_pay NUMERIC(14,2),
    pf_employer NUMERIC(14,2),
    esi_employer NUMERIC(14,2),
    employer_cost NUMERIC(14,2),
    headcount_flag INTEGER,
    CONSTRAINT uq_payroll_employee_month
        UNIQUE (employee_id, period_end_date)
);

CREATE TABLE IF NOT EXISTS dw.fact_leave (
    leave_request_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    employee_key BIGINT REFERENCES dw.dim_employee(employee_key),
    leave_type_code TEXT REFERENCES dw.dim_leave_type(leave_type_code),
    start_date_key INTEGER REFERENCES dw.dim_date(date_key),
    end_date_key INTEGER REFERENCES dw.dim_date(date_key),
    start_date DATE,
    end_date DATE,
    days NUMERIC(8,2),
    status TEXT,
    applied_on DATE,
    decided_on DATE,
    approver_id TEXT,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS dw.fact_headcount_monthly (
    date_key INTEGER REFERENCES dw.dim_date(date_key),
    month_start_date DATE NOT NULL,
    department_id TEXT NOT NULL,
    headcount_start INTEGER,
    hires INTEGER,
    exits INTEGER,
    voluntary_exits INTEGER,
    transfers_in INTEGER,
    transfers_out INTEGER,
    headcount_end INTEGER,
    attrition_rate_monthly_pct NUMERIC(8,4),
    PRIMARY KEY (month_start_date, department_id)
);

-- Indexes for common joins and date filters.
CREATE INDEX IF NOT EXISTS idx_employee_business_id
    ON dw.dim_employee(employee_id);

CREATE INDEX IF NOT EXISTS idx_employee_current
    ON dw.dim_employee(employee_id, is_current);

CREATE INDEX IF NOT EXISTS idx_attendance_employee_date
    ON dw.fact_attendance(employee_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_date
    ON dw.fact_attendance(attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_monthly_period
    ON dw.fact_attendance_monthly(period_end_date);

CREATE INDEX IF NOT EXISTS idx_payroll_period
    ON dw.fact_payroll(period_end_date);

CREATE INDEX IF NOT EXISTS idx_payroll_run
    ON dw.fact_payroll(run_id);

CREATE INDEX IF NOT EXISTS idx_payroll_employee_month
    ON dw.fact_payroll(employee_id, period_end_date);

CREATE INDEX IF NOT EXISTS idx_leave_dates
    ON dw.fact_leave(start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_headcount_department_month
    ON dw.fact_headcount_monthly(department_id, month_start_date);
