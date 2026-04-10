# edu_portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a custom-designed web portal for students, teachers, and parents with vibrant UI, collapsible sidebar, and HTMX-powered live interactions — without using Odoo's default portal/website modules.

**Architecture:** Custom `http.Controller` routes + QWeb templates + custom CSS/JS + bundled HTMX. All three user roles are `base.group_portal` users (free licensing). Teachers write data via controllers with `sudo()` + explicit ownership checks; students/parents read via ORM record rules.

**Tech Stack:** Odoo 19, Python 3, HTMX 1.9, QWeb XML, Custom CSS with CSS variables, Vanilla JS

**Spec:** `docs/superpowers/specs/2026-04-10-edu-portal-design.md`

---

## File Structure

```
edu_portal/
├── __manifest__.py
├── __init__.py
├── controllers/
│   ├── __init__.py
│   ├── helpers.py           # Permission/ownership check utilities
│   ├── main.py              # /portal redirect, role routing
│   ├── teacher.py           # /portal/teacher/* routes
│   ├── student.py           # /portal/student/* routes
│   └── parent.py            # /portal/parent/* routes
├── models/
│   ├── __init__.py
│   ├── res_users.py         # portal_role + children_partner_ids + login redirect
│   ├── edu_student.py       # portal_access + action_grant_portal_access
│   ├── edu_guardian.py      # portal_access + action_grant_portal_access
│   └── hr_employee.py       # portal_access + action_grant_portal_access
├── views/
│   ├── portal_layout.xml    # Master layout template
│   ├── components.xml       # Sidebar, topbar, reusable components
│   ├── teacher_templates.xml  # All teacher-facing templates
│   ├── student_templates.xml  # All student-facing templates
│   ├── parent_templates.xml   # All parent-facing templates
│   ├── res_users_views.xml    # Backend: portal_role field display
│   ├── edu_student_views.xml  # Backend: Grant Portal Access button
│   ├── edu_guardian_views.xml # Backend: Grant Portal Access button
│   └── hr_employee_views.xml  # Backend: Grant Portal Access button
├── security/
│   ├── security.xml         # 3 portal groups + record rules
│   └── ir.model.access.csv
├── data/
│   └── mail_templates.xml   # Welcome email template
└── static/
    └── src/
        ├── css/
        │   └── portal.css   # Complete stylesheet
        ├── js/
        │   ├── portal.js    # Sidebar, role switcher
        │   └── entry.js     # Attendance + marks entry helpers
        └── vendor/
            └── htmx.min.js  # HTMX library
```

---

### Task 1: Module Scaffold

**Files:**
- Create: `edu_portal/__manifest__.py`
- Create: `edu_portal/__init__.py`
- Create: `edu_portal/models/__init__.py`
- Create: `edu_portal/controllers/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
cd /opt/custom_addons/education
mkdir -p edu_portal/{controllers,models,views,security,data,static/src/{css,js,vendor}}
```

- [ ] **Step 2: Create `__manifest__.py`**

```python
{
    'name': 'Education: Portal',
    'version': '19.0.1.0.0',
    'summary': 'Custom student, teacher, and parent portal for the EMIS system.',
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'hr',
        'edu_academic_structure',
        'edu_student',
        'edu_enrollment',
        'edu_academic_progression',
        'edu_classroom',
        'edu_attendance',
        'edu_exam',
        'edu_assessment',
        'edu_result',
        'edu_fees',
        'edu_pre_admission_crm',
        'edu_hr',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_templates.xml',
        'views/portal_layout.xml',
        'views/components.xml',
        'views/teacher_templates.xml',
        'views/student_templates.xml',
        'views/parent_templates.xml',
        'views/res_users_views.xml',
        'views/edu_student_views.xml',
        'views/edu_guardian_views.xml',
        'views/hr_employee_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'edu_portal/static/src/vendor/htmx.min.js',
            'edu_portal/static/src/css/portal.css',
            'edu_portal/static/src/js/portal.js',
            'edu_portal/static/src/js/entry.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

- [ ] **Step 3: Create `edu_portal/__init__.py`**

```python
from . import models
from . import controllers
```

- [ ] **Step 4: Create `edu_portal/models/__init__.py`**

```python
from . import res_users
from . import edu_student
from . import edu_guardian
from . import hr_employee
```

- [ ] **Step 5: Create `edu_portal/controllers/__init__.py`**

```python
from . import helpers
from . import main
from . import teacher
from . import student
from . import parent
```

- [ ] **Step 6: Commit**

```bash
git add edu_portal/
git commit -m "feat(edu_portal): scaffold module with manifest and init files"
```

---

### Task 2: Security Groups

**Files:**
- Create: `edu_portal/security/security.xml` (groups only — record rules added in later tasks)
- Create: `edu_portal/security/ir.model.access.csv`

- [ ] **Step 1: Create `security.xml` with the 3 portal groups**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Portal Privilege Category
    ══════════════════════════════════════════════════════ -->
    <record id="privilege_edu_portal" model="res.groups.privilege">
        <field name="name">Education Portal</field>
        <field name="sequence">95</field>
        <field name="category_id" ref="edu_academic_structure.module_category_education"/>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Portal Groups
         All three inherit from base.group_portal (free licensing)
    ══════════════════════════════════════════════════════ -->

    <record id="group_edu_portal_student" model="res.groups">
        <field name="name">Portal: Student</field>
        <field name="privilege_id" ref="privilege_edu_portal"/>
        <field name="implied_ids" eval="[(4, ref('base.group_portal'))]"/>
        <field name="comment">Student portal user. Can view own attendance, results, assessments, and fees.</field>
    </record>

    <record id="group_edu_portal_parent" model="res.groups">
        <field name="name">Portal: Parent</field>
        <field name="privilege_id" ref="privilege_edu_portal"/>
        <field name="implied_ids" eval="[(4, ref('base.group_portal'))]"/>
        <field name="comment">Parent portal user. Can view children's attendance, results, assessments, and fees.</field>
    </record>

    <record id="group_edu_portal_teacher" model="res.groups">
        <field name="name">Portal: Teacher</field>
        <field name="privilege_id" ref="privilege_edu_portal"/>
        <field name="implied_ids" eval="[(4, ref('base.group_portal'))]"/>
        <field name="comment">Teacher portal user. Can mark attendance, enter marks, and record assessments for their classrooms via the portal controller.</field>
    </record>
</odoo>
```

- [ ] **Step 2: Create minimal `ir.model.access.csv`**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

