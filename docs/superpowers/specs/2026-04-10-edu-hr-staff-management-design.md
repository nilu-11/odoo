# edu_hr — Staff Management Module Design Spec

**Date**: 2026-04-10
**Module**: `edu_hr`
**Status**: Approved
**Author**: Innovax Solutions

---

## Overview

Extends Odoo's `hr.employee` with education-specific staff management — staff classification, academic qualifications, subject expertise, and direct integration with the classroom teaching ecosystem. Migrates all existing `teacher_id` references from `res.users` to `hr.employee` for a unified staff identity layer.

## Goals

1. Give every school staff member (teachers, lab assistants, librarians, admin, support) a rich profile built on `hr.employee`
2. Link teachers directly to classrooms, exams, attendance, and assessments via `hr.employee` instead of `res.users`
3. Provide workload visibility through smart buttons on the staff profile
4. Bridge `edu.department` (academic) to `hr.department` (organizational) without replacing either
5. Prepare the staff identity layer for future `edu_portal` teacher portal access

## Non-Goals

- Leave management / substitution tracking (future, depends on `edu_timetable`)
- Timetable or scheduling
- Portal user creation (handled by future `edu_portal`)
- Payroll integration
- Hard workload constraints / capacity blocking

---

## Models

### 1. `hr.employee` extension (in-place `_inherit`)

**File**: `edu_hr/models/hr_employee.py`

New fields added to `hr.employee`:

| Field | Type | Details |
|-------|------|---------|
| `is_teaching_staff` | Boolean | Default False. Filters teaching vs non-teaching staff |
| `staff_type` | Selection | `teacher`, `lab_assistant`, `librarian`, `admin_staff`, `support_staff`, `other` |
| `employee_code` | Char | Institution-specific staff ID (e.g. TCH-001). Auto-generated via sequence |
| `edu_department_id` | Many2one → `edu.department` | Academic department affiliation |
| `qualification_ids` | One2many → `edu.staff.qualification` | Academic qualifications |
| `subject_expertise_ids` | Many2many → `edu.subject` | Subjects the staff member can teach |
| `classroom_ids` | One2many → `edu.classroom` | Classrooms where this employee is the teacher (inverse of `teacher_id`) |
| `classroom_count` | Integer (computed, stored) | Count of active classrooms |
| `exam_paper_count` | Integer (computed) | Count of exam papers assigned |
| `assessment_record_count` | Integer (computed) | Count of assessment records |
| `attendance_register_count` | Integer (computed) | Count of attendance registers |

**Computed field logic**:
- `classroom_count`: `search_count` on `edu.classroom` where `teacher_id = self.id`
- `exam_paper_count`: `search_count` on `edu.exam.paper` where `teacher_id = self.id`
- `assessment_record_count`: `search_count` on `edu.continuous.assessment.record` where `teacher_id = self.id`
- `attendance_register_count`: `search_count` on `edu.attendance.register` where `teacher_id = self.id`

**Smart button actions**: Each count field has a corresponding `action_view_*` method that opens a filtered list view.

### 2. `edu.staff.qualification`

**File**: `edu_hr/models/edu_staff_qualification.py`

| Field | Type | Details |
|-------|------|---------|
| `employee_id` | Many2one → `hr.employee` | Required, ondelete='cascade' |
| `degree` | Char | Required. e.g. "B.Ed", "M.Sc Physics" |
| `institution` | Char | e.g. "Tribhuvan University" |
| `year_of_completion` | Integer | e.g. 2020 |
| `notes` | Text | Optional remarks |

### 3. `edu.department` extension

**File**: `edu_hr/models/edu_department.py`

| Field | Type | Details |
|-------|------|---------|
| `hr_department_id` | Many2one → `hr.department` | Optional link to HR organizational department |

### 4. `teacher_id` migration — inherited field overrides

Each file uses `_inherit` on the target model to redefine `teacher_id`:

