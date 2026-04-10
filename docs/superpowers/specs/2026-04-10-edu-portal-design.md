# edu_portal — Custom Portal Design Spec

**Date**: 2026-04-10
**Module**: `edu_portal`
**Status**: Approved
**Author**: Innovax Solutions

---

## Overview

A custom-designed web portal for students, teachers, and parents of the EMIS system. It provides a modern, interactive UI built on Odoo's HTTP controller layer with QWeb templates, custom CSS/JS, and HTMX for live updates. It does **not** use Odoo's default `portal` or `website` modules — the entire UI is custom-designed for the education domain.

All three user roles are `base.group_portal` users (free licensing in Odoo). Teachers replace their backend interaction with the portal entirely.

## Goals

1. Provide a polished, modern portal that students, teachers, and parents can use confidently without Odoo training
2. Teachers can mark attendance, enter exam marks, and record continuous assessments from the portal — no backend access needed
3. Students and parents have read-only access to their academic and financial data
4. No per-seat licensing cost — all users are portal users (free in Odoo)
5. Responsive design works on phones, tablets, and desktops
6. Installable as a single module depending on existing EMIS modules

## Non-Goals

- Online fee payment (future, requires payment gateway integration)
- Document uploads (assignments, scanned certificates)
- Messaging/chat between roles
- Push notifications or email alerts beyond welcome email
- Offline mode
- Native mobile apps
- Calendar/timetable features (depends on future `edu_timetable`)
- Report card PDF generation (uses existing `edu_exam` report template)

---

## Architecture

### Technology Stack

- **Backend**: Odoo 19 `http.Controller` routes (not `portal` or `website`)
- **Templates**: QWeb XML templates (server-rendered HTML)
- **Interactivity**: HTMX for partial page updates (no full-page reloads for data entry)
- **Styling**: Custom CSS with design tokens (CSS variables); vibrant gradient + glassmorphism aesthetic
- **JavaScript**: Vanilla JS for sidebar toggle, keyboard shortcuts in data entry grids
- **Auth**: Odoo's built-in session auth (`@http.route(auth='user')`)
- **HTMX**: Bundled locally (`static/src/vendor/htmx.min.js`), not CDN

### High-level data flow

```
Browser (HTMX-enabled)
    ↕ HTTP request/response
edu_portal controllers
    ↓ permission check (role + ownership)
    ↓ query existing EMIS models via env (sudo for teacher writes)
    ↓ render QWeb template with context
Odoo server → QWeb rendered HTML / fragment → Browser
```

---

## User Provisioning

### Portal Access Field

Each identity-bearing model gets a `portal_access` boolean field and a `Grant Portal Access` action button:

- **`edu.student`**: `portal_access` boolean; button triggers `action_grant_portal_access()`
- **`edu.guardian`**: `portal_access` boolean; button triggers `action_grant_portal_access()`
- **`hr.employee`**: `portal_access` boolean (visible only when `is_teaching_staff=True`); button triggers `action_grant_portal_access()`

### Grant Portal Access Action

`action_grant_portal_access()` performs the following:
1. Check if `partner_id` already has a linked `res.users` — if yes, add the appropriate portal group; if no, create a new `res.users` record
2. Assign the appropriate portal group (`group_edu_portal_student`, `group_edu_portal_parent`, or `group_edu_portal_teacher`)
3. Generate a temporary password (random 12-char string)
4. Optionally send a welcome email with credentials using a mail template
5. Set `portal_access = True` on the source record

### Revoke Access

A separate `action_revoke_portal_access()` action removes the user from the portal group. The `res.users` record is not deleted (for audit trail), just disabled via group removal.

---

## Security Groups

Three new groups in `edu_portal/security/security.xml`:

| Group | Inherits From | Purpose |
|-------|---------------|---------|
| `group_edu_portal_student` | `base.group_portal` | Student portal user — read-only own data |
| `group_edu_portal_parent` | `base.group_portal` | Parent portal user — read-only child data |
| `group_edu_portal_teacher` | `base.group_portal` | Teacher portal user — writes via controller with explicit checks |

All three are **portal users** (not internal users). This means:
- Free licensing in Odoo
- No Apps menu access
- No `/odoo/web` backend URL access
- All interaction happens at `/portal/*`

---

## Access Control Strategy

### Student & Parent (Record Rules)

Record rules scope `base.group_portal` access so student/parent portal users see only their own data. Defined in `edu_portal/security/security.xml`:

| Model | Group | Domain |
|-------|-------|--------|
| `edu.student` | `group_edu_portal_student` | `[('partner_id', '=', user.partner_id.id)]` |
| `edu.attendance.sheet.line` | `group_edu_portal_student` | `[('student_id.partner_id', '=', user.partner_id.id)]` |
| `edu.exam.marksheet` | `group_edu_portal_student` | `[('student_id.partner_id', '=', user.partner_id.id)]` |
| `edu.continuous.assessment.record` | `group_edu_portal_student` | `[('student_id.partner_id', '=', user.partner_id.id)]` |
| `edu.student.fee.due` | `group_edu_portal_student` | `[('student_id.partner_id', '=', user.partner_id.id)]` |
| `edu.student.fee.plan` | `group_edu_portal_student` | `[('student_id.partner_id', '=', user.partner_id.id)]` |
| `edu.student.payment` | `group_edu_portal_student` | `[('student_id.partner_id', '=', user.partner_id.id)]` |
| `edu.student` | `group_edu_portal_parent` | `[('partner_id', 'in', <parent's children partners>)]` (domain computed via guardian relationship — see Parent Domain Resolution below) |
| `edu.attendance.sheet.line` | `group_edu_portal_parent` | Traverse `student_id.partner_id` against parent's children partners |
| `edu.exam.marksheet` | `group_edu_portal_parent` | Same traversal |
| `edu.continuous.assessment.record` | `group_edu_portal_parent` | Same traversal |
| `edu.student.fee.due` | `group_edu_portal_parent` | Same traversal |
| `edu.student.fee.plan` | `group_edu_portal_parent` | Same traversal |
| `edu.student.payment` | `group_edu_portal_parent` | Same traversal |

### Parent Domain Resolution

The parent domain is complex because the chain is: `res.users.partner_id` → `edu.guardian` (linked by `partner_id`) → `edu.applicant.guardian.rel` (intermediate table) → `edu.applicant.profile` → `edu.student` (via applicant's student_id or enrollment). Since record rule domains can't easily express this chain, we create a computed helper method on `res.users`:

```python
def _get_parent_children_partner_ids(self):
    """Return partner IDs of all children (students) linked to this parent user via the guardian relationship.

    Chain: res.users.partner_id → edu.guardian → edu.applicant.guardian.rel
        → edu.applicant.profile → edu.student (via applicant_profile_id) → partner_id
    """
    self.ensure_one()
    guardian = self.env['edu.guardian'].sudo().search(
        [('partner_id', '=', self.partner_id.id)], limit=1
    )
    if not guardian:
        return []
    applicant_profiles = guardian.applicant_ids.mapped('applicant_id')
    students = self.env['edu.student'].sudo().search([
        ('applicant_profile_id', 'in', applicant_profiles.ids),
    ])
    return students.mapped('partner_id').ids
```

Record rule domains use this via a `user.` reference to a helper field. Since Odoo record rule domains can only call methods via `user`, we store the resolved IDs as a non-stored computed field on `res.users`:

```python
children_partner_ids = fields.Many2many(
    comodel_name='res.partner',
    compute='_compute_children_partner_ids',
    string='Children Partners (for parent portal rules)',
)
```

And the record rule domain becomes:
```python
[('student_id.partner_id', 'in', user.children_partner_ids.ids)]
```

Student/parent controllers use **normal ORM** (no sudo) — the record rules filter automatically.

### Teacher (Controller-Level Enforcement)

Teacher portal users do NOT get model-level record rules. All teacher writes go through controllers using `env.sudo()` with **explicit ownership checks**:

```python
# Example controller guard pattern
user = request.env.user
if user.portal_role != 'teacher':
    return request.not_found()

employee = user.employee_id
classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
if classroom.teacher_id != employee:
    return request.not_found()

# Authorized — perform write with sudo
request.env['edu.attendance.sheet.line'].sudo().write({...})
```

This makes the controller the single enforcement layer for teacher writes. No complex record rules try to express "can write if teacher_id matches".

### Existing edu_hr Backend Rules

The record rules in `edu_hr` (e.g., `rule_classroom_teacher_own`) remain valid but are **unused by portal teacher users** because portal users are not in the `group_classroom_teacher` / `group_exam_teacher` / `group_attendance_teacher` / `group_assessment_teacher` groups. These rules remain useful for admins or officers who have both portal and backend access.

---

## Role Detection

Extend `res.users` with a computed `portal_role` field:

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    portal_role = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('parent', 'Parent'),
            ('teacher', 'Teacher'),
            ('multi', 'Multiple'),
            ('none', 'None'),
        ],
        compute='_compute_portal_role',
    )

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
```

Multi-role users (e.g., a teacher whose own child is a student) get `portal_role = 'multi'` and see a role switcher in the top bar. The active role is stored in the session (`request.session.active_portal_role`).

---

## URL Structure

### Route map

```
── Root ──────────────────────────────
/portal                              → Role-based redirect to home