(Empty for now — we'll add entries in the record rules task.)

- [ ] **Step 3: Commit**

```bash
git add edu_portal/security/
git commit -m "feat(edu_portal): add portal groups for student, parent, teacher"
```

---

### Task 3: res.users Extension

**Files:**
- Create: `edu_portal/models/res_users.py`

- [ ] **Step 1: Create `res_users.py`**

```python
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # ═══ Portal Role ═══

    portal_role = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('parent', 'Parent'),
            ('teacher', 'Teacher'),
            ('multi', 'Multiple Roles'),
            ('none', 'No Portal Role'),
        ],
        string='Portal Role',
        compute='_compute_portal_role',
    )

    # ═══ Parent's Children (for record rule scoping) ═══

    children_partner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='res_users_children_partner_rel',
        column1='user_id',
        column2='partner_id',
        string='Children Partners',
        compute='_compute_children_partner_ids',
        store=False,
        help='Partner records of children (students) linked to this parent via guardian relationship. '
             'Used by parent portal record rules to scope access.',
    )

    # ═══ Computed Methods ═══

    def _compute_portal_role(self):
        for user in self:
            roles = []
            if user.has_group('edu_portal.group_edu_portal_student'):
                roles.append('student')
            if user.has_group('edu_portal.group_edu_portal_parent'):
                roles.append('parent')
            if user.has_group('edu_portal.group_edu_portal_teacher'):
                roles.append('teacher')
            if len(roles) == 0:
                user.portal_role = 'none'
            elif len(roles) == 1:
                user.portal_role = roles[0]
            else:
                user.portal_role = 'multi'

    def _compute_children_partner_ids(self):
        Guardian = self.env['edu.guardian'].sudo()
        Student = self.env['edu.student'].sudo()
        for user in self:
            if not user.partner_id:
                user.children_partner_ids = [(5, 0, 0)]
                continue
            guardian = Guardian.search([('partner_id', '=', user.partner_id.id)], limit=1)
            if not guardian:
                user.children_partner_ids = [(5, 0, 0)]
                continue
            applicant_profiles = guardian.applicant_ids.mapped('applicant_id')
            students = Student.search([
                ('applicant_profile_id', 'in', applicant_profiles.ids),
            ])
            user.children_partner_ids = [(6, 0, students.mapped('partner_id').ids)]

    # ═══ Login Redirect Override ═══

    def _get_portal_landing_url(self):
        """Return landing URL for portal users after login."""
        self.ensure_one()
        if self.portal_role in ('student', 'parent', 'teacher', 'multi'):
            return '/portal'
        return False
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/models/res_users.py
git commit -m "feat(edu_portal): add portal_role and children_partner_ids to res.users"
```

---

### Task 4: edu.student Portal Access

**Files:**
- Create: `edu_portal/models/edu_student.py`

- [ ] **Step 1: Create `edu_student.py`**

```python
import secrets
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduStudent(models.Model):
    _inherit = 'edu.student'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='When enabled, this student has access to the student portal at /portal.',
    )
    portal_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Portal User',
        compute='_compute_portal_user_id',
        help='Computed from partner_id.user_ids filtered to portal users.',
    )

    @api.depends('partner_id', 'partner_id.user_ids')
    def _compute_portal_user_id(self):
        Group = self.env.ref('edu_portal.group_edu_portal_student', raise_if_not_found=False)
        for rec in self:
            if not rec.partner_id or not Group:
                rec.portal_user_id = False
                continue
            users = rec.partner_id.user_ids.filtered(lambda u: Group in u.groups_id)
            rec.portal_user_id = users[:1]

    def action_grant_portal_access(self):
        """Create (or update) a res.users portal user for this student."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Cannot grant portal access: student has no partner record.'))

        group = self.env.ref('edu_portal.group_edu_portal_student')
        existing_user = self.partner_id.user_ids[:1]
        temp_password = _generate_portal_password()

        if existing_user:
            existing_user.write({'groups_id': [(4, group.id)]})
            user = existing_user
        else:
            user = self.env['res.users'].sudo().create({
                'name': self.display_name,
                'login': self.partner_id.email or f'student_{self.id}@portal.local',
                'partner_id': self.partner_id.id,
                'password': temp_password,
                'groups_id': [(6, 0, [group.id])],
            })

        self.portal_access = True
        self._send_portal_welcome_email(user, temp_password)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Portal user created for %s. Login: %s') % (self.display_name, user.login),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_revoke_portal_access(self):
        """Remove student portal group from the linked user."""
        self.ensure_one()
        group = self.env.ref('edu_portal.group_edu_portal_student')
        if self.portal_user_id:
            self.portal_user_id.sudo().write({'groups_id': [(3, group.id)]})
        self.portal_access = False
        return True

    def _send_portal_welcome_email(self, user, temp_password):
        template = self.env.ref('edu_portal.mail_template_portal_welcome', raise_if_not_found=False)
        if template:
            template.sudo().with_context(
                portal_user=user,
                portal_temp_password=temp_password,
                portal_role='student',
            ).send_mail(self.id, force_send=False)


def _generate_portal_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/models/edu_student.py
git commit -m "feat(edu_portal): add portal access provisioning for edu.student"
```

---

### Task 5: edu.guardian Portal Access

**Files:**
- Create: `edu_portal/models/edu_guardian.py`

- [ ] **Step 1: Create `edu_guardian.py`**

```python
import secrets
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduGuardian(models.Model):
    _inherit = 'edu.guardian'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='When enabled, this guardian has access to the parent portal at /portal.',
    )
    portal_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Portal User',
        compute='_compute_portal_user_id',
    )

    @api.depends('partner_id', 'partner_id.user_ids')
    def _compute_portal_user_id(self):
        Group = self.env.ref('edu_portal.group_edu_portal_parent', raise_if_not_found=False)
        for rec in self:
            if not rec.partner_id or not Group:
                rec.portal_user_id = False
                continue
            users = rec.partner_id.user_ids.filtered(lambda u: Group in u.groups_id)
            rec.portal_user_id = users[:1]

    def action_grant_portal_access(self):
        """Create (or update) a res.users portal user for this guardian."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Cannot grant portal access: guardian has no partner record.'))

        group = self.env.ref('edu_portal.group_edu_portal_parent')
        existing_user = self.partner_id.user_ids[:1]
        temp_password = _generate_portal_password()

        if existing_user:
            existing_user.write({'groups_id': [(4, group.id)]})
            user = existing_user
        else:
            user = self.env['res.users'].sudo().create({
                'name': self.full_name,
                'login': self.partner_id.email or f'parent_{self.id}@portal.local',
                'partner_id': self.partner_id.id,
                'password': temp_password,
                'groups_id': [(6, 0, [group.id])],
            })

        self.portal_access = True
        self._send_portal_welcome_email(user, temp_password)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Portal user created for %s. Login: %s') % (self.full_name, user.login),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_revoke_portal_access(self):
        self.ensure_one()
        group = self.env.ref('edu_portal.group_edu_portal_parent')
        if self.portal_user_id:
            self.portal_user_id.sudo().write({'groups_id': [(3, group.id)]})
        self.portal_access = False
        return True

    def _send_portal_welcome_email(self, user, temp_password):
        template = self.env.ref('edu_portal.mail_template_portal_welcome', raise_if_not_found=False)
        if template:
            template.sudo().with_context(
                portal_user=user,
                portal_temp_password=temp_password,
                portal_role='parent',
            ).send_mail(self.id, force_send=False)


def _generate_portal_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/models/edu_guardian.py
git commit -m "feat(edu_portal): add portal access provisioning for edu.guardian"
```

---

### Task 6: hr.employee Portal Access

**Files:**
- Create: `edu_portal/models/hr_employee.py`

- [ ] **Step 1: Create `hr_employee.py`**

```python
import secrets
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='When enabled, this teaching staff has access to the teacher portal at /portal.',
    )
    portal_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Portal User',
        compute='_compute_portal_user_id',
    )

    @api.depends('user_id')
    def _compute_portal_user_id(self):
        Group = self.env.ref('edu_portal.group_edu_portal_teacher', raise_if_not_found=False)
        for rec in self:
            if rec.user_id and Group and Group in rec.user_id.groups_id:
                rec.portal_user_id = rec.user_id
            else:
                rec.portal_user_id = False

    def action_grant_portal_access(self):
        """Create or upgrade a res.users record for this employee as a teacher portal user."""
        self.ensure_one()
        if not self.is_teaching_staff:
            raise UserError(_('Portal access is only available for teaching staff.'))

        group = self.env.ref('edu_portal.group_edu_portal_teacher')
        temp_password = _generate_portal_password()

        if self.user_id:
            # Existing user — add the teacher portal group
            self.user_id.write({'groups_id': [(4, group.id)]})
            user = self.user_id
        elif self.work_contact_id and self.work_contact_id.user_ids:
            user = self.work_contact_id.user_ids[:1]
            user.write({'groups_id': [(4, group.id)]})
            self.user_id = user
        else:
            # Create new user linked to employee
            login = self.work_email or f'teacher_{self.id}@portal.local'
            user = self.env['res.users'].sudo().create({
                'name': self.name,
                'login': login,
                'password': temp_password,
                'groups_id': [(6, 0, [group.id])],
            })
            self.user_id = user

        self.portal_access = True
        self._send_portal_welcome_email(user, temp_password)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Teacher portal user created for %s. Login: %s') % (self.name, user.login),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_revoke_portal_access(self):
        self.ensure_one()
        group = self.env.ref('edu_portal.group_edu_portal_teacher')
        if self.portal_user_id:
            self.portal_user_id.sudo().write({'groups_id': [(3, group.id)]})
        self.portal_access = False
        return True

    def _send_portal_welcome_email(self, user, temp_password):
        template = self.env.ref('edu_portal.mail_template_portal_welcome', raise_if_not_found=False)
        if template:
            template.sudo().with_context(
                portal_user=user,
                portal_temp_password=temp_password,
                portal_role='teacher',
            ).send_mail(self.id, force_send=False)


def _generate_portal_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/models/hr_employee.py
git commit -m "feat(edu_portal): add portal access provisioning for teaching staff"
```

---

### Task 7: Welcome Email Template

**Files:**
- Create: `edu_portal/data/mail_templates.xml`

- [ ] **Step 1: Create `mail_templates.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="mail_template_portal_welcome" model="mail.template">
        <field name="name">Portal: Welcome Email</field>
        <field name="model_id" ref="base.model_res_partner"/>
        <field name="subject">Welcome to the EMIS Portal</field>
        <field name="email_from">{{ (object.company_id.email or user.email) }}</field>
        <field name="email_to">{{ ctx.get('portal_user').email }}</field>
        <field name="body_html" type="html">
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; border-radius: 12px 12px 0 0;">
                    <h1 style="margin: 0; font-size: 22px;">Welcome to EMIS Portal</h1>
                </div>
                <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p>Hello <t t-out="ctx.get('portal_user').name"/>,</p>
                    <p>Your EMIS portal account has been created. You can use it to access your
                    <strong t-out="ctx.get('portal_role', 'portal')"/> information.</p>
                    <div style="background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0;">
                        <p style="margin: 0 0 8px 0;"><strong>Login:</strong> <t t-out="ctx.get('portal_user').login"/></p>
                        <p style="margin: 0;"><strong>Temporary Password:</strong> <code t-out="ctx.get('portal_temp_password')"/></p>
                    </div>
                    <p>Please log in at <a t-att-href="url" style="color: #667eea;">the portal</a> and change your password on first login.</p>
                    <p style="color: #64748b; font-size: 12px; margin-top: 24px;">If you did not expect this email, please contact your school administrator.</p>
                </div>
            </div>
        </field>
        <field name="auto_delete" eval="True"/>
    </record>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/data/mail_templates.xml
git commit -m "feat(edu_portal): add welcome email mail template"
```

---

### Task 8: Record Rules — Student Read Access

**Files:**
- Modify: `edu_portal/security/security.xml` (append record rules)

- [ ] **Step 1: Append record rules for student portal access**

Append to the existing `edu_portal/security/security.xml` before the closing `</odoo>` tag:

```xml
    <!-- ══════════════════════════════════════════════════════
         Student Portal — Record Rules
         Scope all reads to the student's own partner.
    ══════════════════════════════════════════════════════ -->

    <record id="rule_portal_student_own_record" model="ir.rule">
        <field name="name">Portal Student: own record only</field>
        <field name="model_id" ref="edu_student.model_edu_student"/>
        <field name="domain_force">[('partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_student_attendance" model="ir.rule">
        <field name="name">Portal Student: own attendance lines</field>
        <field name="model_id" ref="edu_attendance.model_edu_attendance_sheet_line"/>
        <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_student_marksheet" model="ir.rule">
        <field name="name">Portal Student: own marksheets</field>
        <field name="model_id" ref="edu_exam.model_edu_exam_marksheet"/>
        <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_student_assessment" model="ir.rule">
        <field name="name">Portal Student: own assessments</field>
        <field name="model_id" ref="edu_assessment.model_edu_continuous_assessment_record"/>
        <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_student_fee_due" model="ir.rule">
        <field name="name">Portal Student: own fee dues</field>
        <field name="model_id" ref="edu_fees.model_edu_student_fee_due"/>
        <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_student_fee_plan" model="ir.rule">
        <field name="name">Portal Student: own fee plans</field>
        <field name="model_id" ref="edu_fees.model_edu_student_fee_plan"/>
        <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_student_payment" model="ir.rule">
        <field name="name">Portal Student: own payments</field>
        <field name="model_id" ref="edu_fees.model_edu_student_payment"/>
        <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_student'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/security/security.xml
git commit -m "feat(edu_portal): add student portal record rules"
```

---

### Task 9: Record Rules — Parent Read Access

**Files:**
- Modify: `edu_portal/security/security.xml` (append parent rules)

- [ ] **Step 1: Append parent record rules**

Append before `</odoo>`:

```xml
    <!-- ══════════════════════════════════════════════════════
         Parent Portal — Record Rules
         Scope reads to children linked via guardian relationship.
         Uses user.children_partner_ids (computed on res.users).
    ══════════════════════════════════════════════════════ -->

    <record id="rule_portal_parent_student" model="ir.rule">
        <field name="name">Portal Parent: children records</field>
        <field name="model_id" ref="edu_student.model_edu_student"/>
        <field name="domain_force">[('partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_parent_attendance" model="ir.rule">
        <field name="name">Portal Parent: children attendance</field>
        <field name="model_id" ref="edu_attendance.model_edu_attendance_sheet_line"/>
        <field name="domain_force">[('student_id.partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_parent_marksheet" model="ir.rule">
        <field name="name">Portal Parent: children marksheets</field>
        <field name="model_id" ref="edu_exam.model_edu_exam_marksheet"/>
        <field name="domain_force">[('student_id.partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_parent_assessment" model="ir.rule">
        <field name="name">Portal Parent: children assessments</field>
        <field name="model_id" ref="edu_assessment.model_edu_continuous_assessment_record"/>
        <field name="domain_force">[('student_id.partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_parent_fee_due" model="ir.rule">
        <field name="name">Portal Parent: children fee dues</field>
        <field name="model_id" ref="edu_fees.model_edu_student_fee_due"/>
        <field name="domain_force">[('student_id.partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_parent_fee_plan" model="ir.rule">
        <field name="name">Portal Parent: children fee plans</field>
        <field name="model_id" ref="edu_fees.model_edu_student_fee_plan"/>
        <field name="domain_force">[('student_id.partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>

    <record id="rule_portal_parent_payment" model="ir.rule">
        <field name="name">Portal Parent: children payments</field>
        <field name="model_id" ref="edu_fees.model_edu_student_payment"/>
        <field name="domain_force">[('student_id.partner_id', 'in', user.children_partner_ids.ids)]</field>
        <field name="groups" eval="[(4, ref('group_edu_portal_parent'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/security/security.xml
git commit -m "feat(edu_portal): add parent portal record rules"
```

---

### Task 10: Static Assets — HTMX + JS Skeleton

**Files:**
- Create: `edu_portal/static/src/vendor/htmx.min.js`
- Create: `edu_portal/static/src/js/portal.js`
- Create: `edu_portal/static/src/js/entry.js`

- [ ] **Step 1: Download HTMX 1.9.10 locally**

```bash
cd /opt/custom_addons/education/edu_portal/static/src/vendor
curl -L -o htmx.min.js https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js
ls -la htmx.min.js
```

Expected: file size ~47KB.

- [ ] **Step 2: Create `portal.js`**

```javascript
/* EMIS Portal — main JS (sidebar, role switcher, misc UI) */
(function() {
    'use strict';

    // ─── Sidebar toggle ────────────────────────────────────
    function initSidebarToggle() {
        const toggle = document.querySelector('[data-sidebar-toggle]');
        const body = document.body;
        if (!toggle) return;

        toggle.addEventListener('click', function() {
            body.classList.toggle('sidebar-collapsed');
            // Persist state via cookie (server reads on next request)
            const collapsed = body.classList.contains('sidebar-collapsed');
            document.cookie = `portal_sidebar_collapsed=${collapsed ? '1' : '0'}; path=/; max-age=31536000`;
        });
    }

    // ─── Mobile drawer backdrop ────────────────────────────
    function initMobileDrawer() {
        const backdrop = document.querySelector('[data-sidebar-backdrop]');
        const body = document.body;
        if (!backdrop) return;
        backdrop.addEventListener('click', function() {
            body.classList.remove('sidebar-open');
        });
    }

    // ─── User menu dropdown ────────────────────────────────
    function initUserMenu() {
        const trigger = document.querySelector('[data-user-menu-trigger]');
        const menu = document.querySelector('[data-user-menu]');
        if (!trigger || !menu) return;
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            menu.classList.toggle('open');
        });
        document.addEventListener('click', function() {
            menu.classList.remove('open');
        });
    }

    // ─── HTMX success flash ────────────────────────────────
    function initHtmxFlash() {
        document.body.addEventListener('htmx:afterSwap', function(evt) {
            const target = evt.detail.target;
            if (target && target.classList) {
                target.classList.add('flash-success');
                setTimeout(() => target.classList.remove('flash-success'), 600);
            }
        });
    }

    // ─── Init on DOM ready ─────────────────────────────────
    document.addEventListener('DOMContentLoaded', function() {
        initSidebarToggle();
        initMobileDrawer();
        initUserMenu();
        initHtmxFlash();
    });
})();
```

- [ ] **Step 3: Create `entry.js`**

```javascript
/* EMIS Portal — data entry grid helpers (attendance, marks) */
(function() {
    'use strict';

    // ─── Attendance: keyboard shortcuts ─────────────────────
    // Press P, A, L, E while focused on a row to mark that student
    function initAttendanceKeyboard() {
        document.addEventListener('keydown', function(e) {
            const row = e.target.closest('[data-attendance-row]');
            if (!row) return;
            const keyMap = {
                'p': 'present', 'P': 'present',
                'a': 'absent',  'A': 'absent',
                'l': 'late',    'L': 'late',
                'e': 'excused', 'E': 'excused',
            };
            const status = keyMap[e.key];
            if (!status) return;
            e.preventDefault();
            const lineId = row.getAttribute('data-line-id');
            htmx.ajax('POST', '/portal/teacher/attendance/mark', {
                target: row,
                swap: 'outerHTML',
                values: { line_id: lineId, status: status },
            });
            // Move focus to next row
            const nextRow = row.nextElementSibling;
            if (nextRow && nextRow.hasAttribute('data-attendance-row')) {
                nextRow.focus();
            }
        });
    }

    // ─── Marks entry: tab navigation ────────────────────────
    function initMarksTabNavigation() {
        const inputs = document.querySelectorAll('[data-marks-input]');
        inputs.forEach((input, idx) => {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const next = inputs[idx + 1];
                    if (next) next.focus();
                }
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        initAttendanceKeyboard();
        initMarksTabNavigation();
    });
    // Re-init after HTMX swaps (grids may be reloaded)
    document.body.addEventListener('htmx:afterSwap', function() {
        initMarksTabNavigation();
    });
})();
```

- [ ] **Step 4: Commit**

```bash
git add edu_portal/static/src/vendor/htmx.min.js edu_portal/static/src/js/
git commit -m "feat(edu_portal): bundle HTMX and add UI + entry grid JS helpers"
```

---

### Task 11: CSS — Complete Portal Stylesheet

**Files:**
- Create: `edu_portal/static/src/css/portal.css`

- [ ] **Step 1: Create `portal.css`**

```css
/* ══════════════════════════════════════════════════════════
   EMIS Portal Stylesheet
   Vibrant gradient + glassmorphism design
   ══════════════════════════════════════════════════════════ */

/* ─── Design Tokens ──────────────────────────────────────── */
:root {
    --grad-start: #667eea;
    --grad-end: #764ba2;
    --glass-bg: rgba(255, 255, 255, 0.15);
    --glass-bg-strong: rgba(255, 255, 255, 0.25);
    --glass-border: rgba(255, 255, 255, 0.2);
    --glass-blur: blur(10px);
    --text-on-gradient: #ffffff;
    --text-muted: rgba(255, 255, 255, 0.7);
    --text-dim: rgba(255, 255, 255, 0.5);
    --sidebar-width: 240px;
    --sidebar-collapsed-width: 72px;
    --topbar-height: 64px;
    --radius-lg: 16px;
    --radius-md: 12px;
    --radius-sm: 8px;
    --accent-success: #10b981;
    --accent-warning: #f59e0b;
    --accent-danger: #ef4444;
    --accent-info: #3b82f6;
    --card-bg: rgba(255, 255, 255, 0.95);
    --card-text: #1e293b;
}

/* ─── Base ───────────────────────────────────────────────── */
* { box-sizing: border-box; }

html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    color: var(--text-on-gradient);
    background: linear-gradient(135deg, var(--grad-start) 0%, var(--grad-end) 100%);
    background-attachment: fixed;
    min-height: 100vh;
}

a { color: inherit; text-decoration: none; }
button { font-family: inherit; cursor: pointer; border: none; }

/* ─── Layout ─────────────────────────────────────────────── */
.portal-body {
    display: flex;
    min-height: 100vh;
}

.portal-sidebar {
    width: var(--sidebar-width);
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-right: 1px solid var(--glass-border);
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    transition: width 0.25s ease, transform 0.25s ease;
    z-index: 100;
    overflow-y: auto;
}

.portal-main {
    flex: 1;
    margin-left: var(--sidebar-width);
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    transition: margin-left 0.25s ease;
}

/* Collapsed sidebar */
body.sidebar-collapsed .portal-sidebar { width: var(--sidebar-collapsed-width); }
body.sidebar-collapsed .portal-main { margin-left: var(--sidebar-collapsed-width); }
body.sidebar-collapsed .sidebar-label,
body.sidebar-collapsed .sidebar-brand-text { display: none; }

/* ─── Sidebar Content ────────────────────────────────────── */
.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 20px;
    border-bottom: 1px solid var(--glass-border);
    font-weight: 700;
    font-size: 16px;
}

.sidebar-brand-icon {
    width: 32px; height: 32px;
    background: var(--glass-bg-strong);
    border-radius: var(--radius-sm);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}

.sidebar-nav {
    list-style: none;
    padding: 12px 0;
    margin: 0;
}

.sidebar-nav li { padding: 0; }

.sidebar-nav a {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 20px;
    color: var(--text-muted);
    font-size: 14px;
    transition: all 0.15s;
    position: relative;
}

.sidebar-nav a:hover {
    background: var(--glass-bg);
    color: var(--text-on-gradient);
}

.sidebar-nav a.active {
    background: var(--glass-bg-strong);
    color: var(--text-on-gradient);
    border-left: 3px solid white;
    padding-left: 17px;
}

.sidebar-nav .nav-icon {
    width: 20px; height: 20px;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
}

.sidebar-badge {
    background: var(--accent-danger);
    color: white;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 10px;
    margin-left: auto;
}

body.sidebar-collapsed .sidebar-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    padding: 2px 5px;
}

/* ─── Topbar ─────────────────────────────────────────────── */
.portal-topbar {
    height: var(--topbar-height);
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-bottom: 1px solid var(--glass-border);
    display: flex;
    align-items: center;
    padding: 0 24px;
    gap: 16px;
    position: sticky;
    top: 0;
    z-index: 50;
}

.topbar-toggle {
    background: var(--glass-bg-strong);
    color: white;
    width: 40px; height: 40px;
    border-radius: var(--radius-sm);
    font-size: 20px;
    display: flex; align-items: center; justify-content: center;
}

.topbar-title { font-size: 18px; font-weight: 600; }
.topbar-spacer { flex: 1; }

.topbar-child-selector,
.topbar-role-switch {
    background: var(--glass-bg-strong);
    color: white;
    padding: 8px 14px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    border: 1px solid var(--glass-border);
}

.topbar-user {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 12px;
    background: var(--glass-bg-strong);
    border-radius: var(--radius-sm);
    cursor: pointer;
    position: relative;
}

.topbar-user-avatar {
    width: 32px; height: 32px;
    background: white;
    color: var(--grad-start);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700;
}

.user-menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: var(--card-bg);
    color: var(--card-text);
    border-radius: var(--radius-md);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    min-width: 200px;
    padding: 8px;
    display: none;
}

.user-menu.open { display: block; }
.user-menu a {
    display: block;
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    font-size: 13px;
}
.user-menu a:hover { background: #f1f5f9; }

/* ─── Content Area ───────────────────────────────────────── */
.portal-content {
    padding: 24px;
    flex: 1;
}

.page-title {
    font-size: 24px;
    font-weight: 700;
    margin: 0 0 20px 0;
}

/* ─── Cards (glassmorphism) ──────────────────────────────── */
.card {
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 20px;
    margin-bottom: 16px;
}

.card-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    margin: 0 0 12px 0;
}

.card-value {
    font-size: 28px;
    font-weight: 700;
    margin: 0;
}

.card-sub {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* Stat card grid */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

/* Dashboard two-column layout */
.dashboard-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 20px;
}

@media (max-width: 1024px) {
    .dashboard-grid { grid-template-columns: 1fr; }
}

/* ─── Classroom Card ─────────────────────────────────────── */
.classroom-card {
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 16px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: transform 0.15s, background 0.15s;
    cursor: pointer;
}

.classroom-card:hover {
    background: var(--glass-bg-strong);
    transform: translateY(-1px);
}

.classroom-card-info h3 {
    margin: 0 0 4px 0;
    font-size: 15px;
    font-weight: 600;
}

.classroom-card-info p {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
}

.classroom-card-badge {
    padding: 5px 12px;
    border-radius: 16px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.badge-warning { background: rgba(245, 158, 11, 0.3); color: #fef3c7; }
.badge-danger { background: rgba(239, 68, 68, 0.3); color: #fee2e2; }
.badge-success { background: rgba(16, 185, 129, 0.3); color: #d1fae5; }
.badge-muted { background: rgba(255, 255, 255, 0.15); color: var(--text-muted); }

/* ─── Tables / Grids ─────────────────────────────────────── */
.data-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border-radius: var(--radius-md);
    overflow: hidden;
}

.data-table th {
    background: var(--glass-bg-strong);
    padding: 14px 16px;
    text-align: left;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 700;
}

.data-table td {
    padding: 14px 16px;
    border-top: 1px solid var(--glass-border);
    font-size: 14px;
}

.data-table tr:hover td { background: var(--glass-bg); }

/* Attendance row flash on HTMX update */
.flash-success {
    animation: flashSuccess 0.6s ease;
}

@keyframes flashSuccess {
    0% { background: rgba(16, 185, 129, 0.4); }
    100% { background: transparent; }
}

/* ─── Buttons ────────────────────────────────────────────── */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 600;
    transition: all 0.15s;
    text-decoration: none;
    border: none;
    cursor: pointer;
}

.btn-primary {
    background: white;
    color: var(--grad-start);
}
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

.btn-secondary {
    background: var(--glass-bg-strong);
    color: white;
    border: 1px solid var(--glass-border);
}
.btn-secondary:hover { background: rgba(255, 255, 255, 0.35); }

.btn-sm { padding: 6px 12px; font-size: 12px; }

/* Attendance status buttons (row-level) */
.status-btn {
    background: var(--glass-bg);
    color: white;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    margin-right: 4px;
    border: 1px solid transparent;
}
.status-btn:hover { background: var(--glass-bg-strong); }
.status-btn.active-present { background: var(--accent-success); border-color: var(--accent-success); }
.status-btn.active-absent { background: var(--accent-danger); border-color: var(--accent-danger); }
.status-btn.active-late { background: var(--accent-warning); border-color: var(--accent-warning); }
.status-btn.active-excused { background: var(--accent-info); border-color: var(--accent-info); }

/* ─── Forms ──────────────────────────────────────────────── */
.input {
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    color: white;
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    font-size: 14px;
    width: 100%;
}

.input:focus { outline: 2px solid white; outline-offset: 1px; }
.input::placeholder { color: var(--text-muted); }

.form-group { margin-bottom: 16px; }
.form-label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 6px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ─── Empty State ────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
}

.empty-state-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
}

.empty-state-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 6px;
    color: white;
}

/* ─── Responsive: Mobile ─────────────────────────────────── */
@media (max-width: 768px) {
    .portal-sidebar {
        transform: translateX(-100%);
        width: var(--sidebar-width);
    }
    body.sidebar-open .portal-sidebar { transform: translateX(0); }
    body.sidebar-open::after {
        content: '';
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 90;
    }
    .portal-main { margin-left: 0 !important; }
    .stat-grid { grid-template-columns: 1fr 1fr; }
    .data-table { display: block; overflow-x: auto; }
    .topbar-title { display: none; }
}

/* ─── Responsive: Tablet ─────────────────────────────────── */
@media (min-width: 769px) and (max-width: 1023px) {
    .portal-sidebar { width: var(--sidebar-collapsed-width); }
    .portal-main { margin-left: var(--sidebar-collapsed-width); }
    .sidebar-label, .sidebar-brand-text { display: none; }
}
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/static/src/css/portal.css
git commit -m "feat(edu_portal): complete portal stylesheet with glassmorphism and responsive design"
```

---

### Task 12: Master Layout Template

**Files:**
- Create: `edu_portal/views/portal_layout.xml`

- [ ] **Step 1: Create `portal_layout.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Master Portal Layout
         Used by all portal pages via t-call.
    ══════════════════════════════════════════════════════ -->
    <template id="portal_layout" name="EMIS Portal Layout">
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <title><t t-esc="page_title or 'EMIS Portal'"/></title>
                <link rel="stylesheet" type="text/css" href="/edu_portal/static/src/css/portal.css"/>
                <script src="/edu_portal/static/src/vendor/htmx.min.js"/>
            </head>
            <body t-attf-class="portal-body #{'sidebar-collapsed' if sidebar_collapsed else ''}"
                  t-att-data-role="portal_role">
                <t t-call="edu_portal.sidebar_component"/>
                <div class="portal-main">
                    <t t-call="edu_portal.topbar_component"/>
                    <main class="portal-content">
                        <t t-out="0"/>
                    </main>
                </div>
                <script src="/edu_portal/static/src/js/portal.js"/>
                <script src="/edu_portal/static/src/js/entry.js"/>
            </body>
        </html>
    </template>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/views/portal_layout.xml
git commit -m "feat(edu_portal): add master portal layout template"
```

---

### Task 13: Sidebar, Topbar & Reusable Components

**Files:**
- Create: `edu_portal/views/components.xml`

- [ ] **Step 1: Create `components.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Sidebar Component
         Renders role-specific navigation items.
         Expects: portal_role, sidebar_items, active_item
    ══════════════════════════════════════════════════════ -->
    <template id="sidebar_component" name="Portal Sidebar">
        <aside class="portal-sidebar" data-sidebar>
            <div class="sidebar-brand">
                <div class="sidebar-brand-icon">E</div>
                <span class="sidebar-brand-text">EMIS Portal</span>
            </div>
            <ul class="sidebar-nav">
                <t t-foreach="sidebar_items" t-as="item">
                    <li>
                        <a t-att-href="item['url']"
                           t-attf-class="#{'active' if item.get('key') == active_item else ''}">
                            <span class="nav-icon"><t t-esc="item['icon']"/></span>
                            <span class="sidebar-label"><t t-esc="item['label']"/></span>
                            <t t-if="item.get('badge')">
                                <span class="sidebar-badge"><t t-esc="item['badge']"/></span>
                            </t>
                        </a>
                    </li>
                </t>
            </ul>
        </aside>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Topbar Component
         Expects: page_title, user, portal_role, active_child (parent only)
    ══════════════════════════════════════════════════════ -->
    <template id="topbar_component" name="Portal Topbar">
        <header class="portal-topbar">
            <button class="topbar-toggle" data-sidebar-toggle="1" type="button">≡</button>
            <div class="topbar-title"><t t-esc="page_title or ''"/></div>
            <div class="topbar-spacer"/>

            <!-- Child selector (parent role only) -->
            <t t-if="portal_role == 'parent' and children">
                <select class="topbar-child-selector"
                        onchange="window.location.href='/portal/parent/switch-child/' + this.value">
                    <t t-foreach="children" t-as="child">
                        <option t-att-value="child.id" t-att-selected="active_child and active_child.id == child.id">
                            <t t-esc="child.display_name"/>
                        </option>
                    </t>
                </select>
            </t>

            <!-- Role switcher (multi-role users only) -->
            <t t-if="user.portal_role == 'multi'">
                <select class="topbar-role-switch"
                        onchange="window.location.href='/portal/role-switch/' + this.value">
                    <option value="student" t-att-selected="portal_role == 'student'">Student</option>
                    <option value="parent" t-att-selected="portal_role == 'parent'">Parent</option>
                    <option value="teacher" t-att-selected="portal_role == 'teacher'">Teacher</option>
                </select>
            </t>

            <!-- User menu -->
            <div class="topbar-user" data-user-menu-trigger="1">
                <div class="topbar-user-avatar"><t t-esc="user.name[0].upper() if user.name else '?'"/></div>
                <span><t t-esc="user.name"/></span>
                <div class="user-menu" data-user-menu="1">
                    <a t-attf-href="/portal/#{portal_role}/profile">My Profile</a>
                    <a href="/web/session/logout">Logout</a>
                </div>
            </div>
        </header>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Stat Card Component
         Expects: label, value, sub
    ══════════════════════════════════════════════════════ -->
    <template id="stat_card_component" name="Portal Stat Card">
        <div class="card">
            <p class="card-title"><t t-esc="label"/></p>
            <p class="card-value"><t t-esc="value"/></p>
            <t t-if="sub"><p class="card-sub"><t t-esc="sub"/></p></t>
        </div>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Classroom Card Component
         Expects: classroom, status_label, status_class, detail_url
    ══════════════════════════════════════════════════════ -->
    <template id="classroom_card_component" name="Portal Classroom Card">
        <a t-att-href="detail_url" class="classroom-card">
            <div class="classroom-card-info">
                <h3><t t-esc="classroom.name"/></h3>
                <p>
                    <t t-esc="classroom.section_id.name"/> ·
                    <t t-esc="classroom.subject_id.name"/>
                </p>
            </div>
            <span t-attf-class="classroom-card-badge #{status_class}">
                <t t-esc="status_label"/>
            </span>
        </a>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Empty State Component
         Expects: icon, title, message
    ══════════════════════════════════════════════════════ -->
    <template id="empty_state_component" name="Portal Empty State">
        <div class="empty-state">
            <div class="empty-state-icon"><t t-esc="icon or '📭'"/></div>
            <div class="empty-state-title"><t t-esc="title"/></div>
            <p><t t-esc="message or ''"/></p>
        </div>
    </template>
</odoo>
```

- [ ] **Step 2: Commit**

```bash
git add edu_portal/views/components.xml
git commit -m "feat(edu_portal): add sidebar, topbar, and reusable components"
```

---

### Task 14: Controller Helpers & Main Controller

**Files:**
- Create: `edu_portal/controllers/helpers.py`
- Create: `edu_portal/controllers/main.py`

- [ ] **Step 1: Create `helpers.py`**

```python
"""Shared helpers for edu_portal controllers."""
from odoo.http import request


def get_portal_role(user):
    """Return the effective portal role for this user, respecting session override for multi-role users."""
    role = user.portal_role
    if role == 'multi':
        session_role = request.session.get('active_portal_role')
        return session_role or 'teacher'
    return role


def set_portal_role(role):
    """Store the active portal role for multi-role users in the session."""
    request.session['active_portal_role'] = role


def is_sidebar_collapsed():
    """Read sidebar collapsed state from cookie."""
    return request.httprequest.cookies.get('portal_sidebar_collapsed') == '1'


def get_teacher_employee(user):
    """Return the hr.employee linked to this teacher user, or None."""
    emp = request.env['hr.employee'].sudo().search(
        [('user_id', '=', user.id)], limit=1,
    )
    return emp or None


def get_student_record(user):
    """Return the edu.student linked to this student user's partner, or None."""
    if not user.partner_id:
        return None
    return request.env['edu.student'].sudo().search(
        [('partner_id', '=', user.partner_id.id)], limit=1,
    ) or None


def get_guardian_record(user):
    """Return the edu.guardian linked to this parent user's partner, or None."""
    if not user.partner_id:
        return None
    return request.env['edu.guardian'].sudo().search(
        [('partner_id', '=', user.partner_id.id)], limit=1,
    ) or None


def get_parent_children(user):
    """Return the list of edu.student records (children) for a parent user."""
    guardian = get_guardian_record(user)
    if not guardian:
        return request.env['edu.student'].sudo()
    applicant_profiles = guardian.applicant_ids.mapped('applicant_id')
    return request.env['edu.student'].sudo().search(
        [('applicant_profile_id', 'in', applicant_profiles.ids)],
    )


def get_active_child(user):
    """Return the currently selected child for a parent, or the first child if none selected."""
    children = get_parent_children(user)
    if not children:
        return None
    active_id = request.session.get('active_child_id')
    if active_id:
        active = children.filtered(lambda s: s.id == active_id)
        if active:
            return active
    return children[0]


def set_active_child(student_id):
    request.session['active_child_id'] = student_id


def teacher_owns_classroom(employee, classroom):
    """Assert a teacher owns a given classroom. Return True/False."""
    if not employee or not classroom:
        return False
    return classroom.teacher_id == employee


def base_context(active_item=None, page_title=None):
    """Build the base context dict all portal templates need."""
    user = request.env.user
    role = get_portal_role(user)
    return {
        'user': user,
        'portal_role': role,
        'page_title': page_title or '',
        'sidebar_collapsed': is_sidebar_collapsed(),
        'active_item': active_item,
    }
```

- [ ] **Step 2: Create `main.py`**

```python
"""Root portal controllers — redirection and role switching."""
from odoo import http
from odoo.http import request
from .helpers import get_portal_role, set_portal_role, set_active_child


class PortalMainController(http.Controller):

    @http.route('/portal', type='http', auth='user', website=False)
    def portal_home(self, **kw):
        """Redirect to role-specific home."""
        user = request.env.user
        role = get_portal_role(user)
        if role == 'teacher':
            return request.redirect('/portal/teacher/home')
        elif role == 'student':
            return request.redirect('/portal/student/home')
        elif role == 'parent':
            return request.redirect('/portal/parent/home')
        else:
            # No portal role — send to standard Odoo backend
            return request.redirect('/odoo')

    @http.route('/portal/role-switch/<string:role>', type='http', auth='user', methods=['GET', 'POST'])
    def role_switch(self, role, **kw):
        """Switch active role for multi-role users."""
        if role not in ('student', 'parent', 'teacher'):
            return request.not_found()
        user = request.env.user
        if user.portal_role != 'multi':
            return request.not_found()
        set_portal_role(role)
        return request.redirect('/portal')

    @http.route('/portal/parent/switch-child/<int:student_id>', type='http', auth='user')
    def switch_child(self, student_id, **kw):
        """Set active child for parent portal users."""
        from .helpers import get_parent_children
        user = request.env.user
        children = get_parent_children(user)
        if student_id not in children.ids:
            return request.not_found()
        set_active_child(student_id)
        return request.redirect('/portal/parent/home')
```

- [ ] **Step 3: Commit**

```bash
git add edu_portal/controllers/helpers.py edu_portal/controllers/main.py
git commit -m "feat(edu_portal): add controller helpers and main routing"
```

---

### Task 15: Teacher Controller — Home, Classrooms, Roster

**Files:**
- Create: `edu_portal/controllers/teacher.py`
- Create: `edu_portal/views/teacher_templates.xml` (initial pages)

- [ ] **Step 1: Create `teacher.py` (initial routes)**

```python
"""Teacher portal controllers."""
from odoo import http, _
from odoo.http import request
from .helpers import (
    base_context, get_teacher_employee, teacher_owns_classroom, get_portal_role,
)


class TeacherPortalController(http.Controller):

    def _guard_teacher(self):
        """Ensure current user is a teacher. Returns employee or None."""
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return None
        return get_teacher_employee(user)

    def _teacher_sidebar_items(self, employee, active=None):
        """Build sidebar navigation with badges for a teacher."""
        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms_with_open = Classroom.search_count([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ])
        marks_entry_papers = ExamPaper.search_count([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'marks_entry'),
        ])
        items = [
            {'key': 'home',        'label': 'Dashboard',    'icon': '🏠', 'url': '/portal/teacher/home'},
            {'key': 'classrooms',  'label': 'Classrooms',   'icon': '📚', 'url': '/portal/teacher/classrooms',
             'badge': classrooms_with_open or None},
            {'key': 'marks',       'label': 'Exam Marks',   'icon': '📝', 'url': '/portal/teacher/marks',
             'badge': marks_entry_papers or None},
            {'key': 'assessments', 'label': 'Assessments',  'icon': '✅', 'url': '/portal/teacher/assessments'},
            {'key': 'profile',     'label': 'My Profile',   'icon': '👤', 'url': '/portal/teacher/profile'},
        ]
        return items

    # ─── Home (Dashboard) ───────────────────────────────────
    @http.route('/portal/teacher/home', type='http', auth='user', website=False)
    def teacher_home(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', employee.id)])
        # Build status info per classroom
        classroom_cards = []
        for cl in classrooms:
            marks_papers = ExamPaper.search_count([
                ('batch_id', '=', cl.batch_id.id),
                ('curriculum_line_id', '=', cl.curriculum_line_id.id),
                ('teacher_id', '=', employee.id),
                ('state', '=', 'marks_entry'),
            ])
            if marks_papers:
                status_label, status_class = 'Marks Due', 'badge-danger'
            elif cl.state == 'active':
                status_label, status_class = 'Active', 'badge-success'
            else:
                status_label, status_class = cl.state.title(), 'badge-muted'
            classroom_cards.append({
                'classroom': cl,
                'status_label': status_label,
                'status_class': status_class,
                'detail_url': '/portal/teacher/classroom/%d' % cl.id,
            })
        context = base_context(active_item='home', page_title='Dashboard')
        context.update({
            'employee': employee,
            'classroom_cards': classroom_cards,
            'total_classrooms': len(classrooms),
            'total_students': sum(classrooms.mapped('student_count')),
            'pending_marks': ExamPaper.search_count([
                ('teacher_id', '=', employee.id), ('state', '=', 'marks_entry'),
            ]),
            'sidebar_items': self._teacher_sidebar_items(employee, 'home'),
        })
        return request.render('edu_portal.teacher_home_page', context)

    # ─── Classrooms List ────────────────────────────────────
    @http.route('/portal/teacher/classrooms', type='http', auth='user', website=False)
    def teacher_classrooms(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classrooms = request.env['edu.classroom'].sudo().search(
            [('teacher_id', '=', employee.id)],
        )
        context = base_context(active_item='classrooms', page_title='My Classrooms')
        context.update({
            'employee': employee,
            'classrooms': classrooms,
            'sidebar_items': self._teacher_sidebar_items(employee, 'classrooms'),
        })
        return request.render('edu_portal.teacher_classrooms_page', context)

    # ─── Classroom Detail ───────────────────────────────────
    @http.route('/portal/teacher/classroom/<int:classroom_id>', type='http', auth='user', website=False)
    def teacher_classroom_detail(self, classroom_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
        if not classroom.exists() or not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        # Get active students in this section
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ])
        students = histories.mapped('student_id')
        context = base_context(
            active_item='classrooms',
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'classroom': classroom,
            'students': students,
            'sidebar_items': self._teacher_sidebar_items(employee, 'classrooms'),
        })
        return request.render('edu_portal.teacher_classroom_detail_page', context)

    # ─── Profile ────────────────────────────────────────────
    @http.route('/portal/teacher/profile', type='http', auth='user', website=False)
    def teacher_profile(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        context = base_context(active_item='profile', page_title='My Profile')
        context.update({
            'employee': employee,
            'sidebar_items': self._teacher_sidebar_items(employee, 'profile'),
        })
        return request.render('edu_portal.teacher_profile_page', context)
```

- [ ] **Step 2: Create `teacher_templates.xml` (home, classrooms, classroom detail, profile)**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Teacher Home / Dashboard
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_home_page" name="Teacher Home">
        <t t-call="edu_portal.portal_layout">
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">My Classrooms</p>
                    <p class="card-value"><t t-esc="total_classrooms"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Total Students</p>
                    <p class="card-value"><t t-esc="total_students"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Marks Due</p>
                    <p class="card-value"><t t-esc="pending_marks"/></p>
                </div>
            </div>
            <div class="dashboard-grid">
                <div>
                    <h2 class="page-title">My Classrooms</h2>
                    <t t-if="classroom_cards">
                        <t t-foreach="classroom_cards" t-as="card">
                            <t t-call="edu_portal.classroom_card_component">
                                <t t-set="classroom" t-value="card['classroom']"/>
                                <t t-set="status_label" t-value="card['status_label']"/>
                                <t t-set="status_class" t-value="card['status_class']"/>
                                <t t-set="detail_url" t-value="card['detail_url']"/>
                            </t>
                        </t>
                    </t>
                    <t t-else="">
                        <t t-call="edu_portal.empty_state_component">
                            <t t-set="icon" t-value="'📚'"/>
                            <t t-set="title" t-value="'No classrooms assigned'"/>
                            <t t-set="message" t-value="'Classrooms will appear here once an administrator assigns you as the teacher.'"/>
                        </t>
                    </t>
                </div>
                <aside>
                    <div class="card">
                        <p class="card-title">Quick Links</p>
                        <a class="btn btn-secondary btn-sm" href="/portal/teacher/classrooms">All Classrooms</a>
                    </div>
                </aside>
            </div>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Teacher Classrooms List
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_classrooms_page" name="Teacher Classrooms">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Classrooms</h2>
            <t t-if="classrooms">
                <t t-foreach="classrooms" t-as="cl">
                    <a t-attf-href="/portal/teacher/classroom/#{cl.id}" class="classroom-card">
                        <div class="classroom-card-info">
                            <h3><t t-esc="cl.name"/></h3>
                            <p>
                                <t t-esc="cl.batch_id.name"/> ·
                                <t t-esc="cl.section_id.name"/> ·
                                <t t-esc="cl.subject_id.name"/>
                            </p>
                        </div>
                        <span class="classroom-card-badge badge-muted"><t t-esc="cl.state.title()"/></span>
                    </a>
                </t>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'📚'"/>
                    <t t-set="title" t-value="'No classrooms'"/>
                    <t t-set="message" t-value="'No classrooms have been assigned to you yet.'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Teacher Classroom Detail
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_classroom_detail_page" name="Teacher Classroom Detail">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title"><t t-esc="classroom.name"/></h2>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Students</p>
                    <p class="card-value"><t t-esc="len(students)"/></p>
                </div>
                <div class="card">
                    <p class="card-title">State</p>
                    <p class="card-value"><t t-esc="classroom.state.title()"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Section</p>
                    <p class="card-value"><t t-esc="classroom.section_id.name"/></p>
                </div>
            </div>

            <div class="card">
                <p class="card-title">Quick Actions</p>
                <a class="btn btn-primary btn-sm" t-attf-href="/portal/teacher/attendance/#{classroom.id}">Mark Attendance</a>
                <a class="btn btn-secondary btn-sm" t-attf-href="/portal/teacher/assessments/#{classroom.id}">View Assessments</a>
                <a class="btn btn-secondary btn-sm" t-attf-href="/portal/teacher/roster/#{classroom.id}">Student Roster</a>
            </div>

            <h3 class="page-title" style="margin-top:30px;">Students</h3>
            <table class="data-table">
                <thead>
                    <tr><th>Roll</th><th>Name</th><th>Student ID</th></tr>
                </thead>
                <tbody>
                    <t t-foreach="students" t-as="s">
                        <tr>
                            <td><t t-esc="s.admission_number or ''"/></td>
                            <td><t t-esc="s.display_name"/></td>
                            <td><t t-esc="s.student_no or ''"/></td>
                        </tr>
                    </t>
                </tbody>
            </table>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Teacher Profile
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_profile_page" name="Teacher Profile">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Profile</h2>
            <div class="card">
                <p class="card-title">Name</p>
                <p class="card-value"><t t-esc="employee.name"/></p>
            </div>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Employee Code</p>
                    <p class="card-value" style="font-size:18px;"><t t-esc="employee.employee_code or '—'"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Department</p>
                    <p class="card-value" style="font-size:18px;"><t t-esc="employee.edu_department_id.name or '—'"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Staff Type</p>
                    <p class="card-value" style="font-size:18px;"><t t-esc="dict(employee._fields['staff_type'].selection).get(employee.staff_type, '—')"/></p>
                </div>
            </div>
        </t>
    </template>
</odoo>
```

- [ ] **Step 3: Commit**

```bash
git add edu_portal/controllers/teacher.py edu_portal/views/teacher_templates.xml
git commit -m "feat(edu_portal): add teacher controller and core page templates"
```

---

### Task 16: Teacher Attendance Entry

**Files:**
- Modify: `edu_portal/controllers/teacher.py` (append attendance routes)
- Modify: `edu_portal/views/teacher_templates.xml` (append attendance templates)

- [ ] **Step 1: Append attendance routes to `teacher.py`**

Append inside the `TeacherPortalController` class (before the closing class marker):

```python
    # ─── Attendance ─────────────────────────────────────────
    @http.route('/portal/teacher/attendance/<int:classroom_id>', type='http', auth='user', website=False)
    def teacher_attendance(self, classroom_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
        if not classroom.exists() or not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        # Get or create today's attendance sheet
        AttendanceSheet = request.env['edu.attendance.sheet'].sudo()
        register = classroom.attendance_register_id
        if not register:
            classroom._ensure_attendance_register()
            register = classroom.attendance_register_id
        # Find an in-progress or draft sheet, else get the latest
        sheet = AttendanceSheet.search([
            ('register_id', '=', register.id),
            ('state', 'in', ['draft', 'in_progress']),
        ], order='session_date desc', limit=1)
        context = base_context(
            active_item='classrooms',
            page_title='Attendance · %s' % classroom.name,
        )
        context.update({
            'employee': employee,
            'classroom': classroom,
            'sheet': sheet,
            'sidebar_items': self._teacher_sidebar_items(employee, 'classrooms'),
        })
        return request.render('edu_portal.teacher_attendance_page', context)

    @http.route('/portal/teacher/attendance/mark', type='http', auth='user', methods=['POST'], website=False, csrf=False)
    def teacher_attendance_mark(self, line_id, status, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.not_found()
        line = request.env['edu.attendance.sheet.line'].sudo().browse(int(line_id))
        if not line.exists():
            return request.not_found()
        classroom = line.classroom_id
        if not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        if status not in ('present', 'absent', 'late', 'excused'):
            return request.not_found()
        line.write({'status': status})
        # Return the updated row
        return request.render('edu_portal.teacher_attendance_row_partial', {
            'line': line,
        })
```

- [ ] **Step 2: Append attendance templates to `teacher_templates.xml`**

Append before `</odoo>`:

```xml
    <!-- ══════════════════════════════════════════════════════
         Teacher Attendance Entry Page
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_attendance_page" name="Teacher Attendance">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">Attendance · <t t-esc="classroom.name"/></h2>
            <t t-if="not sheet">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'✓'"/>
                    <t t-set="title" t-value="'No active attendance sheet'"/>
                    <t t-set="message" t-value="'An attendance sheet needs to be created for today before you can mark attendance.'"/>
                </t>
            </t>
            <t t-else="">
                <div class="card">
                    <p class="card-title">Session</p>
                    <p class="card-value" style="font-size:18px;"><t t-esc="sheet.session_date"/></p>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width:80px;">Roll</th>
                            <th>Student</th>
                            <th style="width:320px;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        <t t-foreach="sheet.line_ids" t-as="line">
                            <t t-call="edu_portal.teacher_attendance_row_partial">
                                <t t-set="line" t-value="line"/>
                            </t>
                        </t>
                    </tbody>
                </table>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         HTMX Partial: Single attendance row
         Returned when a status is clicked — replaces the row.
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_attendance_row_partial" name="Teacher Attendance Row">
        <tr t-att-data-line-id="line.id" data-attendance-row="1" tabindex="0">
            <td><t t-esc="line.roll_number or ''"/></td>
            <td><t t-esc="line.student_id.display_name"/></td>
            <td>
                <t t-set="s" t-value="line.status"/>
                <button type="button"
                        t-attf-class="status-btn #{'active-present' if s == 'present' else ''}"
                        hx-post="/portal/teacher/attendance/mark"
                        hx-vals='{"line_id": "%d", "status": "present"}' t-att-hx-vals='{"line_id": "%d" % line.id + ", \"status\": \"present\""}'
                        hx-target="closest tr"
                        hx-swap="outerHTML">P</button>
                <button type="button"
                        t-attf-class="status-btn #{'active-absent' if s == 'absent' else ''}"
                        hx-post="/portal/teacher/attendance/mark"
                        t-attf-hx-vals='#{{}}&quot;line_id&quot;: &quot;{line.id}&quot;, &quot;status&quot;: &quot;absent&quot;#{{}}'
                        hx-target="closest tr"
                        hx-swap="outerHTML">A</button>
                <button type="button"
                        t-attf-class="status-btn #{'active-late' if s == 'late' else ''}"
                        hx-post="/portal/teacher/attendance/mark"
                        t-attf-hx-vals='#{{}}&quot;line_id&quot;: &quot;{line.id}&quot;, &quot;status&quot;: &quot;late&quot;#{{}}'
                        hx-target="closest tr"
                        hx-swap="outerHTML">L</button>
                <button type="button"
                        t-attf-class="status-btn #{'active-excused' if s == 'excused' else ''}"
                        hx-post="/portal/teacher/attendance/mark"
                        t-attf-hx-vals='#{{}}&quot;line_id&quot;: &quot;{line.id}&quot;, &quot;status&quot;: &quot;excused&quot;#{{}}'
                        hx-target="closest tr"
                        hx-swap="outerHTML">E</button>
            </td>
        </tr>
    </template>
```

> **Implementation note**: HTMX `hx-vals` JSON attributes are awkward in QWeb. If the `t-attf-hx-vals` approach above causes XML issues, switch to explicit `<form>` submission per button or use `hx-include` pointing to hidden inputs. The simplest reliable approach is:
>
> ```xml
> <form hx-post="/portal/teacher/attendance/mark" hx-target="closest tr" hx-swap="outerHTML" style="display:inline">
>     <input type="hidden" name="line_id" t-att-value="line.id"/>
>     <input type="hidden" name="status" value="present"/>
>     <button type="submit" t-attf-class="status-btn #{'active-present' if s == 'present' else ''}">P</button>
> </form>
> ```
>
> Use the form pattern — it's cleaner than embedded JSON in attributes.

- [ ] **Step 3: Refactor the row partial to use the form pattern**

Replace the `teacher_attendance_row_partial` template body with:

```xml
    <template id="teacher_attendance_row_partial" name="Teacher Attendance Row">
        <tr t-att-data-line-id="line.id" data-attendance-row="1" tabindex="0">
            <td><t t-esc="line.roll_number or ''"/></td>
            <td><t t-esc="line.student_id.display_name"/></td>
            <td>
                <t t-foreach="[('present','P','active-present'), ('absent','A','active-absent'), ('late','L','active-late'), ('excused','E','active-excused')]" t-as="opt">
                    <form hx-post="/portal/teacher/attendance/mark"
                          hx-target="closest tr"
                          hx-swap="outerHTML"
                          style="display:inline">
                        <input type="hidden" name="line_id" t-att-value="line.id"/>
                        <input type="hidden" name="status" t-att-value="opt[0]"/>
                        <button type="submit"
                                t-attf-class="status-btn #{opt[2] if line.status == opt[0] else ''}">
                            <t t-esc="opt[1]"/>
                        </button>
                    </form>
                </t>
            </td>
        </tr>
    </template>
```

- [ ] **Step 4: Commit**

```bash
git add edu_portal/controllers/teacher.py edu_portal/views/teacher_templates.xml
git commit -m "feat(edu_portal): add teacher attendance entry with HTMX live updates"
```

---

### Task 17: Teacher Marks Entry

**Files:**
- Modify: `edu_portal/controllers/teacher.py` (append marks routes)
- Modify: `edu_portal/views/teacher_templates.xml` (append marks templates)

- [ ] **Step 1: Append marks routes to `teacher.py`**

Append inside `TeacherPortalController`:

```python
    # ─── Marks Entry ────────────────────────────────────────
    @http.route('/portal/teacher/marks', type='http', auth='user', website=False)
    def teacher_marks_list(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        papers = request.env['edu.exam.paper'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'marks_entry'),
        ])
        context = base_context(active_item='marks', page_title='Marks Entry')
        context.update({
            'employee': employee,
            'papers': papers,
            'sidebar_items': self._teacher_sidebar_items(employee, 'marks'),
        })
        return request.render('edu_portal.teacher_marks_list_page', context)

    @http.route('/portal/teacher/marks/<int:paper_id>', type='http', auth='user', website=False)
    def teacher_marks_entry(self, paper_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        paper = request.env['edu.exam.paper'].sudo().browse(paper_id)
        if not paper.exists() or paper.teacher_id != employee:
            return request.not_found()
        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('exam_paper_id', '=', paper.id),
            ('is_latest_attempt', '=', True),
        ])
        context = base_context(active_item='marks', page_title='Marks · %s' % paper.display_name)
        context.update({
            'employee': employee,
            'paper': paper,
            'marksheets': marksheets,
            'sidebar_items': self._teacher_sidebar_items(employee, 'marks'),
        })
        return request.render('edu_portal.teacher_marks_entry_page', context)

    @http.route('/portal/teacher/marks/save', type='http', auth='user', methods=['POST'], website=False, csrf=False)
    def teacher_marks_save(self, marksheet_id, marks_obtained, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.not_found()
        marksheet = request.env['edu.exam.marksheet'].sudo().browse(int(marksheet_id))
        if not marksheet.exists() or marksheet.exam_paper_id.teacher_id != employee:
            return request.not_found()
        try:
            marks_value = float(marks_obtained) if marks_obtained else 0.0
        except (TypeError, ValueError):
            return request.not_found()
        if marks_value < 0 or marks_value > marksheet.max_marks:
            return request.render('edu_portal.teacher_marks_row_partial', {
                'marksheet': marksheet,
                'error': 'Invalid marks: must be between 0 and %s' % marksheet.max_marks,
            })
        marksheet.write({'marks_obtained': marks_value})
        return request.render('edu_portal.teacher_marks_row_partial', {
            'marksheet': marksheet,
            'error': None,
        })
```

- [ ] **Step 2: Append marks templates to `teacher_templates.xml`**

Append before `</odoo>`:

```xml
    <!-- ══════════════════════════════════════════════════════
         Teacher Marks Entry List
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_marks_list_page" name="Teacher Marks List">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">Exam Marks Entry</h2>
            <t t-if="papers">
                <t t-foreach="papers" t-as="p">
                    <a t-attf-href="/portal/teacher/marks/#{p.id}" class="classroom-card">
                        <div class="classroom-card-info">
                            <h3><t t-esc="p.display_name"/></h3>
                            <p>
                                <t t-esc="p.exam_session_id.name"/> ·
                                Max: <t t-esc="p.max_marks"/>
                            </p>
                        </div>
                        <span class="classroom-card-badge badge-warning">Entry Open</span>
                    </a>
                </t>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'📝'"/>
                    <t t-set="title" t-value="'No marks entry open'"/>
                    <t t-set="message" t-value="'When exam papers are in marks_entry state, they will appear here.'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Teacher Marks Entry Grid
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_marks_entry_page" name="Teacher Marks Entry">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title"><t t-esc="paper.display_name"/></h2>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Max Marks</p>
                    <p class="card-value"><t t-esc="paper.max_marks"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Pass Marks</p>
                    <p class="card-value"><t t-esc="paper.pass_marks"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Students</p>
                    <p class="card-value"><t t-esc="len(marksheets)"/></p>
                </div>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width:80px;">Roll</th>
                        <th>Student</th>
                        <th style="width:160px;">Marks</th>
                        <th style="width:120px;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="marksheets" t-as="ms">
                        <t t-call="edu_portal.teacher_marks_row_partial">
                            <t t-set="marksheet" t-value="ms"/>
                            <t t-set="error" t-value="None"/>
                        </t>
                    </t>
                </tbody>
            </table>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         HTMX Partial: Single marks row
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_marks_row_partial" name="Teacher Marks Row">
        <tr t-att-data-marksheet-id="marksheet.id">
            <td><t t-esc="marksheet.student_id.admission_number or ''"/></td>
            <td><t t-esc="marksheet.student_id.display_name"/></td>
            <td>
                <form hx-post="/portal/teacher/marks/save"
                      hx-target="closest tr"
                      hx-swap="outerHTML"
                      hx-trigger="change from:input"
                      style="display:inline">
                    <input type="hidden" name="marksheet_id" t-att-value="marksheet.id"/>
                    <input type="number"
                           name="marks_obtained"
                           class="input"
                           style="width:120px;"
                           step="0.01"
                           min="0"
                           t-att-max="marksheet.max_marks"
                           t-att-value="marksheet.marks_obtained"
                           data-marks-input="1"/>
                </form>
                <t t-if="error">
                    <div style="color:#fee2e2; font-size:11px; margin-top:4px;"><t t-esc="error"/></div>
                </t>
            </td>
            <td>
                <t t-if="marksheet.marks_obtained &gt;= marksheet.pass_marks">
                    <span class="classroom-card-badge badge-success">Pass</span>
                </t>
                <t t-else="">
                    <span class="classroom-card-badge badge-danger">Fail</span>
                </t>
            </td>
        </tr>
    </template>
```

- [ ] **Step 3: Commit**

```bash
git add edu_portal/controllers/teacher.py edu_portal/views/teacher_templates.xml
git commit -m "feat(edu_portal): add teacher marks entry with HTMX live save"
```

---

### Task 18: Teacher Assessments

**Files:**
- Modify: `edu_portal/controllers/teacher.py` (append assessment routes)
- Modify: `edu_portal/views/teacher_templates.xml` (append assessment templates)

- [ ] **Step 1: Append assessment routes to `teacher.py`**

```python
    # ─── Assessments ────────────────────────────────────────
    @http.route('/portal/teacher/assessments', type='http', auth='user', website=False)
    def teacher_assessments_list(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classrooms = request.env['edu.classroom'].sudo().search(
            [('teacher_id', '=', employee.id)],
        )
        context = base_context(active_item='assessments', page_title='Assessments')
        context.update({
            'employee': employee,
            'classrooms': classrooms,
            'sidebar_items': self._teacher_sidebar_items(employee, 'assessments'),
        })
        return request.render('edu_portal.teacher_assessments_list_page', context)

    @http.route('/portal/teacher/assessments/<int:classroom_id>', type='http', auth='user', website=False)
    def teacher_classroom_assessments(self, classroom_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
        if not classroom.exists() or not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc', limit=100)
        context = base_context(
            active_item='assessments',
            page_title='Assessments · %s' % classroom.name,
        )
        context.update({
            'employee': employee,
            'classroom': classroom,
            'records': records,
            'sidebar_items': self._teacher_sidebar_items(employee, 'assessments'),
        })
        return request.render('edu_portal.teacher_classroom_assessments_page', context)
```

- [ ] **Step 2: Append assessment templates**

```xml
    <!-- ══════════════════════════════════════════════════════
         Teacher Assessments List (all classrooms)
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_assessments_list_page" name="Teacher Assessments List">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">Continuous Assessments</h2>
            <p style="color:var(--text-muted); margin-bottom:20px;">Select a classroom to view assessments.</p>
            <t t-foreach="classrooms" t-as="cl">
                <a t-attf-href="/portal/teacher/assessments/#{cl.id}" class="classroom-card">
                    <div class="classroom-card-info">
                        <h3><t t-esc="cl.name"/></h3>
                        <p><t t-esc="cl.section_id.name"/> · <t t-esc="cl.subject_id.name"/></p>
                    </div>
                    <span class="classroom-card-badge badge-muted">View</span>
                </a>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Teacher Classroom Assessments
    ══════════════════════════════════════════════════════ -->
    <template id="teacher_classroom_assessments_page" name="Teacher Classroom Assessments">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">Assessments · <t t-esc="classroom.name"/></h2>
            <t t-if="records">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Student</th>
                            <th>Category</th>
                            <th>Marks</th>
                            <th>State</th>
                        </tr>
                    </thead>
                    <tbody>
                        <t t-foreach="records" t-as="r">
                            <tr>
                                <td><t t-esc="r.assessment_date"/></td>
                                <td><t t-esc="r.student_id.display_name"/></td>
                                <td><t t-esc="r.category_id.name"/></td>
                                <td><t t-esc="r.marks_obtained"/> / <t t-esc="r.max_marks"/></td>
                                <td><span class="classroom-card-badge badge-muted"><t t-esc="r.state.title()"/></span></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'✅'"/>
                    <t t-set="title" t-value="'No assessments yet'"/>
                    <t t-set="message" t-value="'Use the backend bulk generate wizard to create assessment records.'"/>
                </t>
            </t>
        </t>
    </template>
```

- [ ] **Step 3: Commit**

```bash
git add edu_portal/controllers/teacher.py edu_portal/views/teacher_templates.xml
git commit -m "feat(edu_portal): add teacher assessments list view"
```

---

### Task 19: Student Controller & Templates

**Files:**
- Create: `edu_portal/controllers/student.py`
- Create: `edu_portal/views/student_templates.xml`

- [ ] **Step 1: Create `student.py`**

```python
"""Student portal controllers."""
from odoo import http
from odoo.http import request
from .helpers import base_context, get_student_record, get_portal_role


class StudentPortalController(http.Controller):

    def _guard_student(self):
        user = request.env.user
        if get_portal_role(user) != 'student':
            return None
        return get_student_record(user)

    def _student_sidebar_items(self, student, active=None):
        return [
            {'key': 'home',        'label': 'Dashboard',   'icon': '🏠', 'url': '/portal/student/home'},
            {'key': 'attendance',  'label': 'Attendance',  'icon': '✓', 'url': '/portal/student/attendance'},
            {'key': 'results',     'label': 'Results',     'icon': '📊', 'url': '/portal/student/results'},
            {'key': 'assessments', 'label': 'Assessments', 'icon': '📝', 'url': '/portal/student/assessments'},
            {'key': 'fees',        'label': 'Fees',        'icon': '💰', 'url': '/portal/student/fees'},
            {'key': 'profile',     'label': 'Profile',     'icon': '👤', 'url': '/portal/student/profile'},
        ]

    @http.route('/portal/student/home', type='http', auth='user', website=False)
    def student_home(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        lines = request.env['edu.attendance.sheet.line'].search(
            [('student_id', '=', student.id)], limit=30, order='session_date desc',
        )
        total = len(lines)
        present = len(lines.filtered(lambda l: l.status == 'present'))
        attendance_pct = round((present / total) * 100, 1) if total else 0.0
        marksheets = request.env['edu.exam.marksheet'].search(
            [('student_id', '=', student.id)], limit=5, order='create_date desc',
        )
        dues = request.env['edu.student.fee.due'].search(
            [('student_id', '=', student.id), ('state', '!=', 'paid')],
        )
        outstanding = sum(dues.mapped('balance_amount')) if dues else 0.0
        context = base_context(active_item='home', page_title='Dashboard')
        context.update({
            'student': student,
            'attendance_pct': attendance_pct,
            'recent_marksheets': marksheets,
            'outstanding_dues': outstanding,
            'sidebar_items': self._student_sidebar_items(student, 'home'),
        })
        return request.render('edu_portal.student_home_page', context)

    @http.route('/portal/student/attendance', type='http', auth='user', website=False)
    def student_attendance(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        lines = request.env['edu.attendance.sheet.line'].search(
            [('student_id', '=', student.id)], order='session_date desc', limit=200,
        )
        context = base_context(active_item='attendance', page_title='My Attendance')
        context.update({
            'student': student,
            'lines': lines,
            'sidebar_items': self._student_sidebar_items(student, 'attendance'),
        })
        return request.render('edu_portal.student_attendance_page', context)

    @http.route('/portal/student/results', type='http', auth='user', website=False)
    def student_results(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        marksheets = request.env['edu.exam.marksheet'].search(
            [('student_id', '=', student.id)], order='create_date desc',
        )
        context = base_context(active_item='results', page_title='My Results')
        context.update({
            'student': student,
            'marksheets': marksheets,
            'sidebar_items': self._student_sidebar_items(student, 'results'),
        })
        return request.render('edu_portal.student_results_page', context)

    @http.route('/portal/student/assessments', type='http', auth='user', website=False)
    def student_assessments(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        records = request.env['edu.continuous.assessment.record'].search(
            [('student_id', '=', student.id)], order='assessment_date desc', limit=200,
        )
        context = base_context(active_item='assessments', page_title='My Assessments')
        context.update({
            'student': student,
            'records': records,
            'sidebar_items': self._student_sidebar_items(student, 'assessments'),
        })
        return request.render('edu_portal.student_assessments_page', context)

    @http.route('/portal/student/fees', type='http', auth='user', website=False)
    def student_fees(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        dues = request.env['edu.student.fee.due'].search(
            [('student_id', '=', student.id)], order='due_date',
        )
        payments = request.env['edu.student.payment'].search(
            [('student_id', '=', student.id)], order='payment_date desc',
        )
        total_due = sum(dues.mapped('balance_amount')) if dues else 0.0
        context = base_context(active_item='fees', page_title='My Fees')
        context.update({
            'student': student,
            'dues': dues,
            'payments': payments,
            'total_due': total_due,
            'sidebar_items': self._student_sidebar_items(student, 'fees'),
        })
        return request.render('edu_portal.student_fees_page', context)

    @http.route('/portal/student/profile', type='http', auth='user', website=False)
    def student_profile(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        context = base_context(active_item='profile', page_title='My Profile')
        context.update({
            'student': student,
            'sidebar_items': self._student_sidebar_items(student, 'profile'),
        })
        return request.render('edu_portal.student_profile_page', context)
```

- [ ] **Step 2: Create `student_templates.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Student Home
    ══════════════════════════════════════════════════════ -->
    <template id="student_home_page" name="Student Home">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">Welcome, <t t-esc="student.display_name"/></h2>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Attendance</p>
                    <p class="card-value"><t t-esc="attendance_pct"/>%</p>
                    <p class="card-sub">last 30 sessions</p>
                </div>
                <div class="card">
                    <p class="card-title">Outstanding Fees</p>
                    <p class="card-value"><t t-esc="'{:,.0f}'.format(outstanding_dues)"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Recent Results</p>
                    <p class="card-value"><t t-esc="len(recent_marksheets)"/></p>
                </div>
            </div>
            <div class="card">
                <p class="card-title">Recent Marksheets</p>
                <t t-if="recent_marksheets">
                    <t t-foreach="recent_marksheets" t-as="ms">
                        <div style="padding:8px 0; border-bottom:1px solid var(--glass-border);">
                            <strong><t t-esc="ms.exam_paper_id.display_name"/></strong> ·
                            <t t-esc="ms.marks_obtained"/> / <t t-esc="ms.max_marks"/>
                        </div>
                    </t>
                </t>
                <t t-else=""><p style="color:var(--text-muted);">No results yet.</p></t>
            </div>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Student Attendance
    ══════════════════════════════════════════════════════ -->
    <template id="student_attendance_page" name="Student Attendance">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Attendance</h2>
            <t t-if="lines">
                <table class="data-table">
                    <thead>
                        <tr><th>Date</th><th>Subject</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="lines" t-as="l">
                            <tr>
                                <td><t t-esc="l.session_date"/></td>
                                <td><t t-esc="l.subject_id.name or l.classroom_id.subject_id.name"/></td>
                                <td>
                                    <t t-if="l.status == 'present'"><span class="classroom-card-badge badge-success">Present</span></t>
                                    <t t-if="l.status == 'absent'"><span class="classroom-card-badge badge-danger">Absent</span></t>
                                    <t t-if="l.status == 'late'"><span class="classroom-card-badge badge-warning">Late</span></t>
                                    <t t-if="l.status == 'excused'"><span class="classroom-card-badge badge-muted">Excused</span></t>
                                </td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'✓'"/>
                    <t t-set="title" t-value="'No attendance records yet'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Student Results
    ══════════════════════════════════════════════════════ -->
    <template id="student_results_page" name="Student Results">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Results</h2>
            <t t-if="marksheets">
                <table class="data-table">
                    <thead>
                        <tr><th>Paper</th><th>Session</th><th>Marks</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="marksheets" t-as="ms">
                            <tr>
                                <td><t t-esc="ms.exam_paper_id.display_name"/></td>
                                <td><t t-esc="ms.exam_paper_id.exam_session_id.name"/></td>
                                <td><t t-esc="ms.marks_obtained"/> / <t t-esc="ms.max_marks"/></td>
                                <td>
                                    <t t-if="ms.marks_obtained &gt;= (ms.exam_paper_id.pass_marks or 0)">
                                        <span class="classroom-card-badge badge-success">Pass</span>
                                    </t>
                                    <t t-else="">
                                        <span class="classroom-card-badge badge-danger">Fail</span>
                                    </t>
                                </td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'📊'"/>
                    <t t-set="title" t-value="'No results published yet'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Student Assessments
    ══════════════════════════════════════════════════════ -->
    <template id="student_assessments_page" name="Student Assessments">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Assessments</h2>
            <t t-if="records">
                <table class="data-table">
                    <thead>
                        <tr><th>Date</th><th>Category</th><th>Title</th><th>Marks</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="records" t-as="r">
                            <tr>
                                <td><t t-esc="r.assessment_date"/></td>
                                <td><t t-esc="r.category_id.name"/></td>
                                <td><t t-esc="r.name or ''"/></td>
                                <td><t t-esc="r.marks_obtained"/> / <t t-esc="r.max_marks"/></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'📝'"/>
                    <t t-set="title" t-value="'No assessment records yet'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Student Fees
    ══════════════════════════════════════════════════════ -->
    <template id="student_fees_page" name="Student Fees">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Fees</h2>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Outstanding</p>
                    <p class="card-value"><t t-esc="'{:,.0f}'.format(total_due)"/></p>
                </div>
            </div>
            <h3 class="page-title" style="font-size:18px; margin-top:20px;">Dues</h3>
            <t t-if="dues">
                <table class="data-table">
                    <thead>
                        <tr><th>Due Date</th><th>Fee Head</th><th>Amount</th><th>Balance</th><th>State</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="dues" t-as="d">
                            <tr>
                                <td><t t-esc="d.due_date"/></td>
                                <td><t t-esc="d.fee_head_id.name"/></td>
                                <td><t t-esc="d.amount"/></td>
                                <td><t t-esc="d.balance_amount"/></td>
                                <td><span class="classroom-card-badge badge-muted"><t t-esc="d.state.title()"/></span></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else=""><p style="color:var(--text-muted);">No fee dues on record.</p></t>

            <h3 class="page-title" style="font-size:18px; margin-top:30px;">Payment History</h3>
            <t t-if="payments">
                <table class="data-table">
                    <thead>
                        <tr><th>Date</th><th>Reference</th><th>Amount</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="payments" t-as="p">
                            <tr>
                                <td><t t-esc="p.payment_date"/></td>
                                <td><t t-esc="p.display_name"/></td>
                                <td><t t-esc="p.amount"/></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else=""><p style="color:var(--text-muted);">No payments on record.</p></t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Student Profile
    ══════════════════════════════════════════════════════ -->
    <template id="student_profile_page" name="Student Profile">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Profile</h2>
            <div class="card">
                <p class="card-title">Name</p>
                <p class="card-value"><t t-esc="student.display_name"/></p>
            </div>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Student ID</p>
                    <p class="card-value" style="font-size:18px;"><t t-esc="student.student_no or '—'"/></p>
                </div>
                <div class="card">
                    <p class="card-title">Program</p>
                    <p class="card-value" style="font-size:18px;"><t t-esc="student.program_id.name or '—'"/></p>
                </div>
            </div>
        </t>
    </template>
</odoo>
```

- [ ] **Step 3: Commit**

```bash
git add edu_portal/controllers/student.py edu_portal/views/student_templates.xml
git commit -m "feat(edu_portal): add student portal controller and templates"
```

---

### Task 20: Parent Controller & Templates

**Files:**
- Create: `edu_portal/controllers/parent.py`
- Create: `edu_portal/views/parent_templates.xml`

- [ ] **Step 1: Create `parent.py`**

```python
"""Parent portal controllers."""
from odoo import http
from odoo.http import request
from .helpers import (
    base_context, get_guardian_record, get_parent_children, get_active_child, get_portal_role,
)


class ParentPortalController(http.Controller):

    def _guard_parent(self):
        user = request.env.user
        if get_portal_role(user) != 'parent':
            return None
        return get_guardian_record(user)

    def _parent_sidebar_items(self, guardian, active=None):
        return [
            {'key': 'home',        'label': 'Overview',    'icon': '🏠', 'url': '/portal/parent/home'},
            {'key': 'attendance',  'label': 'Attendance',  'icon': '✓', 'url': '/portal/parent/attendance'},
            {'key': 'results',     'label': 'Results',     'icon': '📊', 'url': '/portal/parent/results'},
            {'key': 'assessments', 'label': 'Assessments', 'icon': '📝', 'url': '/portal/parent/assessments'},
            {'key': 'fees',        'label': 'Fees',        'icon': '💰', 'url': '/portal/parent/fees'},
            {'key': 'profile',     'label': 'Profile',     'icon': '👤', 'url': '/portal/parent/profile'},
        ]

    def _base_parent_context(self, active_item, page_title):
        user = request.env.user
        guardian = self._guard_parent()
        children = get_parent_children(user)
        active_child = get_active_child(user)
        context = base_context(active_item=active_item, page_title=page_title)
        context.update({
            'guardian': guardian,
            'children': children,
            'active_child': active_child,
            'sidebar_items': self._parent_sidebar_items(guardian, active_item),
        })
        return context

    @http.route('/portal/parent/home', type='http', auth='user', website=False)
    def parent_home(self, **kw):
        user = request.env.user
        if not self._guard_parent():
            return request.redirect('/portal')
        children = get_parent_children(user)
        # Build per-child summary
        summaries = []
        for child in children:
            lines = request.env['edu.attendance.sheet.line'].search(
                [('student_id', '=', child.id)], limit=30,
            )
            total = len(lines)
            present = len(lines.filtered(lambda l: l.status == 'present'))
            pct = round((present / total) * 100, 1) if total else 0.0
            dues = request.env['edu.student.fee.due'].search(
                [('student_id', '=', child.id), ('state', '!=', 'paid')],
            )
            outstanding = sum(dues.mapped('balance_amount')) if dues else 0.0
            summaries.append({
                'student': child,
                'attendance_pct': pct,
                'outstanding': outstanding,
            })
        context = self._base_parent_context('home', 'Overview')
        context['summaries'] = summaries
        return request.render('edu_portal.parent_home_page', context)

    @http.route('/portal/parent/attendance', type='http', auth='user', website=False)
    def parent_attendance(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('attendance', 'Attendance')
        child = context['active_child']
        if child:
            context['lines'] = request.env['edu.attendance.sheet.line'].search(
                [('student_id', '=', child.id)], order='session_date desc', limit=200,
            )
        else:
            context['lines'] = []
        return request.render('edu_portal.parent_attendance_page', context)

    @http.route('/portal/parent/results', type='http', auth='user', website=False)
    def parent_results(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('results', 'Results')
        child = context['active_child']
        if child:
            context['marksheets'] = request.env['edu.exam.marksheet'].search(
                [('student_id', '=', child.id)], order='create_date desc',
            )
        else:
            context['marksheets'] = []
        return request.render('edu_portal.parent_results_page', context)

    @http.route('/portal/parent/assessments', type='http', auth='user', website=False)
    def parent_assessments(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('assessments', 'Assessments')
        child = context['active_child']
        if child:
            context['records'] = request.env['edu.continuous.assessment.record'].search(
                [('student_id', '=', child.id)], order='assessment_date desc', limit=200,
            )
        else:
            context['records'] = []
        return request.render('edu_portal.parent_assessments_page', context)

    @http.route('/portal/parent/fees', type='http', auth='user', website=False)
    def parent_fees(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('fees', 'Fees')
        child = context['active_child']
        if child:
            dues = request.env['edu.student.fee.due'].search(
                [('student_id', '=', child.id)], order='due_date',
            )
            payments = request.env['edu.student.payment'].search(
                [('student_id', '=', child.id)], order='payment_date desc',
            )
            context['dues'] = dues
            context['payments'] = payments
            context['total_due'] = sum(dues.mapped('balance_amount')) if dues else 0.0
        else:
            context['dues'] = []
            context['payments'] = []
            context['total_due'] = 0.0
        return request.render('edu_portal.parent_fees_page', context)

    @http.route('/portal/parent/profile', type='http', auth='user', website=False)
    def parent_profile(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('profile', 'My Profile')
        return request.render('edu_portal.parent_profile_page', context)
```

- [ ] **Step 2: Create `parent_templates.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Parent Home — Children Overview
    ══════════════════════════════════════════════════════ -->
    <template id="parent_home_page" name="Parent Home">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">Children Overview</h2>
            <t t-if="summaries">
                <t t-foreach="summaries" t-as="s">
                    <div class="card">
                        <h3 style="margin:0 0 12px 0; font-size:18px;">
                            <t t-esc="s['student'].display_name"/>
                        </h3>
                        <div class="stat-grid" style="margin-bottom:0;">
                            <div>
                                <p class="card-title">Attendance</p>
                                <p class="card-value" style="font-size:20px;"><t t-esc="s['attendance_pct']"/>%</p>
                            </div>
                            <div>
                                <p class="card-title">Outstanding</p>
                                <p class="card-value" style="font-size:20px;"><t t-esc="'{:,.0f}'.format(s['outstanding'])"/></p>
                            </div>
                        </div>
                    </div>
                </t>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'👨‍👩‍👧'"/>
                    <t t-set="title" t-value="'No children linked'"/>
                    <t t-set="message" t-value="'Please contact the school administrator.'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Parent Attendance (reuses student_attendance_page layout)
    ══════════════════════════════════════════════════════ -->
    <template id="parent_attendance_page" name="Parent Attendance">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">
                Attendance
                <t t-if="active_child"> · <t t-esc="active_child.display_name"/></t>
            </h2>
            <t t-if="lines">
                <table class="data-table">
                    <thead>
                        <tr><th>Date</th><th>Subject</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="lines" t-as="l">
                            <tr>
                                <td><t t-esc="l.session_date"/></td>
                                <td><t t-esc="l.subject_id.name or l.classroom_id.subject_id.name"/></td>
                                <td>
                                    <t t-if="l.status == 'present'"><span class="classroom-card-badge badge-success">Present</span></t>
                                    <t t-if="l.status == 'absent'"><span class="classroom-card-badge badge-danger">Absent</span></t>
                                    <t t-if="l.status == 'late'"><span class="classroom-card-badge badge-warning">Late</span></t>
                                    <t t-if="l.status == 'excused'"><span class="classroom-card-badge badge-muted">Excused</span></t>
                                </td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'✓'"/>
                    <t t-set="title" t-value="'No attendance records for the selected child'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Parent Results
    ══════════════════════════════════════════════════════ -->
    <template id="parent_results_page" name="Parent Results">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">
                Results
                <t t-if="active_child"> · <t t-esc="active_child.display_name"/></t>
            </h2>
            <t t-if="marksheets">
                <table class="data-table">
                    <thead>
                        <tr><th>Paper</th><th>Session</th><th>Marks</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="marksheets" t-as="ms">
                            <tr>
                                <td><t t-esc="ms.exam_paper_id.display_name"/></td>
                                <td><t t-esc="ms.exam_paper_id.exam_session_id.name"/></td>
                                <td><t t-esc="ms.marks_obtained"/> / <t t-esc="ms.max_marks"/></td>
                                <td>
                                    <t t-if="ms.marks_obtained &gt;= (ms.exam_paper_id.pass_marks or 0)">
                                        <span class="classroom-card-badge badge-success">Pass</span>
                                    </t>
                                    <t t-else="">
                                        <span class="classroom-card-badge badge-danger">Fail</span>
                                    </t>
                                </td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'📊'"/>
                    <t t-set="title" t-value="'No results for the selected child'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Parent Assessments
    ══════════════════════════════════════════════════════ -->
    <template id="parent_assessments_page" name="Parent Assessments">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">
                Assessments
                <t t-if="active_child"> · <t t-esc="active_child.display_name"/></t>
            </h2>
            <t t-if="records">
                <table class="data-table">
                    <thead>
                        <tr><th>Date</th><th>Category</th><th>Title</th><th>Marks</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="records" t-as="r">
                            <tr>
                                <td><t t-esc="r.assessment_date"/></td>
                                <td><t t-esc="r.category_id.name"/></td>
                                <td><t t-esc="r.name or ''"/></td>
                                <td><t t-esc="r.marks_obtained"/> / <t t-esc="r.max_marks"/></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <t t-call="edu_portal.empty_state_component">
                    <t t-set="icon" t-value="'📝'"/>
                    <t t-set="title" t-value="'No assessments for the selected child'"/>
                </t>
            </t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Parent Fees
    ══════════════════════════════════════════════════════ -->
    <template id="parent_fees_page" name="Parent Fees">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">
                Fees
                <t t-if="active_child"> · <t t-esc="active_child.display_name"/></t>
            </h2>
            <div class="stat-grid">
                <div class="card">
                    <p class="card-title">Outstanding</p>
                    <p class="card-value"><t t-esc="'{:,.0f}'.format(total_due)"/></p>
                </div>
            </div>
            <h3 class="page-title" style="font-size:18px; margin-top:20px;">Dues</h3>
            <t t-if="dues">
                <table class="data-table">
                    <thead>
                        <tr><th>Due Date</th><th>Fee Head</th><th>Amount</th><th>Balance</th><th>State</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="dues" t-as="d">
                            <tr>
                                <td><t t-esc="d.due_date"/></td>
                                <td><t t-esc="d.fee_head_id.name"/></td>
                                <td><t t-esc="d.amount"/></td>
                                <td><t t-esc="d.balance_amount"/></td>
                                <td><span class="classroom-card-badge badge-muted"><t t-esc="d.state.title()"/></span></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </t>
            <t t-else=""><p style="color:var(--text-muted);">No fee dues on record.</p></t>
        </t>
    </template>

    <!-- ══════════════════════════════════════════════════════
         Parent Profile
    ══════════════════════════════════════════════════════ -->
    <template id="parent_profile_page" name="Parent Profile">
        <t t-call="edu_portal.portal_layout">
            <h2 class="page-title">My Profile</h2>
            <t t-if="guardian">
                <div class="card">
                    <p class="card-title">Name</p>
                    <p class="card-value"><t t-esc="guardian.full_name"/></p>
                </div>
                <div class="stat-grid">
                    <div class="card">
                        <p class="card-title">Phone</p>
                        <p class="card-value" style="font-size:18px;"><t t-esc="guardian.phone or '—'"/></p>
                    </div>
                    <div class="card">
                        <p class="card-title">Email</p>
                        <p class="card-value" style="font-size:18px;"><t t-esc="guardian.email or '—'"/></p>
                    </div>
                </div>
            </t>
        </t>
    </template>
</odoo>
```

- [ ] **Step 3: Commit**

```bash
git add edu_portal/controllers/parent.py edu_portal/views/parent_templates.xml
git commit -m "feat(edu_portal): add parent portal controller and templates"
```

---

### Task 21: Backend Views — Portal Access Buttons

**Files:**
- Create: `edu_portal/views/edu_student_views.xml`
- Create: `edu_portal/views/edu_guardian_views.xml`
- Create: `edu_portal/views/hr_employee_views.xml`
- Create: `edu_portal/views/res_users_views.xml`

- [ ] **Step 1: Create `edu_student_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_edu_student_form_portal" model="ir.ui.view">
        <field name="name">edu.student.form.portal</field>
        <field name="model">edu.student</field>
        <field name="inherit_id" ref="edu_student.view_edu_student_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_grant_portal_access"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-user-plus"
                        invisible="portal_access">
                    <span>Grant Portal Access</span>
                </button>
                <button name="action_revoke_portal_access"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-user-times"
                        invisible="not portal_access">
                    <span>Revoke Portal Access</span>
                </button>
            </xpath>
        </field>
    </record>
</odoo>
```

> **Note:** If `edu_student.view_edu_student_form` does not have a `div[@name='button_box']`, use a different xpath anchor. Check the source view at `edu_student/views/` and adapt.

- [ ] **Step 2: Create `edu_guardian_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_edu_guardian_form_portal" model="ir.ui.view">
        <field name="name">edu.guardian.form.portal</field>
        <field name="model">edu.guardian</field>
        <field name="inherit_id" ref="edu_pre_admission_crm.view_edu_guardian_form"/>
        <field name="arch" type="xml">
            <xpath expr="//sheet" position="inside">
                <group string="Portal Access">
                    <field name="portal_access" readonly="1"/>
                    <field name="portal_user_id" readonly="1"/>
                    <button name="action_grant_portal_access"
                            type="object"
                            string="Grant Portal Access"
                            class="btn-primary"
                            invisible="portal_access"/>
                    <button name="action_revoke_portal_access"
                            type="object"
                            string="Revoke Portal Access"
                            invisible="not portal_access"/>
                </group>
            </xpath>
        </field>
    </record>
</odoo>
```

> **Note:** External ID `edu_pre_admission_crm.view_edu_guardian_form` — verify the actual ID before install using:
> ```bash
> grep 'id="view.*guardian.*form"' edu_pre_admission_crm/views/*.xml
> ```
> Update the `inherit_id` to whatever is found.

- [ ] **Step 3: Create `hr_employee_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_hr_employee_form_portal" model="ir.ui.view">
        <field name="name">hr.employee.form.portal</field>
        <field name="model">hr.employee</field>
        <field name="inherit_id" ref="hr.view_employee_form"/>
        <field name="arch" type="xml">
            <xpath expr="//notebook/page[@name='education']" position="inside">
                <group string="Portal Access" invisible="not is_teaching_staff">
                    <field name="portal_access" readonly="1"/>
                    <field name="portal_user_id" readonly="1"/>
                    <button name="action_grant_portal_access"
                            type="object"
                            string="Grant Portal Access"
                            class="btn-primary"
                            invisible="portal_access"/>
                    <button name="action_revoke_portal_access"
                            type="object"
                            string="Revoke Portal Access"
                            invisible="not portal_access"/>
                </group>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 4: Create `res_users_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_res_users_form_portal" model="ir.ui.view">
        <field name="name">res.users.form.portal</field>
        <field name="model">res.users</field>
        <field name="inherit_id" ref="base.view_users_form"/>
        <field name="arch" type="xml">
            <xpath expr="//sheet" position="inside">
                <group string="Education Portal" groups="base.group_system">
                    <field name="portal_role" readonly="1"/>
                </group>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 5: Commit**

```bash
git add edu_portal/views/edu_student_views.xml edu_portal/views/edu_guardian_views.xml edu_portal/views/hr_employee_views.xml edu_portal/views/res_users_views.xml
git commit -m "feat(edu_portal): add backend view extensions for portal access buttons"
```

---

### Task 22: Verify External IDs

**Files:**
- Read-only verification

- [ ] **Step 1: Verify external IDs used in view inherits**

```bash
cd /opt/custom_addons/education

# Student form
grep -rn 'id="view_edu_student_form"' edu_student/views/

# Guardian form
grep -rn 'id=".*guardian.*form"' edu_pre_admission_crm/views/

# HR employee form (Odoo core — should exist)
find /opt/odoo19/odoo/addons/hr -name "*.xml" | xargs grep -l 'id="view_employee_form"' | head -1

# base res.users form (Odoo core)
find /opt/odoo19/odoo/addons/base -name "*.xml" | xargs grep -l 'id="view_users_form"' | head -1
```

- [ ] **Step 2: Update any mismatched IDs**

If any grep returns empty or unexpected results, update the `inherit_id` in the corresponding view file and commit.

```bash
# Example fix if the guardian view ID is different
git add edu_portal/views/edu_guardian_views.xml
git commit -m "fix(edu_portal): correct guardian view inherit ID"
```

---

### Task 23: Install & Smoke Test

**Files:**
- Read-only verification

- [ ] **Step 1: Verify complete file structure**

```bash
cd /opt/custom_addons/education
find edu_portal/ -type f | sort
```

Expected output: ~28 files including controllers (6), models (5), views (9), security (2), data (1), static (4).

- [ ] **Step 2: Validate all XML files parse**

```bash
for f in edu_portal/**/*.xml; do
    python3 -c "import xml.etree.ElementTree as ET; ET.parse('$f')" && echo "OK: $f"
done
```

Expected: all files report "OK".

- [ ] **Step 3: Lint Python files**

```bash
ruff check edu_portal/
```

Expected: no errors beyond pre-existing F401 import warnings on `__init__.py` files.

- [ ] **Step 4: Compile Python files**

```bash
python3 -m py_compile edu_portal/**/*.py && echo "All Python files compile"
```

- [ ] **Step 5: Install the module**

```bash
odoo -c /etc/odoo19.conf -d <your_database> -i edu_portal --stop-after-init \
    --addons-path=/opt/odoo19/odoo/addons,/opt/odoo19/enterprise,/opt/custom_addons/education
```

Expected: clean install with no errors.

- [ ] **Step 6: Manual smoke test**

After installation, manually verify:

1. Go to **Students** → open any student → verify **Grant Portal Access** button appears
2. Click it → verify success notification → verify `portal_access = True`
3. Go to **Settings > Users & Companies > Users** → find the new user → verify `portal_role = student`
4. Log out, log in as the new student user
5. Verify redirect to `/portal/student/home`
6. Verify sidebar shows Dashboard, Attendance, Results, Assessments, Fees, Profile
7. Verify all pages load without errors
8. Toggle hamburger menu → verify sidebar collapses to icon rail
9. Repeat for a guardian (parent) and a teaching staff (teacher)
10. For teacher: verify attendance entry grid loads and HTMX updates work
11. For parent with multiple children: verify child selector dropdown in top bar

- [ ] **Step 7: Final commit of any fixes**

```bash
git add -A edu_portal/
git commit -m "feat(edu_portal): complete portal module — ready for testing"
```