**File**: `edu_hr/models/edu_classroom.py`
```python
class EduClassroom(models.Model):
    _inherit = 'edu.classroom'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
    )
```

**File**: `edu_hr/models/edu_exam_paper.py`
```python
class EduExamPaper(models.Model):
    _inherit = 'edu.exam.paper'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
    )
```

**File**: `edu_hr/models/edu_attendance.py`
Overrides on `edu.attendance.register` and `edu.attendance.sheet`:
- `register.teacher_id`: related from `classroom_id.teacher_id` (auto-follows new type)
- `sheet.teacher_id`: related from `register_id.teacher_id` (auto-follows)

> **Note**: Since these are `related` fields, they should auto-resolve the new comodel when `edu.classroom.teacher_id` changes. The explicit override file is defensive — if Odoo resolves them automatically at install, this file can be simplified to just the security rule domain updates.

**File**: `edu_hr/models/edu_continuous_assessment_record.py`
```python
class EduContinuousAssessmentRecord(models.Model):
    _inherit = 'edu.continuous.assessment.record'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        default=lambda self: self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        ),
        index=True,
        tracking=True,
    )
```

---

## Security

### Groups

No new security groups. The existing groups in `edu_classroom`, `edu_exam`, `edu_attendance`, and `edu_assessment` continue to work. Staff-level access uses Odoo's built-in `hr.group_hr_user` and `hr.group_hr_manager`.

### Record Rule Updates

All existing teacher-scoped record rules must update their domain from direct user match to employee traversal:

| Module | Rule | Old Domain | New Domain |
|--------|------|-----------|------------|
| `edu_classroom` | `rule_classroom_teacher_own` | `[('teacher_id', '=', user.id)]` | `[('teacher_id.user_id', '=', user.id)]` |
| `edu_exam` | `rule_exam_paper_teacher` | `[('teacher_id', '=', user.id)]` | `[('teacher_id.user_id', '=', user.id)]` |
| `edu_exam` | `rule_exam_marksheet_teacher` | `[('exam_paper_id.teacher_id', '=', user.id)]` | `[('exam_paper_id.teacher_id.user_id', '=', user.id)]` |
| `edu_attendance` | `rule_attendance_register_teacher_own` | `[('teacher_id', '=', user.id)]` | `[('teacher_id.user_id', '=', user.id)]` |
| `edu_attendance` | `rule_attendance_sheet_teacher_own` | `[('teacher_id', '=', user.id)]` | `[('teacher_id.user_id', '=', user.id)]` |
| `edu_attendance` | `rule_attendance_line_teacher_own` | `[('classroom_id.teacher_id', '=', user.id)]` | `[('classroom_id.teacher_id.user_id', '=', user.id)]` |
| `edu_assessment` | `rule_assessment_record_teacher` | `['|', ('teacher_id', '=', user.id), ('classroom_id.teacher_id', '=', user.id)]` | `['|', ('teacher_id.user_id', '=', user.id), ('classroom_id.teacher_id.user_id', '=', user.id)]` |

These overrides are defined in `edu_hr/security/security.xml` using the same `ir.rule` external IDs (with module prefix) to replace the originals at install time.

### Access Control (ir.model.access.csv)

| Model | Group | Read | Write | Create | Unlink |
|-------|-------|------|-------|--------|--------|
| `edu.staff.qualification` | `hr.group_hr_user` | 1 | 1 | 1 | 1 |
| `edu.staff.qualification` | `base.group_user` | 1 | 0 | 0 | 0 |

`hr.employee` access is already handled by Odoo's `hr` module.

---

## Views

### Staff Form View

Extends `hr.employee` form with new tabs and smart buttons:

**Smart buttons** (header area):
- Classrooms (count) → opens classroom list filtered to this employee
- Exam Papers (count) → opens exam paper list
- Assessments (count) → opens assessment record list
- Attendance (count) → opens attendance register list

