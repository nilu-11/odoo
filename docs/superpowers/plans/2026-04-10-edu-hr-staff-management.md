# edu_hr — Staff Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `edu_hr` module that extends `hr.employee` with education-specific staff management and migrates all `teacher_id` fields from `res.users` to `hr.employee` across classroom, exam, attendance, and assessment modules.

**Architecture:** In-place `_inherit` on `hr.employee` adds staff classification, qualifications, and subject expertise. Separate `_inherit` files override `teacher_id` on four downstream models. Security record rules update domains from `teacher_id = user.id` to `teacher_id.user_id = user.id`. View XML inherits update filters and actions.

**Tech Stack:** Odoo 19, Python 3, XML (views/security/data)

**Spec:** `docs/superpowers/specs/2026-04-10-edu-hr-staff-management-design.md`

---

## File Structure

```
edu_hr/
├── __manifest__.py                              # Module metadata and dependencies
├── __init__.py                                  # Package init → models
├── models/
│   ├── __init__.py                              # Import all model files
│   ├── hr_employee.py                           # Extend hr.employee with edu fields + workload
│   ├── edu_staff_qualification.py               # edu.staff.qualification model
│   ├── edu_department.py                        # Add hr_department_id to edu.department
│   ├── edu_classroom.py                         # Override teacher_id → hr.employee
│   ├── edu_exam_paper.py                        # Override teacher_id → hr.employee
│   ├── edu_attendance.py                        # Override teacher_id on register + sheet
│   └── edu_continuous_assessment_record.py      # Override teacher_id → hr.employee
├── views/
│   ├── hr_employee_views.xml                    # Staff form/list/search extensions
│   ├── edu_classroom_views.xml                  # View inherits for teacher_id migration
│   ├── edu_exam_paper_views.xml                 # View inherits for teacher_id migration
│   ├── edu_attendance_views.xml                 # View inherits for teacher_id migration
│   ├── edu_assessment_views.xml                 # View inherits for teacher_id migration
│   └── menu_views.xml                           # Staff Management menu tree
├── security/
│   ├── security.xml                             # Override record rules for teacher domains
│   └── ir.model.access.csv                      # ACL for edu.staff.qualification
└── data/
    └── ir_sequence_data.xml                     # Employee code sequence
```

---

### Task 1: Module Scaffold

**Files:**
- Create: `edu_hr/__manifest__.py`
- Create: `edu_hr/__init__.py`
- Create: `edu_hr/models/__init__.py`

- [ ] **Step 1: Create `__manifest__.py`**

```python
{
    'name': 'Education: Staff Management',
    'version': '19.0.1.0.0',
    'summary': 'Teacher and staff profiles — extends hr.employee with education-specific fields and classroom integration.',
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'edu_academic_structure',
        'edu_classroom',
        'edu_exam',
        'edu_attendance',
        'edu_assessment',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/hr_employee_views.xml',
        'views/edu_classroom_views.xml',
        'views/edu_exam_paper_views.xml',
        'views/edu_attendance_views.xml',
        'views/edu_assessment_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
```

- [ ] **Step 2: Create `__init__.py`**

```python
from . import models
```

- [ ] **Step 3: Create `models/__init__.py`**

```python
from . import hr_employee
from . import edu_staff_qualification
from . import edu_department
from . import edu_classroom
from . import edu_exam_paper
from . import edu_attendance
from . import edu_continuous_assessment_record
```

- [ ] **Step 4: Commit scaffold**

```bash
cd /opt/custom_addons/education
git add edu_hr/__manifest__.py edu_hr/__init__.py edu_hr/models/__init__.py
git commit -m "feat(edu_hr): scaffold module with manifest and init files"
```

---

### Task 2: Core Staff Model — `hr.employee` Extension

**Files:**
- Create: `edu_hr/models/hr_employee.py`

- [ ] **Step 1: Create `hr_employee.py`**

