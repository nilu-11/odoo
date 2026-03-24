# edu_fees_structure — Module Summary

## Overview

This is an Odoo 19 module (`edu_fees_structure`) that is part of a larger Education Management Information System (EMIS). It handles **fee configuration** — defining what fees are owed by students and how those fees are collected. It does NOT generate invoices; that is the responsibility of a downstream billing module.

The module depends on `edu_academic_structure`, which provides:
- `edu.academic.year` — academic/intake years
- `edu.program` — degree programs (e.g., BCA, BBA)
- `edu.program.term` — progression stages (e.g., BCA Semester 1, BCA Semester 2)
- `edu.batch` — a specific batch within a program and intake year
- `edu.term` — term definitions (semester, trimester, etc.)

---

## Core Design Principle

The module separates two concerns:

1. **What is owed** — fee amounts per progression stage (fee structure + fee lines)
2. **How it is collected** — payment plan configuration (installment slots or monthly billing)

---

## Models

### 1. `edu.fee.head`
Reusable fee components. Think of these as categories of fees.

**Key fields:**
- `name`, `code` — identity
- `fee_type` — selection: `admission`, `tuition`, `exam`, `lab`, `university_registration`, `hostel`, `transport`, `other`
- `is_one_time` — boolean, e.g. Admission Fee is collected once
- `is_refundable` — boolean, defaults onto fee lines
- `active` — archivable
- `company_id` — multi-company support

**Constraint:** `UNIQUE(code, company_id)`

**Delete guard:** Cannot delete if used in any fee structure line.

---

### 2. `edu.fee.term`
Named payment timing labels. Optional reference data used if the institution wants named slots like "At Admission", "Installment 1", "Semester Fee".

**Key fields:**
- `name`, `code`
- `term_type` — selection: `admission`, `installment`, `semester`, `annual`, `trigger_based`
- `sequence`, `active`, `company_id`

> Note: This model does NOT inherit `mail.thread` — no chatter.

---

### 3. `edu.fee.structure`
The master record. One fee structure covers the **full program duration** (all semesters/stages) for a specific intake cohort.

**Scope:** `program_id` + `academic_year_id` (intake/cohort year) + optional `batch_id`
- If `batch_id` is blank → general program-level structure
- If `batch_id` is set → batch-specific override

**Key fields:**
- `name`, `code` (auto-assigned via `ir.sequence`)
- `academic_year_id` — the intake/cohort year (NOT the current calendar year)
- `program_id`, `batch_id`, `department_id` (related), `company_id` (related)
- `currency_id`
- `total_amount` — computed sum of all line amounts
- `line_count` — computed count of fee lines
- `payment_plan_count` — computed count of payment plans
- `state` — `draft` → `active` → `closed`
- `active` — archivable
- `note`

**State transitions:**
- `action_activate()` — draft → active (requires at least one fee line)
- `action_close()` — active → closed
- `action_reset_draft()` — active/closed → draft

**Write locking:** Closed structures cannot be modified (except state, active, note, chatter fields).

**Uniqueness:** Only one fee structure per `(program_id, academic_year_id, batch_id)` scope. Enforced in Python (not SQL) to handle NULL `batch_id` correctly in PostgreSQL.

**Integration helpers (for billing/enrollment/admission modules):**
- `get_fee_summary()` — returns fee breakdown grouped by progression stage
- `get_payment_plans()` — returns all payment plans with full installment/monthly detail
- `get_scholarship_applicable_total()` — sum of scholarship-eligible fee amounts

---

### 4. `edu.fee.structure.line`
One fee component for one progression stage. Answers: "how much is owed for fee head X in semester Y?"

**Key fields:**
- `fee_structure_id` — parent structure (cascade delete)
- `program_term_id` — which semester/stage (e.g. BCA Semester 1)
- `fee_head_id` — which fee component (e.g. Tuition Fee)
- `amount` — total amount owed for this fee in this stage
- `payment_trigger` — optional: `at_admission`, `at_exam_registration`, `before_exam`, `before_result`, `custom`
- `mandatory` — cannot be waived
- `scholarship_allowed` — eligible for discount/scholarship
- `refundable` — defaults from fee head, overrideable per line
- `sequence`, `note`

**Stored related fields** (for reporting/search/billing):
- `progression_no` — from `program_term_id.progression_no`
- `currency_id` — from fee structure
- `fee_type` — from fee head
- `program_id`, `academic_year_id`, `batch_id`, `company_id` — from fee structure

**SQL constraint:** `UNIQUE(fee_structure_id, program_term_id, fee_head_id)`

**Write locking:**
- Closed structure → no changes at all
- Active structure → only `amount`, `mandatory`, `scholarship_allowed`, `refundable`, `sequence`, `note`, `payment_trigger` can change; structural fields (`program_term_id`, `fee_head_id`) are locked
- Draft → fully editable

**Unlink guard:** Can only delete lines when structure is in draft.

**`payment_trigger` usage:**
- Set for fees billed outside the payment plan (e.g. Admission Fee → `at_admission`, University Reg Fee → `at_exam_registration`)
- Leave blank for fees handled by the payment plan (Tuition, Lab)
- The billing module uses this to determine when to generate the invoice for standalone fees

---

### 5. `edu.fee.payment.plan`
A configurable payment plan that defines HOW fees are collected. Multiple plans can exist on one fee structure — students (or batches) are assigned one plan at enrollment.