── Teacher routes ───────────────────
/portal/teacher/home                          → Dashboard (classroom-first list)
/portal/teacher/classrooms                    → All classrooms list
/portal/teacher/classroom/<int:id>            → Classroom detail (roster + stats)
/portal/teacher/attendance/<int:classroom_id> → Current attendance sheet
/portal/teacher/attendance/<int:classroom_id>/history → Past sheets
/portal/teacher/attendance/mark               → HTMX POST: mark student (line-level)
/portal/teacher/attendance/submit             → HTMX POST: submit/close sheet
/portal/teacher/marks/<int:paper_id>          → Marks entry grid
/portal/teacher/marks/save                    → HTMX POST: save single mark
/portal/teacher/assessments/<int:classroom_id> → Assessments list
/portal/teacher/assessment/new/<int:classroom_id> → New assessment form
/portal/teacher/assessment/save               → HTMX POST: save
/portal/teacher/roster/<int:classroom_id>     → Student roster view
/portal/teacher/profile                       → Own profile (hr.employee)

── Student routes ───────────────────
/portal/student/home                 → Dashboard
/portal/student/attendance           → Attendance history
/portal/student/results              → Exam results list
/portal/student/result/<int:session_id> → Single report card
/portal/student/assessments          → Continuous assessments history
/portal/student/fees                 → Fee dues + payment history
/portal/student/profile              → Own profile

── Parent routes ────────────────────
/portal/parent/home                  → Children overview
/portal/parent/switch-child/<int:student_id> → POST: set active child in session
/portal/parent/attendance            → Attendance for active child
/portal/parent/results               → Results for active child
/portal/parent/assessments           → Assessments for active child
/portal/parent/fees                  → Fees for active child
/portal/parent/profile               → Own profile (guardian record)

── Shared ───────────────────────────
/portal/sidebar-toggle               → HTMX POST: toggle sidebar state (session)
/portal/role-switch/<role>           → HTMX POST: switch role (multi-role users)
```

### Login flow

Users log in at the standard Odoo `/web/login` page (not rebuilt). After authentication, a redirect override on `res.users` or a `session.login` override redirects portal users to `/portal`. Non-portal internal users retain default backend redirect.

---

## Module Structure

```
edu_portal/
├── __manifest__.py
├── __init__.py
├── controllers/
│   ├── __init__.py
│   ├── main.py                  # /portal redirect, role detection
│   ├── teacher.py               # /portal/teacher/* routes
│   ├── student.py               # /portal/student/* routes
│   ├── parent.py                # /portal/parent/* routes
│   └── helpers.py               # Permission checks, shared utilities
├── models/
│   ├── __init__.py
│   ├── res_users.py             # portal_role computed field, login redirect
│   ├── edu_student.py           # portal_access + action_grant_portal_access
│   ├── edu_guardian.py          # portal_access + action_grant_portal_access
│   └── hr_employee.py           # portal_access + action_grant_portal_access
├── views/
│   ├── portal_layout.xml        # Master layout (sidebar + topbar + content slot)
│   ├── components/
│   │   ├── sidebar.xml
│   │   ├── topbar.xml
│   │   ├── stat_card.xml
│   │   ├── classroom_card.xml
│   │   └── empty_state.xml
│   ├── teacher/
│   │   ├── home.xml
│   │   ├── classroom_detail.xml
│   │   ├── attendance_sheet.xml
│   │   ├── attendance_row_partial.xml
│   │   ├── marks_grid.xml
│   │   ├── marks_row_partial.xml
│   │   ├── assessment_list.xml
│   │   ├── assessment_form.xml
│   │   └── roster.xml
│   ├── student/
│   │   ├── home.xml
│   │   ├── attendance.xml
│   │   ├── results.xml
│   │   ├── result_detail.xml
│   │   ├── assessments.xml
│   │   ├── fees.xml
│   │   └── profile.xml
│   ├── parent/
│   │   ├── home.xml
│   │   ├── attendance.xml
│   │   ├── results.xml
│   │   ├── assessments.xml
│   │   ├── fees.xml
│   │   └── profile.xml
│   ├── res_users_views.xml      # Backend: portal_role field on user form
│   ├── edu_student_views.xml    # Backend: Grant Portal Access button
│   ├── edu_guardian_views.xml   # Backend: Grant Portal Access button
│   └── hr_employee_views.xml    # Backend: Grant Portal Access button (teachers only)
├── security/
│   ├── security.xml             # 3 groups + record rules
│   └── ir.model.access.csv
├── data/
│   └── mail_templates.xml       # Welcome email template
└── static/
    └── src/
        ├── css/
        │   ├── portal.css       # Main stylesheet
        │   ├── sidebar.css      # Sidebar component
        │   └── forms.css        # Entry grid styles
        ├── js/
        │   ├── portal.js        # Sidebar toggle, child selector
        │   ├── attendance.js    # Grid keyboard shortcuts
        │   └── marks.js         # Marks grid tab navigation
        ├── img/
        │   └── logo.svg
        └── vendor/
            └── htmx.min.js      # Bundled HTMX library