```python
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ═══ Staff Classification ═══

    is_teaching_staff = fields.Boolean(
        string='Is Teaching Staff',
        default=False,
        tracking=True,
        help='Enable for teachers and instructors who are assigned to classrooms.',
    )
    staff_type = fields.Selection(
        selection=[
            ('teacher', 'Teacher'),
            ('lab_assistant', 'Lab Assistant'),
            ('librarian', 'Librarian'),
            ('admin_staff', 'Administrative Staff'),
            ('support_staff', 'Support Staff'),
            ('other', 'Other'),
        ],
        string='Staff Type',
        tracking=True,
    )
    employee_code = fields.Char(
        string='Employee Code',
        copy=False,
        tracking=True,
        help='Institution-specific staff identifier. Auto-generated for teaching staff.',
    )

    # ═══ Academic Profile ═══

    edu_department_id = fields.Many2one(
        comodel_name='edu.department',
        string='Academic Department',
        ondelete='set null',
        tracking=True,
        help='The academic department this staff member belongs to.',
    )
    qualification_ids = fields.One2many(
        comodel_name='edu.staff.qualification',
        inverse_name='employee_id',
        string='Qualifications',
    )
    subject_expertise_ids = fields.Many2many(
        comodel_name='edu.subject',
        relation='hr_employee_edu_subject_rel',
        column1='employee_id',
        column2='subject_id',
        string='Subject Expertise',
        help='Subjects this staff member is qualified to teach.',
    )

    # ═══ Workload (Computed) ═══

    classroom_ids = fields.One2many(
        comodel_name='edu.classroom',
        inverse_name='teacher_id',
        string='Classrooms',
    )
    classroom_count = fields.Integer(
        string='Classrooms',
        compute='_compute_classroom_count',
        store=True,
    )
    exam_paper_count = fields.Integer(
        string='Exam Papers',
        compute='_compute_exam_paper_count',
    )
    assessment_record_count = fields.Integer(
        string='Assessments',
        compute='_compute_assessment_record_count',
    )
    attendance_register_count = fields.Integer(
        string='Attendance Registers',
        compute='_compute_attendance_register_count',
    )

    # ═══ Computed Methods ═══

    @api.depends('classroom_ids')
    def _compute_classroom_count(self):
        for rec in self:
            rec.classroom_count = len(rec.classroom_ids)

    def _compute_exam_paper_count(self):
        for rec in self:
            if rec.id:
                rec.exam_paper_count = self.env['edu.exam.paper'].search_count(
                    [('teacher_id', '=', rec.id)]
                )
            else:
                rec.exam_paper_count = 0

    def _compute_assessment_record_count(self):
        for rec in self:
            if rec.id:
                rec.assessment_record_count = self.env[
                    'edu.continuous.assessment.record'
                ].search_count([('teacher_id', '=', rec.id)])
            else:
                rec.assessment_record_count = 0

    def _compute_attendance_register_count(self):
        for rec in self:
            if rec.id:
                rec.attendance_register_count = self.env[
                    'edu.attendance.register'
                ].search_count([('teacher_id', '=', rec.id)])
            else:
                rec.attendance_register_count = 0

    # ═══ Smart Button Actions ═══

    def action_view_classrooms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Classrooms — %s' % self.name,
            'res_model': 'edu.classroom',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
            'context': {'default_teacher_id': self.id},
        }

    def action_view_exam_papers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exam Papers — %s' % self.name,
            'res_model': 'edu.exam.paper',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
        }

    def action_view_assessment_records(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assessments — %s' % self.name,
            'res_model': 'edu.continuous.assessment.record',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
        }

    def action_view_attendance_registers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attendance Registers — %s' % self.name,
            'res_model': 'edu.attendance.register',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
        }

    # ═══ Auto-generate Employee Code ═══

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_teaching_staff') and not vals.get('employee_code'):
                vals['employee_code'] = self.env['ir.sequence'].next_by_code(
                    'edu.employee.code'
                ) or ''
        return super().create(vals_list)
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/hr_employee.py
git commit -m "feat(edu_hr): extend hr.employee with staff classification and workload"
```

---

### Task 3: Qualification Model

**Files:**
- Create: `edu_hr/models/edu_staff_qualification.py`

- [ ] **Step 1: Create `edu_staff_qualification.py`**

```python
from odoo import fields, models


class EduStaffQualification(models.Model):
    _name = 'edu.staff.qualification'
    _description = 'Staff Qualification'
    _order = 'year_of_completion desc, degree'

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    degree = fields.Char(
        string='Degree',
        required=True,
        help='e.g. B.Ed, M.Sc Physics, PhD Mathematics',
    )
    institution = fields.Char(
        string='Institution',
        help='e.g. Tribhuvan University',
    )
    year_of_completion = fields.Integer(
        string='Year',
        help='Year of completion, e.g. 2020',
    )
    notes = fields.Text(
        string='Notes',
    )
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/edu_staff_qualification.py
git commit -m "feat(edu_hr): add edu.staff.qualification model"
```

---

### Task 4: Department Link

**Files:**
- Create: `edu_hr/models/edu_department.py`

- [ ] **Step 1: Create `edu_department.py`**

```python
from odoo import fields, models


class EduDepartment(models.Model):
    _inherit = 'edu.department'

    hr_department_id = fields.Many2one(
        comodel_name='hr.department',
        string='HR Department',
        ondelete='set null',
        help='Optional link to the corresponding HR organizational department.',
    )
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/edu_department.py
git commit -m "feat(edu_hr): link edu.department to hr.department"
```

---

### Task 5: Teacher ID Migration — Classroom

**Files:**
- Create: `edu_hr/models/edu_classroom.py`

This is the critical migration. The existing `edu_classroom/models/edu_classroom.py` has `teacher_id = fields.Many2one('res.users', ...)` at line 146. We override it via `_inherit`.

- [ ] **Step 1: Create `edu_hr/models/edu_classroom.py`**

```python
from odoo import fields, models


class EduClassroom(models.Model):
    _inherit = 'edu.classroom'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        index=True,
        domain="[('is_teaching_staff', '=', True)]",
    )
```

