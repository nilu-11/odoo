# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Odoo 19 Education Management Information System (EMIS)** — 14 tightly integrated custom modules for comprehensive school/college management, authored by Innovax Solutions.

## Running & Installing Modules

There is no Makefile or test runner. All workflows use the Odoo CLI directly.

```bash
# Install one or more modules (add -u to update instead of install)
odoo -d <database> -i edu_academic_structure
odoo -d <database> -u edu_fees,edu_fees_accounting

# Install the full EMIS suite (order matters — install dependencies first)
odoo -d <database> -i edu_academic_structure,edu_pre_admission_crm,edu_fees_structure,edu_admission,edu_student,edu_enrollment,edu_academic_progression,edu_classroom,edu_attendance,edu_exam,edu_assessment,edu_result,edu_fees,edu_fees_accounting
```

**Testing** is manual, documented in `TESTING_PLAN.md` (62 KB). There are no automated tests (`test_*.py`). The plan covers all 14 modules plus integration tests; test cases must be run in module dependency order since earlier modules produce master data required by later ones.

**Linting**: `.ruff_cache/` is gitignored, so `ruff` is the expected linter:
```bash
ruff check .
```

## Module Dependency Order

Modules must be installed in this order (each depends on those above it):

```
edu_academic_structure          ← foundation (academic years, terms, programs, batches, sections, subjects)
edu_pre_admission_crm           ← CRM-driven applicant pipeline
edu_fees_structure              ← fee heads, structures, payment plan templates
edu_admission                   ← formal applications, scholarships, offer letters
edu_student                     ← long-term student identity record
edu_enrollment                  ← bridges admission → student; snapshots academic & financial context
edu_academic_progression        ← student placement history, batch promotion wizard
edu_classroom                   ← section×subject×term hub; anchor for attendance/exams/assessments
edu_attendance                  ← register/sheet/line; session-based; configurable thresholds
edu_exam                        ← sessions, papers, marksheets, raw marks, back exam wizard
edu_assessment                  ← continuous assessment; bulk generate/lock wizards
edu_result                      ← scheme-driven result engine; GPA/%, grading tables, backlog
edu_fees                        ← student fee plans, dues, payments, enrollment fee blocking
edu_fees_accounting             ← Odoo Accounting bridge: invoices, credit notes, deposits
```

## Architecture & Key Patterns

### Snapshot Pattern
Data is copied and frozen at key lifecycle transitions to preserve historical accuracy:
- **Admission → Enrollment**: academic placement (program, batch, section, term) and financial context (fee structure, scholarship amounts) are snapshotted on the enrollment record.
- **Enrollment → Student**: student identity is created from the enrollment snapshot.
- Never modify snapshotted fields directly — update the source record before the transition occurs.

### State Machine + Field Locking
Most models use `state = fields.Selection(...)` (typically `draft → active/confirmed → closed/done`). Fields that must not change after confirmation are listed in `_FROZEN_FIELDS` or protected by `_LOCKED_STATES`. Write attempts to locked fields raise `UserError`.

### Mail Thread Inheritance
Nearly all models inherit `['mail.thread', 'mail.activity.mixin']` for chatter, activity tracking, and audit trails. Always include this in new stateful models.

### Referential Integrity
Relational fields use `ondelete='restrict'` by default throughout — deleting a parent record that has children will raise an error. This is intentional.

### Classroom as Anchor
`edu.classroom` (a Section × Subject × Term combination) is the central anchor for attendance sheets, exam papers, assessment records, and result computation. Most downstream operations start by selecting a classroom.

### Result Engine
`edu_result` consumes data from three upstream sources: `edu_exam` (raw marks), `edu_assessment` (continuous assessment marks), and `edu_attendance` (attendance percentage). Result schemes define how these are weighted.

### Fee Blocking
`edu_fees` can block enrollment or other actions when outstanding dues exist. A manager override flag exists to bypass this when needed.

### Accounting Bridge
`edu_fees_accounting` is a strict Odoo Accounting integration layer — it generates `account.move` (invoices/credit notes) from fee dues. Keep fee logic in `edu_fees`; only put accounting journal entries in `edu_fees_accounting`.

## Per-Module File Layout

```
edu_<name>/
├── __manifest__.py
├── models/
│   └── edu_*.py          # one model per file
├── views/
│   ├── edu_*_views.xml   # one view file per model
│   └── menu_views.xml
├── security/
│   ├── security.xml       # groups + record rules
│   └── ir.model.access.csv
├── data/                  # sequences, cron jobs, master data (optional)
├── report/                # QWeb report actions + templates (admission, exam, assessment, result)
└── wizards/               # transient models for multi-step ops (progression, exam, assessment, result)
```

## Security Groups

| Group | Scope |
|---|---|
| `group_education_admin` | Full CRUD across all modules |
| `group_academic_officer` | CRUD on academic records |
| `group_academic_viewer` | Read-only academic access |
| `group_fees_officer` | CRUD on fee records |
| `group_fees_viewer` | Read-only fee access |
| `group_exam_teacher` | Scoped to own classrooms (exam) |
| `group_assessment_teacher` | Scoped to own classrooms (assessment) |
| `group_attendance_teacher` | Scoped to own classrooms (attendance) |
| `group_result_admin` | Full result management |

Record rules further scope teacher-role groups to their own classrooms only.

## Model Field Organization Convention

Model files use visual section separators:

```python
# ═══ Identity / Core Fields ═══
# ═══ Relational Fields ═══
# ═══ State & Lifecycle ═══
# ═══ Computed / Stored ═══
# ═══ Methods / Constraints ═══
```

## Commit Standards

Follow conventional commits (see `CONTRIBUTING.md`):
- `feat(module):` — new functionality
- `fix(module):` — bug fixes
- `chore:` — maintenance, config, gitignore
- `docs:` — documentation only

Do not commit: `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `.vscode/`, `.claude/worktrees/`, `*.log`.