**Key fields:**
- `fee_structure_id` — parent structure (cascade delete)
- `name` — e.g. "Standard Installment Plan", "Monthly Payment Plan"
- `sequence`
- `plan_type` — `installment` or `monthly`
- `months_count` — required for monthly plans (must be > 0)
- `excluded_fee_head_ids` — Many2many to `edu.fee.head`; fee heads excluded from the monthly calculation
- `installment_line_ids` — One2many to `edu.fee.installment.line`; required for installment plans
- `note`, `company_id`

**Constraints:**
- Monthly plan: `months_count` must be > 0
- Installment plan: must have at least one installment line

**Write/unlink locking:** Same rules as fee structure lines.

---

### 6. `edu.fee.installment.line`
One installment slot within an installment payment plan.

**Key fields:**
- `plan_id` — parent plan (cascade delete)
- `sequence` — controls order (Installment 1, 2, 3...)
- `label` — display name (e.g. "Installment 1", "At Admission", "Before Exam")
- `fee_head_ids` — Many2many to `edu.fee.head`; which fee heads are due at this slot
- `note`, `company_id`

---

## How Payment Plans Work

### Installment-Based Plan
The plan is a **semester-agnostic template**. You configure it once:
- Installment 1 → Tuition Fee
- Installment 2 → Lab Fee
- Installment 3 → University Registration Fee

The billing module applies this template to **each semester independently**:
- For Semester 1: match Tuition → Inst 1 invoice, Lab → Inst 2 invoice, Uni Reg → Inst 3 invoice. Admission Fee has `payment_trigger = at_admission` → billed separately at enrollment.
- For Semester 2–8: same template, no Admission Fee line → no separate admission charge.

Any fee head **not listed in any installment slot** is treated as a standalone charge, billed according to its `payment_trigger`.

### Monthly Plan
Per semester:
```
monthly_amount = (sum of all fee lines in that semester
                  EXCLUDING excluded_fee_head_ids) / months_count
```
Excluded fee heads are billed separately via their `payment_trigger`.

**Example (Semester 1, 6 months, excluded: Admission Fee + University Reg Fee):**
```
Admission Fee (10,000) → billed at_admission
University Reg Fee (1,500) → billed at_exam_registration
Monthly amount = (Tuition 5,000 + Lab 2,000) / 6 = Rs. 1,166.67/month
```

---

## Security Groups

Defined in `security/security.xml` and `edu_academic_structure`:

| Group | Permissions |
|---|---|
| `group_education_admin` | Full CRUD on all models |
| `group_fees_officer` | CRUD on all models (no delete on structures/lines) |
| `group_fees_viewer` | Read-only on all models |
| `group_academic_officer` | Read-only on all models |
| `group_academic_viewer` | Read-only on all models |

---

## File Structure

```
edu_fees_structure/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── edu_fee_head.py
│   ├── edu_fee_term.py
│   ├── edu_fee_structure.py
│   ├── edu_fee_structure_line.py
│   └── edu_fee_payment_plan.py       # contains both edu.fee.payment.plan
│                                      # and edu.fee.installment.line
├── views/
│   ├── edu_fee_head_views.xml
│   ├── edu_fee_term_views.xml
│   ├── edu_fee_payment_plan_views.xml
│   ├── edu_fee_structure_views.xml
│   └── menu_views.xml
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
└── data/
    └── sequences.xml                  # sequence for edu.fee.structure code
```

---

## Integration API

The following methods on `edu.fee.structure` are designed for downstream modules:

### `get_fee_summary()`
Returns fee breakdown grouped by progression stage, sorted by `progression_no`.
```python
[
    {
        'program_term_id': int,
        'program_term_name': str,
        'progression_no': int,
        'academic_year': str,
        'lines': [
            {
                'fee_head_id': int,
                'fee_head': str,
                'fee_type': str,
                'payment_trigger': str | None,
                'amount': float,
                'mandatory': bool,
                'scholarship_allowed': bool,
                'refundable': bool,
            },
            ...
        ],
        'subtotal': float,
        'mandatory_subtotal': float,
        'scholarship_eligible_subtotal': float,
    },
    ...
]
```

### `get_payment_plans()`
Returns all payment plans with full detail.
```python
[
    {
        'plan_id': int,
        'name': str,
        'plan_type': 'installment' | 'monthly',
        'months_count': int,
        'excluded_fee_heads': [{'id': int, 'name': str}, ...],
        'installments': [
            {
                'sequence': int,
                'label': str,
                'fee_heads': [{'id': int, 'name': str}, ...],
            },
            ...
        ],
    },
    ...
]
```

### `get_scholarship_applicable_total()`
Returns total amount eligible for scholarship/discount (float).

---

## Key Design Decisions

1. **Intake year = cohort year**, not the current calendar year. Fee lines span multiple academic years across all 8 semesters of a program.

2. **One fee structure per scope.** Only one structure per `(program, intake_year, batch)` combination. Batch-specific structures override the general program structure.

3. **Payment trigger on the line, not on the plan.** Standalone fees (Admission, University Reg) carry a `payment_trigger` directly on the fee line. Plan-managed fees leave it blank.

4. **Installment plan is semester-agnostic.** The same installment template applies to every semester — the billing module matches fee heads per semester.

5. **SQL UNIQUE on fee lines.** Since `payment_trigger` and schedule fields are no longer on the line, `UNIQUE(fee_structure_id, program_term_id, fee_head_id)` is enforced at the database level.

6. **Write locking by state.** Draft → fully editable. Active → financial/flag fields only. Closed → read-only.