**What this changes:**
- `edu_classroom/models/edu_classroom.py:146-152` — comodel changes from `res.users` to `hr.employee`
- `edu_exam/models/edu_classroom.py:62` — `default_teacher_id` context still passes `self.teacher_id.id` (works with hr.employee)
- `edu_classroom/models/edu_classroom.py:422` — `_ensure_attendance_register` passes `self.teacher_id.id` (works unchanged since register's teacher_id will also be hr.employee)
- The `_ALWAYS_UNLOCKED` set already includes `teacher_id` — no change needed

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/edu_classroom.py
git commit -m "feat(edu_hr): migrate classroom teacher_id to hr.employee"
```

---

### Task 6: Teacher ID Migration — Exam Paper

**Files:**
- Create: `edu_hr/models/edu_exam_paper.py`

The existing `edu_exam/models/edu_exam_paper.py` has `teacher_id = fields.Many2one('res.users', ...)` at line 82-87. The `_onchange_classroom_id` at line 280-281 sets `self.teacher_id = self.classroom_id.teacher_id` — since both will now be `hr.employee`, this works unchanged.

- [ ] **Step 1: Create `edu_hr/models/edu_exam_paper.py`**

```python
from odoo import fields, models


class EduExamPaper(models.Model):
    _inherit = 'edu.exam.paper'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        domain="[('is_teaching_staff', '=', True)]",
    )
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/edu_exam_paper.py
git commit -m "feat(edu_hr): migrate exam paper teacher_id to hr.employee"
```

---

### Task 7: Teacher ID Migration — Attendance

**Files:**
- Create: `edu_hr/models/edu_attendance.py`

The existing fields:
- `edu_attendance/models/edu_attendance_register.py:76-82`: `teacher_id = fields.Many2one('res.users', related='classroom_id.teacher_id', store=True)`
- `edu_attendance/models/edu_attendance_sheet.py:88-94`: `teacher_id = fields.Many2one('res.users', related='register_id.teacher_id', store=True)`

Since these are `related` fields pointing to `classroom_id.teacher_id` and `register_id.teacher_id` respectively, they should auto-resolve when the source field changes to `hr.employee`. However, the explicit `comodel_name='res.users'` declaration will conflict. We must override to match.

- [ ] **Step 1: Create `edu_hr/models/edu_attendance.py`**

```python
from odoo import fields, models


class EduAttendanceRegister(models.Model):
    _inherit = 'edu.attendance.register'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        related='classroom_id.teacher_id',
        store=True,
        index=True,
    )


