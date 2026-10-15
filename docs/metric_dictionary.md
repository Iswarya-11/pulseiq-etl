# PulseIQ Metric Dictionary

## 1. Purpose

This document defines the workforce, payroll, finance, attendance, engineering, and AI/ML metrics used in PulseIQ. The definitions and formulas are based on the `metric_dictionary` sheet in `03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx`.

Metrics must be calculated consistently, validated against the source tables, and interpreted using their documented caveats.

## 2. Workforce and Attrition Metrics

| ID | Metric | Business Definition | Formula | Source Table | Grain / Period | Unit | Caveat |
|---|---|---|---|---|---|---|---|
| M01 | Headcount | Active permanent and contract employees on the last day of the month. | Count distinct employees hired by month-end whose exit date is blank or after month-end. | `fact_headcount_monthly` / `dim_employee` | Department × month; month-end | Count | Excludes the CEO when comparing departments only. |
| M02 | Hires | Employees whose hire date falls within the month. | Count employees hired during the month. | `fact_headcount_monthly` | Department × month; monthly | Count | Transfers are not hires. |
| M03 | Exits | Employees who resigned, were terminated, or whose contracts ended during the month. | Count employees whose exit date falls within the month. | `fact_headcount_monthly` | Department × month; monthly | Count | Lower is better. |
| M04 | Monthly Attrition Rate | Share of people who left during the month. | Exits / Headcount at start of month × 100 | `fact_headcount_monthly` | Department × month; monthly | Percent | Very noisy for small departments. |
| M05 | Rolling 12-Month Attrition Rate | Leavers in the last 12 months divided by average headcount over the same period. | Sum of exits over 12 months / Average month-end headcount over 12 months × 100 | `fact_headcount_monthly` | Department × month; rolling 12 months | Percent | Preferred for headline reporting; monthly attrition is more volatile. |
| M06 | Voluntary Attrition Rate | Rolling attrition based only on resignations. | Sum of voluntary exits over 12 months / Average month-end headcount over 12 months × 100 | `fact_headcount_monthly` | Department × month; rolling 12 months | Percent | Uses voluntary exits only. |
| M27 | High-Risk Share | Share of employees in the High attrition-risk band. | Count of records with `risk_band = High` / Total records | `fact_attrition_risk` | Department; point in time | Percent | Show by group only; never rank named individuals. |

## 3. Payroll Metrics

| ID | Metric | Business Definition | Formula | Source Table | Grain / Period | Unit | Caveat |
|---|---|---|---|---|---|---|---|
| M07 | Gross Pay | Total employee earnings before deductions for the month. | Sum of `gross_pay` | `fact_payroll` | Employee × month; monthly | INR | Includes overtime and variable pay. |
| M08 | Net Pay | Take-home pay after employee deductions. | Sum of `net_pay` | `fact_payroll` | Employee × month; monthly | INR | Validate against source payroll records. |
| M09 | Payroll Cost (Employer Cost) | Total employee cost to the company, including gross pay and employer PF and ESI. | Sum of `employer_cost` | `fact_payroll` | Employee × month; monthly | INR | Must reconcile with ledger accounts 5001–5005. |
| M10 | Cost per Head | Average employer cost per paid employee. | Sum of `employer_cost` / Count distinct employee IDs | `fact_payroll` | Department × month; monthly | INR | Part-month joiners may reduce the average. |
| M11 | Overtime Share | Share of employer payroll cost represented by overtime pay. | Sum of `overtime_pay` / Sum of `employer_cost` × 100 | `fact_payroll` | Department × month; monthly | Percent | Only overtime-eligible roles earn overtime. |
| M12 | Variable Pay Share | Bonus, incentive, and award pay as a share of gross pay. | Sum of `variable_pay` / Sum of `gross_pay` × 100 | `fact_payroll` | Department × month; monthly | Percent | April bonuses and quarter-end incentives may create spikes. |
| M15 | Leave Without Pay Days | Unpaid absence and unpaid leave days. | Sum of `lop_days` | `fact_payroll` | Employee × month; monthly | Days | Half-day unpaid leave counts as 0.5 days. |

## 4. Attendance Metrics

| ID | Metric | Business Definition | Formula | Source Table | Grain / Period | Unit | Caveat |
|---|---|---|---|---|---|---|---|
| M13 | Attendance Rate | Days present, including half-day adjustments, divided by scheduled working days. | (Sum of `present_days` + 0.5 × Sum of `half_days_unpaid`) / Sum of `scheduled_days` | `fact_attendance_monthly` | Department × month; monthly | Ratio | Paid leave counts as not present. |
| M14 | Late Arrival Rate | Late check-ins per present day. | Sum of `late_arrivals` / Sum of `present_days` | `fact_attendance_monthly` | Department × month; monthly | Ratio | Work-from-home days use web check-in time. |