**New page tabs** (added to existing employee form):
- **Education** tab: `staff_type`, `is_teaching_staff`, `employee_code`, `edu_department_id`
- **Qualifications** tab: inline editable list of `qualification_ids`
- **Subject Expertise** tab: `subject_expertise_ids` many2many tags widget

### Staff List View

Inherits `hr.employee` list, adds columns: `employee_code`, `staff_type`, `edu_department_id`, `classroom_count`

### Staff Search View

Inherits `hr.employee` search, adds:
- Filters: "Teaching Staff", "Non-Teaching Staff"
- Group by: `staff_type`, `edu_department_id`

### Classroom Form — Teacher Profile Button

Adds a smart button to `edu.classroom` form: "Teacher Profile" → opens the `teacher_id` employee record in form view. Visible only when `teacher_id` is set.

### Menu Structure

```
Staff Management (top-level menu, sequence after Examinations)
├── Staff                → all hr.employee records (uses edu-extended views)
├── Teaching Staff       → filtered: is_teaching_staff = True
├── Departments          → hr.department list/form
└── Configuration
    (reserved for future use)
```

---

## Module Structure

```
edu_hr/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── hr_employee.py
│   ├── edu_staff_qualification.py
│   ├── edu_department.py
│   ├── edu_classroom.py
│   ├── edu_exam_paper.py
│   ├── edu_attendance.py
│   └── edu_continuous_assessment_record.py
├── views/
│   ├── hr_employee_views.xml
│   ├── edu_classroom_views.xml
│   └── menu_views.xml
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
└── data/
    └── ir_sequence_data.xml
```

### Dependencies

```python
'depends': [
    'hr',
    'edu_academic_structure',
    'edu_classroom',
    'edu_exam',
    'edu_attendance',
    'edu_assessment',
],
```

### Install Position

After `edu_assessment` in the dependency chain. Does not affect `edu_result`, `edu_fees`, or `edu_fees_accounting` (they don't reference `teacher_id`).

---

## View/Domain Updates in Existing Modules (via _inherit)

These are changes that `edu_hr` applies to existing module views at install time:

### Classroom views
- `teacher_id` widget changes to show employee name/avatar
- "My Classrooms" filter domain: `[('teacher_id.user_id', '=', uid)]`
- "No Teacher Assigned" filter: `[('teacher_id', '=', False)]` (unchanged)
- Group by teacher (unchanged, just resolves to employee name)
- Kanban teacher display updated for employee avatar

### Exam views
- `teacher_id` in paper form/list resolves to employee
- "My Papers" filter domain update

### Attendance views
- Filters and group-by on teacher follow related field (auto-resolves)

### Assessment views
- `teacher_id` default logic updated to employee lookup
- "My Assessments" filter domain update

---

## Portal Forward Considerations

- `hr.employee` already has `user_id` (Many2one → res.users) — future `edu_portal` will use this to provision portal access for teaching staff
- Staff type classification enables role-based portal content (teachers see classrooms; non-teaching staff don't)
- Subject expertise can drive portal-side teacher directory features

---

## Data

### Sequence

- `ir.sequence` for `employee_code`: prefix `TCH/`, padding 4, e.g. `TCH/0001`
- Auto-assigned on create if `is_teaching_staff` is True and `employee_code` is empty

---

## Testing Notes

Manual testing checklist (no automated tests):

1. Create an `hr.employee` with `is_teaching_staff = True` — verify employee_code auto-generates
2. Add qualifications and subject expertise — verify save/display
3. Assign employee as `teacher_id` on a classroom — verify smart button counts update
4. Open classroom form — verify "Teacher Profile" button navigates correctly
5. Log in as the teacher's `user_id` — verify "My Classrooms" filter shows correct classrooms
6. Verify exam paper, attendance, assessment teacher assignment works with employee selection
7. Verify record rules: teacher user sees only their own records across all modules
8. Create non-teaching staff — verify they don't appear in classroom teacher dropdowns (optional: domain filter)