```

### Dependencies

```python
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
```

No dependency on `portal` or `website`.

---

## UI Design

### Visual Direction

- **Base**: Vibrant purple gradient (`linear-gradient(135deg, #667eea 0%, #764ba2 100%)`) as body background
- **Cards**: Glassmorphism — semi-transparent white with `backdrop-filter: blur(10px)`, rounded corners (12px), subtle shadows
- **Typography**: Clean sans-serif (Inter or system font stack), generous spacing
- **Colors**: Primary purple/blue, accent yellow for warnings, red for overdue, green for success
- **Icons**: Heroicons or similar open-source icon set (SVG sprites for performance)

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ [≡] EMIS Portal                    [Role ▼] [User ▼]    │
├──────┬──────────────────────────────────────────────────┤
│      │                                                  │
│ [🏠] │   Classroom-first dashboard                      │
│ [📚] │   ┌─ Main panel ──────────┐  ┌─ Side ──┐        │
│ [✓] │   │  Classroom cards with │  │ Stats   │        │
│ [📝] │   │  inline status badges │  │ cards   │        │
│ [👥] │   │                       │  │         │        │
│ [👤] │   └───────────────────────┘  └─────────┘        │
│      │                                                  │
└──────┴──────────────────────────────────────────────────┘
```

When sidebar is collapsed (hamburger toggle):
- Sidebar shrinks to a narrow icon rail (~60px wide)
- Icons remain visible, labels hide
- Content area expands to fill reclaimed space
- State persists via session

### Dashboard per Role

**Teacher Dashboard (Classroom-First)**:
- Main panel: list of classrooms (cards) with inline status badges ("Marks due", "Attendance pending", "All caught up")
- Side panel: pending tasks count, total students count
- Clicking a classroom card opens `/portal/teacher/classroom/<id>`

**Student Dashboard**:
- Main panel: recent attendance status, upcoming exams (if any), recent assessment results
- Side panel: fee status card, overall attendance percentage

**Parent Dashboard**:
- Main panel: card per child showing quick stats (attendance %, pending fees, recent grade)
- Clicking a child card sets the active child and navigates to `/portal/parent/home` for that child

### Responsive behavior

- **Desktop / Tablet landscape** (≥ 1024px): Sidebar visible by default, can collapse to icon rail
- **Tablet portrait** (768–1023px): Sidebar collapses to icon rail by default, expandable
- **Mobile** (< 768px): Sidebar hidden; hamburger toggles slide-out drawer overlay; content fills viewport; stat cards stack vertically

### Sidebar behavior (icon rail)

- Toggle via hamburger button in top-left
- Expanded state: ~240px wide with icon + label
- Collapsed state: ~60px wide with icon only
- Active page highlighted with accent color + left border indicator
- Badges (red dot or count) on items with pending work
- State stored in session (sticky across page loads)

---

## Data Entry UX (Teacher)

### Attendance Grid

```
Grade 10A · Physics · Monday, April 10, 2026        [Submit Sheet]

[Mark All Present]  [Mark All Absent]  [Clear All]

┌─────┬─────────────┬──────────┬─────────────────────────┐
│ Roll│ Student     │ Present  │ Status                  │
├─────┼─────────────┼──────────┼─────────────────────────┤
│ 01  │ Alice Sharma│ (●)      │ [P] [A] [L] [E]         │
│ 02  │ Bob Thapa   │ ( )      │ [P] [A] [L] [E]         │
│ ... │ ...         │ ...      │ ...                     │
└─────┴─────────────┴──────────┴─────────────────────────┘
```

- Click a status button → HTMX POST to `/portal/teacher/attendance/mark` → server returns updated row HTML → HTMX swaps the row
- Keyboard shortcuts: P, A, L, E; arrow keys to navigate between rows
- "Mark All Present" bulk action with confirmation

### Marks Entry Grid

```
Paper: Physics Theory (Grade 10A) · Max Marks: 80 · Pass: 32

┌─────┬─────────────┬──────────┬──────────┬─────────────┐
│ Roll│ Student     │ Marks    │ Status   │ Remarks     │
├─────┼─────────────┼──────────┼──────────┼─────────────┤
│ 01  │ Alice Sharma│ [65.5]   │ Pass     │ [...]       │
│ 02  │ Bob Thapa   │ [ 28]    │ Fail     │ [...]       │
│ ... │ ...         │ ...      │ ...      │ ...         │
└─────┴─────────────┴──────────┴──────────┴─────────────┘

[Save All]  [Submit for Publishing]
```

- Tab key navigates between marks inputs (vertical flow)
- Each input saves on blur via HTMX POST to `/portal/teacher/marks/save`
- Status column computed server-side and returned in HTMX response
- Validation errors shown inline

### Assessment Form

Simple form to create a new continuous assessment record:
- Category (selection from active categories for this classroom)
- Title, description
- Max marks, assessment date
- Inline grid to enter marks for each student
- Save as draft or submit (lock)

---

## Notifications (Sidebar Badges)

Badges are computed from existing backend state — no new notification model:

**Teacher**:
- `Attendance (n)` — count of own classrooms with `attendance_register_id.state = 'open'` and sheets in `in_progress`
- `Exam Marks (n)` — count of own exam papers where `state = 'marks_entry'`
- `Assessments (n)` — count of own assessment records in `draft` state

**Student**:
- `Fees (!)` — red indicator if any `edu.fees.due` for student is `state = 'overdue'` or past `due_date`
- `Results` — green dot if new result session was recently published (within 7 days)

**Parent**:
- Per-child badges (in the child selector dropdown) showing child's pending items

Computed in the sidebar template via a helper method `_compute_sidebar_badges(user)` in `controllers/helpers.py` and passed to `portal_layout` as context.

---

## Testing Plan

Manual testing checklist (no automated tests — per project convention):

### Provisioning
1. Create a student → set `portal_access = True` → click Grant button → verify `res.users` created with `group_edu_portal_student`
2. Same for guardian → verify `group_edu_portal_parent`
3. Same for teaching staff → verify `group_edu_portal_teacher`
4. Verify welcome email sent with temporary password
5. Verify login with temporary password works

### Teacher Portal
1. Log in as teacher → verify landing at `/portal/teacher/home`
2. Verify classroom-first dashboard shows correct classrooms with status badges
3. Click a classroom → verify classroom detail shows roster and stats
4. Open attendance sheet → verify grid loads all students → mark some present → verify HTMX live update
5. Use keyboard shortcuts (P, A, L, E) → verify they work
6. Click "Mark All Present" → verify bulk update works
7. Open a paper in marks_entry state → verify grid loads → enter marks → verify tab navigation → verify save on blur
8. Create a new assessment → verify form saves and new record appears in list
9. Navigate to a classroom NOT owned by this teacher via direct URL → verify 404

### Student Portal
1. Log in as student → verify landing at `/portal/student/home`
2. Verify dashboard shows own attendance %, recent results, fee status
3. View attendance history → verify only own records visible
4. View exam results → verify only own marksheets visible
5. Navigate to `/portal/student/...` URL with another student's ID → verify access denied
6. View fees → verify only own dues visible

### Parent Portal
1. Log in as parent (guardian with multiple children) → verify landing at `/portal/parent/home`
2. Verify children overview shows all linked students
3. Click a child → verify child selector in top bar updates
4. View attendance/results/assessments/fees → verify data is for selected child
5. Switch child → verify context switches

### UI Behaviors
1. Toggle sidebar via hamburger → verify collapse/expand animation
2. Verify sidebar state persists on page reload (session)
3. Test on mobile (< 768px) → verify slide-out drawer behavior
4. Test on tablet (768–1023px) → verify collapsed-by-default icon rail
5. Verify all stat cards and buttons are reachable and visually correct

### Multi-role
1. Create a user with both teacher and parent roles → verify `portal_role = 'multi'`
2. Verify role switcher dropdown appears in top bar
3. Switch role → verify sidebar and content update

### Security
1. Try accessing `/portal/teacher/*` URL as student user → verify redirect/404
2. Try POST to `/portal/teacher/attendance/mark` with another teacher's classroom ID → verify 403/404
3. Verify student cannot read another student's records via any URL

---

## Open Questions (for implementation phase)

None — all architectural questions resolved during brainstorming.