class EduAttendanceSheet(models.Model):
    _inherit = 'edu.attendance.sheet'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        related='register_id.teacher_id',
        store=True,
        index=True,
    )
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/edu_attendance.py
git commit -m "feat(edu_hr): migrate attendance teacher_id to hr.employee"
```

---

### Task 8: Teacher ID Migration — Assessment

**Files:**
- Create: `edu_hr/models/edu_continuous_assessment_record.py`

The existing `edu_assessment/models/edu_continuous_assessment_record.py` has:
- Line 153-159: `teacher_id = fields.Many2one('res.users', default=lambda self: self.env.user, ...)`
- Line 224-225: `create()` override: `vals.setdefault('teacher_id', self.env.user.id)` — **must be updated**
- Line 300-301: `_onchange_classroom_id`: `self.teacher_id = cl.teacher_id or self.env.user` — **must be updated**

The `create()` and `_onchange_classroom_id` methods are in the original file. We override them in our `_inherit` to use `hr.employee` lookup.

- [ ] **Step 1: Create `edu_hr/models/edu_continuous_assessment_record.py`**

```python
from odoo import api, fields, models


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
        domain="[('is_teaching_staff', '=', True)]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override to set teacher_id default as hr.employee instead of res.users."""
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        for vals in vals_list:
            if not vals.get('teacher_id') and employee:
                vals.setdefault('teacher_id', employee.id)
        return super().create(vals_list)

    @api.onchange('classroom_id')
    def _onchange_classroom_id(self):
        """Override to use hr.employee for teacher auto-population."""
        if self.classroom_id:
            cl = self.classroom_id
            self.section_id = cl.section_id
            self.batch_id = cl.batch_id
            self.program_term_id = cl.program_term_id
            self.curriculum_line_id = cl.curriculum_line_id
            self.subject_id = cl.subject_id
            # Auto-populate teacher from classroom
            current_employee = self.env['hr.employee'].search(
                [('user_id', '=', self.env.uid)], limit=1
            )
            if not self.teacher_id or self.teacher_id == current_employee:
                self.teacher_id = cl.teacher_id or current_employee
            # Derive academic_year from program_term if available
            if cl.program_term_id and cl.program_term_id.academic_year_id:
                self.academic_year_id = cl.program_term_id.academic_year_id
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/models/edu_continuous_assessment_record.py
git commit -m "feat(edu_hr): migrate assessment teacher_id to hr.employee"
```

---

### Task 9: Security — Record Rule Overrides

**Files:**
- Create: `edu_hr/security/security.xml`
- Create: `edu_hr/security/ir.model.access.csv`

All existing teacher record rules use `[('teacher_id', '=', user.id)]`. Since `teacher_id` now points to `hr.employee` (not `res.users`), we must update to `[('teacher_id.user_id', '=', user.id)]`.

We override the existing rules by referencing their full external IDs.

- [ ] **Step 1: Create `security.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Record Rule Overrides
         teacher_id now points to hr.employee; domains must
         traverse teacher_id.user_id to match the logged-in user.
    ══════════════════════════════════════════════════════ -->

    <!-- ── Classroom ─────────────────────────────────────── -->
    <record id="edu_classroom.rule_classroom_teacher_own" model="ir.rule">
        <field name="name">Classroom: teacher sees own classrooms only</field>
        <field name="model_id" ref="edu_classroom.model_edu_classroom"/>
        <field name="domain_force">[('teacher_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('edu_classroom.group_classroom_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <!-- ── Exam Paper ────────────────────────────────────── -->
    <record id="edu_exam.rule_exam_paper_teacher" model="ir.rule">
        <field name="name">Exam Paper: Teacher sees own papers</field>
        <field name="model_id" ref="edu_exam.model_edu_exam_paper"/>
        <field name="domain_force">[('teacher_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('edu_exam.group_exam_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <!-- ── Exam Marksheet ────────────────────────────────── -->
    <record id="edu_exam.rule_exam_marksheet_teacher" model="ir.rule">
        <field name="name">Marksheet: Teacher sees own paper marksheets</field>
        <field name="model_id" ref="edu_exam.model_edu_exam_marksheet"/>
        <field name="domain_force">[('exam_paper_id.teacher_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('edu_exam.group_exam_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <!-- ── Attendance Register ───────────────────────────── -->
    <record id="edu_attendance.rule_attendance_register_teacher_own" model="ir.rule">
        <field name="name">Attendance Register: teacher sees own classrooms only</field>
        <field name="model_id" ref="edu_attendance.model_edu_attendance_register"/>
        <field name="domain_force">[('teacher_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('edu_attendance.group_attendance_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <!-- ── Attendance Sheet ──────────────────────────────── -->
    <record id="edu_attendance.rule_attendance_sheet_teacher_own" model="ir.rule">
        <field name="name">Attendance Sheet: teacher sees own classrooms only</field>
        <field name="model_id" ref="edu_attendance.model_edu_attendance_sheet"/>
        <field name="domain_force">[('teacher_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('edu_attendance.group_attendance_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <!-- ── Attendance Line ───────────────────────────────── -->
    <record id="edu_attendance.rule_attendance_line_teacher_own" model="ir.rule">
        <field name="name">Attendance Line: teacher sees own classrooms only</field>
        <field name="model_id" ref="edu_attendance.model_edu_attendance_sheet_line"/>
        <field name="domain_force">[('classroom_id.teacher_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('edu_attendance.group_attendance_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <!-- ── Assessment Record ─────────────────────────────── -->
    <record id="edu_assessment.rule_assessment_record_teacher" model="ir.rule">
        <field name="name">Assessment Record: Teacher sees own classroom</field>
        <field name="model_id" ref="edu_assessment.model_edu_continuous_assessment_record"/>
        <field name="domain_force">
            ['|',
              ('teacher_id.user_id', '=', user.id),
              ('classroom_id.teacher_id.user_id', '=', user.id)]
        </field>
        <field name="groups" eval="[(4, ref('edu_assessment.group_assessment_teacher'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="False"/>
    </record>
</odoo>
```

- [ ] **Step 2: Create `ir.model.access.csv`**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_edu_staff_qualification_hr_user,edu.staff.qualification hr user,model_edu_staff_qualification,hr.group_hr_user,1,1,1,1
access_edu_staff_qualification_user,edu.staff.qualification base user,model_edu_staff_qualification,base.group_user,1,0,0,0
```

- [ ] **Step 3: Commit**

```bash
git add edu_hr/security/security.xml edu_hr/security/ir.model.access.csv
git commit -m "feat(edu_hr): override teacher record rules for hr.employee domains"
```

---

### Task 10: Sequence Data

**Files:**
- Create: `edu_hr/data/ir_sequence_data.xml`

- [ ] **Step 1: Create `ir_sequence_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="seq_edu_employee_code" model="ir.sequence">
        <field name="name">Education Employee Code</field>
        <field name="code">edu.employee.code</field>
        <field name="prefix">TCH/</field>
        <field name="padding">4</field>
        <field name="company_id" eval="False"/>
    </record>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/data/ir_sequence_data.xml
git commit -m "feat(edu_hr): add employee code sequence"
```

---

### Task 11: Staff Views — Form, List, Search

**Files:**
- Create: `edu_hr/views/hr_employee_views.xml`

- [ ] **Step 1: Create `hr_employee_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         hr.employee — Form View Extension
    ══════════════════════════════════════════════════════ -->
    <record id="view_hr_employee_form_edu" model="ir.ui.view">
        <field name="name">hr.employee.form.edu</field>
        <field name="model">hr.employee</field>
        <field name="inherit_id" ref="hr.view_employee_form"/>
        <field name="arch" type="xml">
            <!-- Smart buttons -->
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_view_classrooms"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-chalkboard"
                        invisible="not is_teaching_staff">
                    <field name="classroom_count"
                           widget="statinfo"
                           string="Classrooms"/>
                </button>
                <button name="action_view_exam_papers"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-file-text-o"
                        invisible="not is_teaching_staff">
                    <field name="exam_paper_count"
                           widget="statinfo"
                           string="Exam Papers"/>
                </button>
                <button name="action_view_assessment_records"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-pencil-square-o"
                        invisible="not is_teaching_staff">
                    <field name="assessment_record_count"
                           widget="statinfo"
                           string="Assessments"/>
                </button>
                <button name="action_view_attendance_registers"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-calendar-check-o"
                        invisible="not is_teaching_staff">
                    <field name="attendance_register_count"
                           widget="statinfo"
                           string="Attendance"/>
                </button>
            </xpath>

            <!-- Education tab in the notebook -->
            <xpath expr="//notebook" position="inside">
                <page string="Education" name="education">
                    <group>
                        <group string="Staff Classification">
                            <field name="employee_code"/>
                            <field name="staff_type"/>
                            <field name="is_teaching_staff"/>
                        </group>
                        <group string="Academic Affiliation">
                            <field name="edu_department_id"/>
                        </group>
                    </group>
                </page>
                <page string="Qualifications" name="qualifications">
                    <field name="qualification_ids">
                        <list editable="bottom">
                            <field name="degree"/>
                            <field name="institution"/>
                            <field name="year_of_completion"/>
                            <field name="notes"/>
                        </list>
                    </field>
                </page>
                <page string="Subject Expertise" name="subject_expertise"
                      invisible="not is_teaching_staff">
                    <field name="subject_expertise_ids" widget="many2many_tags"/>
                </page>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         hr.employee — List View Extension
    ══════════════════════════════════════════════════════ -->
    <record id="view_hr_employee_list_edu" model="ir.ui.view">
        <field name="name">hr.employee.list.edu</field>
        <field name="model">hr.employee</field>
        <field name="inherit_id" ref="hr.view_employee_tree"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='name']" position="after">
                <field name="employee_code" optional="show"/>
                <field name="staff_type" optional="show"/>
                <field name="edu_department_id" optional="show"/>
                <field name="classroom_count" string="Classrooms" optional="hide"/>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         hr.employee — Search View Extension
    ══════════════════════════════════════════════════════ -->
    <record id="view_hr_employee_search_edu" model="ir.ui.view">
        <field name="name">hr.employee.search.edu</field>
        <field name="model">hr.employee</field>
        <field name="inherit_id" ref="hr.view_employee_filter"/>
        <field name="arch" type="xml">
            <xpath expr="//search" position="inside">
                <field name="employee_code"/>
                <field name="edu_department_id"/>
                <separator/>
                <filter name="filter_teaching_staff"
                        string="Teaching Staff"
                        domain="[('is_teaching_staff', '=', True)]"/>
                <filter name="filter_non_teaching_staff"
                        string="Non-Teaching Staff"
                        domain="[('is_teaching_staff', '=', False)]"/>
                <separator/>
                <filter name="group_staff_type"
                        string="Staff Type"
                        context="{'group_by': 'staff_type'}"/>
                <filter name="group_edu_department"
                        string="Academic Department"
                        context="{'group_by': 'edu_department_id'}"/>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Window Actions
    ══════════════════════════════════════════════════════ -->

    <!-- All Staff -->
    <record id="action_edu_staff_all" model="ir.actions.act_window">
        <field name="name">Staff</field>
        <field name="res_model">hr.employee</field>
        <field name="view_mode">list,kanban,form</field>
        <field name="context">{}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No staff members found.
            </p>
            <p>
                Create staff records for teachers, lab assistants, and other school personnel.
            </p>
        </field>
    </record>

    <!-- Teaching Staff Only -->
    <record id="action_edu_teaching_staff" model="ir.actions.act_window">
        <field name="name">Teaching Staff</field>
        <field name="res_model">hr.employee</field>
        <field name="view_mode">list,kanban,form</field>
        <field name="domain">[('is_teaching_staff', '=', True)]</field>
        <field name="context">{'default_is_teaching_staff': True, 'search_default_filter_teaching_staff': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No teaching staff found.
            </p>
            <p>
                Create teacher records and assign them to classrooms.
            </p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/views/hr_employee_views.xml
git commit -m "feat(edu_hr): add staff form, list, and search view extensions"
```

---

### Task 12: View Overrides — Classroom

**Files:**
- Create: `edu_hr/views/edu_classroom_views.xml`

The existing classroom views use `teacher_id` with `many2one_avatar_user` widget (kanban) and `uid`-based filter domains. We need to:
1. Update the kanban avatar widget from `many2one_avatar_user` to `many2one_avatar_employee`
2. Update "My Classrooms" filter domain to traverse `teacher_id.user_id`
3. Update the "My Classrooms" window action domain
4. Add a "Teacher Profile" smart button

- [ ] **Step 1: Create `edu_hr/views/edu_classroom_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Classroom — Search View: update "My Classrooms" filter
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_classroom_search_hr" model="ir.ui.view">
        <field name="name">edu.classroom.search.hr</field>
        <field name="model">edu.classroom</field>
        <field name="inherit_id" ref="edu_classroom.view_edu_classroom_search"/>
        <field name="arch" type="xml">
            <xpath expr="//filter[@name='filter_my_classrooms']" position="attributes">
                <attribute name="domain">[('teacher_id.user_id', '=', uid)]</attribute>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Classroom — Kanban View: update teacher avatar widget
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_classroom_kanban_hr" model="ir.ui.view">
        <field name="name">edu.classroom.kanban.hr</field>
        <field name="model">edu.classroom</field>
        <field name="inherit_id" ref="edu_classroom.view_edu_classroom_kanban"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='teacher_id'][@widget='many2one_avatar_user']" position="attributes">
                <attribute name="widget">many2one_avatar_employee</attribute>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Classroom — Form View: add Teacher Profile smart button
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_classroom_form_hr" model="ir.ui.view">
        <field name="name">edu.classroom.form.hr</field>
        <field name="model">edu.classroom</field>
        <field name="inherit_id" ref="edu_classroom.view_edu_classroom_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_view_teacher_profile"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-id-card"
                        invisible="not teacher_id"
                        string="Teacher Profile"/>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Update "My Classrooms" window action domain
    ══════════════════════════════════════════════════════ -->
    <record id="edu_classroom.action_edu_classroom_mine" model="ir.actions.act_window">
        <field name="name">My Classrooms</field>
        <field name="res_model">edu.classroom</field>
        <field name="view_mode">kanban,list,form</field>
        <field name="domain">[('teacher_id.user_id', '=', uid)]</field>
        <field name="context">{'search_default_filter_my_classrooms': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No classrooms assigned to you yet.
            </p>
            <p>
                Classrooms will appear here once an administrator assigns
                you as the teacher.
            </p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Add `action_view_teacher_profile` method to `edu_hr/models/edu_classroom.py`**

Update the file created in Task 5:

```python
from odoo import fields, models


class EduClassroom(models.Model):
    _inherit = 'edu.classroom'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        index=True,
        domain="[('is_teaching_staff', '=', True)]",
    )

    def action_view_teacher_profile(self):
        """Open the teacher's staff profile form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teacher Profile',
            'res_model': 'hr.employee',
            'view_mode': 'form',
            'res_id': self.teacher_id.id,
        }
```

- [ ] **Step 3: Commit**

```bash
git add edu_hr/views/edu_classroom_views.xml edu_hr/models/edu_classroom.py
git commit -m "feat(edu_hr): update classroom views for hr.employee teacher"
```

---

### Task 13: View Overrides — Exam Paper

**Files:**
- Create: `edu_hr/views/edu_exam_paper_views.xml`

Existing views to update:
- Search filter "My Papers" at `edu_exam/views/edu_exam_paper_views.xml:17`: `domain="[('teacher_id', '=', uid)]"`
- Window action "My Papers" at line 240: `domain=[('teacher_id', '=', uid)]`
- Context at line 207 in assessment: `'default_teacher_id': uid` — this will no longer work since teacher_id is now hr.employee. We handle this in the assessment views task.

- [ ] **Step 1: Create `edu_hr/views/edu_exam_paper_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Exam Paper — Search View: update "My Papers" filter
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_exam_paper_search_hr" model="ir.ui.view">
        <field name="name">edu.exam.paper.search.hr</field>
        <field name="model">edu.exam.paper</field>
        <field name="inherit_id" ref="edu_exam.view_edu_exam_paper_search"/>
        <field name="arch" type="xml">
            <xpath expr="//filter[@name='filter_my_papers']" position="attributes">
                <attribute name="domain">[('teacher_id.user_id', '=', uid)]</attribute>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Update "My Papers" window action domain
    ══════════════════════════════════════════════════════ -->
    <record id="edu_exam.action_edu_exam_paper_mine" model="ir.actions.act_window">
        <field name="name">My Papers</field>
        <field name="res_model">edu.exam.paper</field>
        <field name="view_mode">list,form</field>
        <field name="domain">[('teacher_id.user_id', '=', uid)]</field>
        <field name="context">{'search_default_filter_my_papers': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No exam papers assigned to you.
            </p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/views/edu_exam_paper_views.xml
git commit -m "feat(edu_hr): update exam paper views for hr.employee teacher"
```

---

### Task 14: View Overrides — Attendance

**Files:**
- Create: `edu_hr/views/edu_attendance_views.xml`

Existing views to update:
- Register search "My Registers": `domain="[('teacher_id', '=', uid)]"`
- Sheet search "My Sheets": `domain="[('teacher_id', '=', uid)]"`
- Sheet window action "My Attendance Sheets": `domain=[('teacher_id', '=', uid)]`

- [ ] **Step 1: Create `edu_hr/views/edu_attendance_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Attendance Register — Search: update "My Registers"
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_attendance_register_search_hr" model="ir.ui.view">
        <field name="name">edu.attendance.register.search.hr</field>
        <field name="model">edu.attendance.register</field>
        <field name="inherit_id" ref="edu_attendance.view_edu_attendance_register_search"/>
        <field name="arch" type="xml">
            <xpath expr="//filter[@name='filter_my_registers']" position="attributes">
                <attribute name="domain">[('teacher_id.user_id', '=', uid)]</attribute>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Attendance Sheet — Search: update "My Sheets"
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_attendance_sheet_search_hr" model="ir.ui.view">
        <field name="name">edu.attendance.sheet.search.hr</field>
        <field name="model">edu.attendance.sheet</field>
        <field name="inherit_id" ref="edu_attendance.view_edu_attendance_sheet_search"/>
        <field name="arch" type="xml">
            <xpath expr="//filter[@name='filter_my_sheets']" position="attributes">
                <attribute name="domain">[('teacher_id.user_id', '=', uid)]</attribute>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Update "My Attendance Sheets" window action domain
    ══════════════════════════════════════════════════════ -->
    <record id="edu_attendance.action_edu_attendance_sheet_mine" model="ir.actions.act_window">
        <field name="name">My Attendance Sheets</field>
        <field name="res_model">edu.attendance.sheet</field>
        <field name="view_mode">list,form</field>
        <field name="domain">[('teacher_id.user_id', '=', uid)]</field>
        <field name="context">{'search_default_filter_my_sheets': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No attendance sheets assigned to you.
            </p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/views/edu_attendance_views.xml
git commit -m "feat(edu_hr): update attendance views for hr.employee teacher"
```

---

### Task 15: View Overrides — Assessment

**Files:**
- Create: `edu_hr/views/edu_assessment_views.xml`

Existing views to update:
- Search "My Assessments": `domain="[('teacher_id', '=', uid)]"`
- Window action "My Assessments": `domain=[('teacher_id', '=', uid)]`, `context={'default_teacher_id': uid, ...}`

The `default_teacher_id: uid` context is problematic — `uid` is a `res.users` ID but `teacher_id` now expects `hr.employee`. We must remove the default from the action context (the field's own `default=lambda` handles this correctly).

- [ ] **Step 1: Create `edu_hr/views/edu_assessment_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Assessment Record — Search: update "My Assessments"
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_assessment_record_search_hr" model="ir.ui.view">
        <field name="name">edu.continuous.assessment.record.search.hr</field>
        <field name="model">edu.continuous.assessment.record</field>
        <field name="inherit_id" ref="edu_assessment.view_edu_continuous_assessment_record_search"/>
        <field name="arch" type="xml">
            <xpath expr="//filter[@name='filter_my_assessments']" position="attributes">
                <attribute name="domain">[('teacher_id.user_id', '=', uid)]</attribute>
            </xpath>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Update "My Assessments" window action
         Remove default_teacher_id: uid (no longer valid —
         teacher_id is hr.employee, not res.users).
         The field's default=lambda handles this correctly.
    ══════════════════════════════════════════════════════ -->
    <record id="edu_assessment.action_edu_continuous_assessment_record_mine" model="ir.actions.act_window">
        <field name="name">My Assessments</field>
        <field name="res_model">edu.continuous.assessment.record</field>
        <field name="view_mode">list,form</field>
        <field name="domain">[('teacher_id.user_id', '=', uid)]</field>
        <field name="context">{'search_default_filter_my_assessments': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No assessment records assigned to you.
            </p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/views/edu_assessment_views.xml
git commit -m "feat(edu_hr): update assessment views for hr.employee teacher"
```

---

### Task 16: Menu Structure

**Files:**
- Create: `edu_hr/views/menu_views.xml`

- [ ] **Step 1: Create `menu_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Staff Management — top-level menu under Education -->
    <menuitem id="menu_edu_hr_root"
              name="Staff Management"
              parent="edu_academic_structure.menu_education_root"
              sequence="25"
              groups="hr.group_hr_user,hr.group_hr_manager,edu_academic_structure.group_education_admin"/>

    <!-- All Staff -->
    <menuitem id="menu_edu_staff_all"
              name="Staff"
              parent="menu_edu_hr_root"
              action="action_edu_staff_all"
              sequence="10"/>

    <!-- Teaching Staff -->
    <menuitem id="menu_edu_teaching_staff"
              name="Teaching Staff"
              parent="menu_edu_hr_root"
              action="action_edu_teaching_staff"
              sequence="20"/>

    <!-- HR Departments -->
    <menuitem id="menu_edu_hr_departments"
              name="Departments"
              parent="menu_edu_hr_root"
              action="hr.open_module_tree_department"
              sequence="30"/>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_hr/views/menu_views.xml
git commit -m "feat(edu_hr): add Staff Management menu structure"
```

---

### Task 17: Verify and Create Directories

Before the module can be installed, ensure all directories exist and the file structure is complete.

- [ ] **Step 1: Create all required directories**

```bash
cd /opt/custom_addons/education
mkdir -p edu_hr/models edu_hr/views edu_hr/security edu_hr/data
```

- [ ] **Step 2: Verify all files exist**

```bash
find edu_hr/ -type f | sort
```

Expected output:
```
edu_hr/__init__.py
edu_hr/__manifest__.py
edu_hr/data/ir_sequence_data.xml
edu_hr/models/__init__.py
edu_hr/models/edu_attendance.py
edu_hr/models/edu_classroom.py
edu_hr/models/edu_continuous_assessment_record.py
edu_hr/models/edu_department.py
edu_hr/models/edu_exam_paper.py
edu_hr/models/hr_employee.py
edu_hr/models/edu_staff_qualification.py
edu_hr/views/edu_assessment_views.xml
edu_hr/views/edu_attendance_views.xml
edu_hr/views/edu_classroom_views.xml
edu_hr/views/edu_exam_paper_views.xml
edu_hr/views/hr_employee_views.xml
edu_hr/views/menu_views.xml
edu_hr/security/ir.model.access.csv
edu_hr/security/security.xml
```

- [ ] **Step 3: Lint Python files**

```bash
cd /opt/custom_addons/education
ruff check edu_hr/
```

Expected: No errors.

- [ ] **Step 4: Fix any linting issues and commit**

```bash
git add -A edu_hr/
git commit -m "chore(edu_hr): verify module structure and lint"
```

---

### Task 18: Verify XML IDs for View Inherits

Before attempting installation, verify that all referenced external IDs exist in the original modules.

- [ ] **Step 1: Verify exam paper view/action external IDs**

```bash
cd /opt/custom_addons/education
grep -r 'id="view_edu_exam_paper_search"' edu_exam/views/
grep -r 'id="action_edu_exam_paper_mine"' edu_exam/views/
grep -r 'id="filter_my_papers"' edu_exam/views/
```

If any ID is not found, update the corresponding `edu_hr/views/*.xml` to use the correct external ID from the source module.

- [ ] **Step 2: Verify attendance view/action external IDs**

```bash
grep -r 'id="view_edu_attendance_register_search"' edu_attendance/views/
grep -r 'id="view_edu_attendance_sheet_search"' edu_attendance/views/
grep -r 'id="action_edu_attendance_sheet_mine"' edu_attendance/views/
grep -r 'id="filter_my_registers"' edu_attendance/views/
grep -r 'id="filter_my_sheets"' edu_attendance/views/
```

- [ ] **Step 3: Verify assessment view/action external IDs**

```bash
grep -r 'id="view_edu_continuous_assessment_record_search"' edu_assessment/views/
grep -r 'id="action_edu_continuous_assessment_record_mine"' edu_assessment/views/
grep -r 'id="filter_my_assessments"' edu_assessment/views/
```

- [ ] **Step 4: Fix any mismatched external IDs**

If any grep returns empty, read the source view file to find the correct ID and update the corresponding `edu_hr/views/*.xml` file. Then commit fixes.

```bash
git add edu_hr/views/
git commit -m "fix(edu_hr): correct view inherit external IDs"
```

---

### Task 19: Install and Smoke Test

- [ ] **Step 1: Install the module**

```bash
odoo -d <database> -i edu_hr --stop-after-init
```

Expected: Clean install with no errors. Watch for:
- `KeyError` or `ValueError` on field definitions
- `MissingError` on XML view inherits
- Foreign key constraint errors on `teacher_id` column type change

- [ ] **Step 2: Verify in the UI**

Manual checks:
1. Navigate to **Staff Management > Staff** — form should show Education tab, Qualifications tab, Subject Expertise tab
2. Create an employee with `is_teaching_staff = True` — verify employee_code auto-generates as `TCH/0001`
3. Navigate to **Classrooms > All Classrooms** — teacher_id dropdown should show employees, not users
4. Open a classroom form — "Teacher Profile" smart button should appear when teacher is assigned
5. Check "My Classrooms" filter works (teacher_id.user_id traversal)
6. Navigate to **Examinations > My Papers** — filter should work
7. Navigate to **Attendance > My Sheets** — filter should work
8. Navigate to **Assessment > My Assessments** — filter should work

- [ ] **Step 3: Final commit with any fixes**

```bash
git add -A edu_hr/
git commit -m "feat(edu_hr): complete staff management module — ready for testing"
```