## 5. Finance Metrics

| ID | Metric | Business Definition | Formula | Source Table | Grain / Period | Unit | Caveat |
|---|---|---|---|---|---|---|---|
| M16 | Revenue | Income recorded in ledger accounts 4001–4004. | Negative sum of `signed_amount` for accounts 4001–4004 | `fact_ledger` | Account × month; monthly | INR | Excludes GST, which is recorded in account 2200. |
| M17 | Net Profit | Revenue minus expenses, using accounts in the 4xxx and 5xxx ranges. | Negative sum of `signed_amount` for accounts 4xxx and 5xxx | `fact_ledger` | Month; monthly | INR | Interest income from account 4900 is included. |
| M18 | Operating Margin | Net profit as a share of revenue. | Net Profit / Revenue × 100 | `fact_ledger` | Month; monthly | Percent | Interpret alongside revenue and net profit. |
| M19 | Payroll as % of Revenue | Share of revenue consumed by payroll cost. | Payroll Cost / Revenue × 100 | `fact_payroll` + `fact_ledger` | Month; monthly | Percent | Use ledger payroll accounts to avoid mismatches. |
| M20 | Days Sales Outstanding (DSO) | Average collection time based on receivables and credit sales. | Closing receivables / Revenue including GST for the last 90 days × 90 | `fact_invoice`, `fact_ledger` | Month; 90 days | Days | Carried-in invoices are included. |
| M21 | Overdue Receivables | Unpaid invoice balance past its due date at the reporting date. | Sum of `balance_due` where due date is before report date and status is not DRAFT or CANCELLED | `fact_invoice` | Client × date; point in time | INR | Exclude draft and cancelled invoices. |

## 6. Engineering and Delivery Metrics

| ID | Metric | Business Definition | Formula | Source Table | Grain / Period | Unit | Caveat |
|---|---|---|---|---|---|---|---|
| M22 | Task Completion Rate | Tasks completed divided by planned tasks, excluding cancelled tasks. | Count of Done tasks / Count of tasks not Cancelled | `fact_task` | Team × sprint; sprint | Percent | Sample feed until the live board is ready; minimum 5 tasks. |
| M23 | On-Time Delivery Rate | Done tasks completed on or before the sprint end date. | Count of tasks with `completed_on_time = Y` / Count of Done tasks | `fact_task` | Team × sprint; sprint | Percent | Minimum 5 tasks. |
| M24 | Velocity | Story points completed during the sprint. | Sum of `story_points` where status is Done | `fact_task` | Team × sprint; sprint | Points | Do not compare velocity across teams. |
| M25 | Average Cycle Time | Average days from task start to completion for completed tasks. | Average of completion date − start date | `fact_task` | Team × sprint; sprint | Days | Negative values indicate data errors. |

## 7. AI/ML Metrics

| ID | Metric | Business Definition | Formula | Source Table | Grain / Period | Unit | Caveat |
|---|---|---|---|---|---|---|---|
| M26 | Anomaly Flag Rate | Share of scored records flagged by the AI anomaly service. | Count of flagged records / Total records | `fact_anomaly` | Source × month; monthly | Percent | Flags are leads for investigation, not proof of an issue. |
| M28 | Forecast Error (MAPE) | Average absolute percentage error of headcount forecasts versus actual values. | Average of absolute(actual − forecast) / actual × 100 | `fact_forecast` versus `fact_headcount` | Department × month; rolling | Percent | Requires actual values for the forecast months. |

## 8. Interpretation and Data Quality Rules

- Use the original business definition and formula for each metric.
- Apply the documented reporting grain and time period consistently.
- Validate calculations against the appropriate source tables.
- Investigate negative or inconsistent financial values rather than silently changing them.
- Avoid drawing conclusions from small groups where the dictionary specifies a minimum group size.
- Treat AI anomaly flags and attrition-risk scores as signals for investigation, not definitive conclusions about individuals.
- Reconcile payroll costs with the specified ledger accounts before publishing finance KPIs.
- Document any changes to formulas or definitions before applying them to dashboards.

## 9. Source Reference

**Source workbook:** `03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx`

**Source sheet:** `metric_dictionary`

**Coverage:** 28 metrics, M01–M28.
