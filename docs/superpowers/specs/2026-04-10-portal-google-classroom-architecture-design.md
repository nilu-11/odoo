# Portal Architecture Refactor — Google Classroom UX & Modular Extension Hooks

**Date:** 2026-04-10
**Status:** Approved (design phase)
**Module:** `edu_portal`
**Author:** Innovax Solutions

## Goals

1. Replace the current top-level-feature-list portal with a Google-Classroom-style classroom hub: home page is a card grid of classrooms; clicking a card opens the classroom with tabs (Stream, Attendance, Exams, Assessments, Results, People).
2. Introduce a registry-based extension mechanism so future "extra" modules (e.g. `edu_assignment`, `edu_library`, `edu_notice`) can add sidebar items and classroom tabs without `edu_portal` knowing about them.
3. Add a real announcement model (Stream) so the classroom hub has a meaningful landing tab.
4. Keep `edu_portal` itself monolithic for the current core EMIS modules — the modular extension pattern applies only to **future** additions.

## Non-Goals

- Splitting current core modules (`edu_attendance`, `edu_exam`, etc.) into feature + bridge pairs. The core stays as-is.
- Building any actual extra/bridge module in this work — only the extension points.
- Comments, reactions, @mentions, scheduled posts, or notifications on Stream announcements.
- Mobile-specific responsive redesign beyond the existing breakpoints.
- Changes to parent-portal flows (out of scope; parent portal is unchanged).
- Automated test infrastructure (project has none; manual testing per `TESTING_PLAN.md`).

## Module Boundary

Three categories of modules going forward:

1. **`edu_portal`** — the portal shell. Owns the renderer, layout, registry models, the Stream announcement model, the core controllers, and XML data seeding the built-in tabs and sidebar items. Hard-depends on the core EMIS modules it renders (current dependency list is unchanged).

2. **Feature modules** (current and future) — pure business logic. **Zero knowledge of `edu_portal`.** A feature module must be installable without the portal.

3. **Bridge modules** (future, e.g. `edu_assignment_portal`) — thin glue modules that depend on both `edu_portal` and a feature module. Each bridge ships:
   - XML records into `edu.portal.classroom.tab` and/or `edu.portal.sidebar.item`
   - Controllers serving the routes those records point to
   - QWeb templates for the feature's portal pages

   Installing the bridge makes the integration appear; uninstalling removes the registry records and the tab/sidebar item disappears automatically.

The current core (`edu_attendance`, `edu_exam`, `edu_assessment`, `edu_result`, `edu_fees`, `edu_classroom`, …) does **not** get bridge modules. `edu_portal` ships their portal wiring directly. The bridge pattern is for new extras only.

## Registry Models

Two new models in `edu_portal`.

### `edu.portal.sidebar.item`

| Field | Type | Notes |
|---|---|---|
| `key` | Char | Unique identifier used for active-state highlighting |
| `label` | Char (translate) | Display text |
| `icon` | Char | Unicode glyph or class name |
| `sequence` | Integer | Sort order within the sidebar |
| `url` | Char | Target route |
| `role` | Selection | `teacher` / `student` / `parent` / `all` |
| `active` | Boolean | Soft-disable without deleting |
| `visibility_method` | Char | Optional dotted path `model.method` returning bool |
| `badge_method` | Char | Optional dotted path returning an int/str badge value |

### `edu.portal.classroom.tab`

| Field | Type | Notes |
|---|---|---|
| `key` | Char | Unique (`stream`, `attendance`, `exams`, `assessments`, `results`, `people`, future: `assignments`) |
| `label` | Char (translate) | |
| `icon` | Char | |
| `sequence` | Integer | Tab order |
| `route_pattern` | Char | Route template with a `{classroom_id}` placeholder |
| `role` | Selection | `teacher` / `student` / `all` |
| `active` | Boolean | |
| `visibility_method` | Char | Optional callable receiving `(classroom, user, role)` |

### Method resolution

Dotted path of form `edu.some.model.method_name`. The portal helper looks up the model via `self.env['edu.some.model']` and calls the method. If the model isn't in the registry (module not installed), the record is treated as visible-with-no-badge — never crashes the portal. Routes for missing modules will still 404 if visited, which is correct.

### Method resolution — dotted path parsing

Model names contain dots (`edu.portal.sidebar.item`), so dotted paths must be split on the **last** dot only: everything before is the model name, everything after is the method name. Resolution:

```python
model_name, method_name = dotted.rsplit('.', 1)
try:
    Model = self.env[model_name]              # KeyError if module missing
    method = getattr(Model, method_name)      # AttributeError if renamed
except (KeyError, AttributeError):
    continue  # silent skip — record treated as visible-no-badge
```

The method is called as a regular Odoo model method (`self.env[model].method()`) — **not** a Python `@classmethod`. It runs with the current environment and reads `self.env.user` for the actor.

### Seeding the built-ins

`edu_portal/data/portal_sidebar_data.xml` and `edu_portal/data/portal_classroom_tabs_data.xml` ship records for all built-in sidebar items and classroom tabs. Bridge modules only add new ones.

Both seed files load with **`noupdate="1"`** so admin edits to `active`, `sequence`, `label`, etc. survive module updates (`-u edu_portal`).

**Classroom tab seeding** — because permission logic and templates diverge by role, each of the 6 built-in tabs ships as **two records** — one with `role='teacher'` and one with `role='student'`. The seed file therefore contains 12 `edu.portal.classroom.tab` records. `route_pattern` substitutes only `{classroom_id}` at render time; the role is baked into the record itself.

## Rendering Pipeline

### Request flow

1. **Controller dispatch** — route is owned by `edu_portal` (core tab) or by a bridge module (future tabs). Either way, the controller does its own auth guard first.

2. **Build the shared context** via `controllers/helpers.py::build_portal_context(active_sidebar_key, active_tab_key, classroom=None, page_title=None)`. This replaces the current `base_context()` and centralizes:
   - **Sidebar items** — query `edu.portal.sidebar.item` filtered by `active=True` and matching role, ordered by `sequence`. Resolve `visibility_method` (skip if False) and `badge_method` (attach count). Missing target models → silent skip.
   - **Classroom tabs** — only if `classroom` is passed. Same query+filter+resolve logic against `edu.portal.classroom.tab`. URLs built via `route_pattern.format(classroom_id=classroom.id)`.
   - **Standard page vars** — `user`, `portal_role`, `page_title`, `sidebar_collapsed`, `active_sidebar_key`, `active_tab_key`.

3. **Template rendering** — page templates `t-call` `edu_portal.portal_layout`. A new `edu_portal.classroom_tabs_component` renders the tab bar; every in-classroom page template `t-call`s it above its content.

### Single resolution point

The entire registry read + method resolution lives in **one function**: `helpers.py::_resolve_portal_registry()`. Controllers never query registry models directly. This isolates the DI logic so it can be cached, swapped, or instrumented without touching controllers.

### Helper signature

```python
def build_portal_context(
    active_sidebar_key: str | None = None,
    active_tab_key: str | None = None,
    classroom=None,
    page_title: str | None = None,
) -> dict:
    ...
```

The current `_teacher_sidebar_items()` and `_student_sidebar_items()` methods are deleted entirely.

## Classroom Hub URLs & Controllers

### URL scheme

```
/portal/{role}/classroom/<int:classroom_id>              → redirects to /stream
/portal/{role}/classroom/<int:classroom_id>/stream
/portal/{role}/classroom/<int:classroom_id>/attendance
/portal/{role}/classroom/<int:classroom_id>/exams
/portal/{role}/classroom/<int:classroom_id>/assessments
/portal/{role}/classroom/<int:classroom_id>/results
/portal/{role}/classroom/<int:classroom_id>/people
```

`{role}` is `teacher` or `student`. Role-prefixed because permission logic, templates, and controller behavior diverge sharply between roles — sharing routes would force per-role branching inside every template.

### Controller layout

- `controllers/teacher_classroom.py` — new, owns all 6 tab handlers for teachers
- `controllers/student_classroom.py` — new, owns all 6 tab handlers for students
- `controllers/teacher.py` — shrinks to home (classroom grid) + profile only
- `controllers/student.py` — shrinks to home (classroom grid) + profile only

The current handlers in `teacher.py` for marks, attendance, and assessments are **moved into** `teacher_classroom.py` under the new URL scheme. Old flat routes (`/portal/teacher/marks`, `/portal/teacher/attendance/<id>`, `/portal/teacher/assessments`, `/portal/teacher/classroom/<id>`, etc.) are **removed**, no redirect shims (portal is internal-only, no external links).

### Shared guard helper

```python
def guard_classroom_access(classroom_id, role):
    """Return (classroom, actor) or redirect/404."""
```

- **Teacher** → loads classroom, verifies `classroom.teacher_id == request.env.user`
- **Student** → loads classroom, verifies the student has an `active` progression history with `section_id == classroom.section_id`
- Anything else → 404

Every tab handler calls this as its first line.

#### ⚠️ Pre-existing bug fix — `teacher_id` is `res.users`, not `hr.employee`

`edu.classroom.teacher_id`, `edu.exam.paper.teacher_id`, `edu.attendance.register.teacher_id`, `edu.attendance.sheet.teacher_id`, and `edu.continuous.assessment.record.teacher_id` are all `Many2one('res.users')`.

The current `edu_portal` code (pre-refactor) has a latent bug — `helpers.py::teacher_owns_classroom` compares `classroom.teacher_id == employee` where `employee` is an `hr.employee` record, so the equality is always False across model types. Similarly, existing `search_count([('teacher_id', '=', employee.id)])` calls in `teacher.py` pass an `hr.employee` id into a `res.users` field. These only happen to work when the user_id and employee_id match by coincidence.

**The refactor fixes this.** The new guard, badge methods, and search domains all use `request.env.user` (or `request.env.user.id`) for auth checks against `teacher_id`. The `hr.employee` record is still fetched via `get_teacher_employee()` but only for display data and for linking to HR records — **never for auth comparisons**.

Every rewritten site must use `user` for teacher equality and `employee` only for display. This includes the badge methods (§"Badge counts"), every tab handler, and the Stream model's teacher access rule (§"Stream — `edu.classroom.post`").

#### Student guard — relies on progression constraint

`edu.student.progression.history` has `@api.constrains('student_id', 'state')` enforcing at most one `active` row per student. The student guard therefore does `search([('student_id', '=', student.id), ('state', '=', 'active'), ('section_id', '=', classroom.section_id.id)], limit=1)` and treats a match as authorization. If the constraint is ever relaxed, this guard must be revisited.

### Tab behavior summary

| Tab | Teacher view | Student view |
|---|---|---|
| **Stream** | Composer + list of posts (pinned on top, then chronological) | Read-only list of posts |
| **Attendance** | Today's sheet in edit mode (HTMX row updates) | Student's own attendance log for this classroom |
| **Exams** | Exam papers list → click for marks entry | Student's marksheets for this classroom |
| **Assessments** | Continuous-assessment records, inline edit | Student's assessment records |
| **Results** | Published results table (all students) | Student's own result card |
| **People** | This classroom's teacher card + grid of student cards for the section | Same, read-only |

**People tab scope.** Because an `edu.classroom` is one *section × subject × term* tuple, it has exactly one `teacher_id`. The People tab shows **only this classroom's teacher** — not all teachers of the section. A student who wants to see another subject's teacher opens the corresponding classroom card. This is intentional and matches Google Classroom's per-class People page.

### Home page

`/portal/teacher/home` and `/portal/student/home` are pure card grids — no stats strip, no widgets. Each card is a colored header (subject-derived color) with classroom name, section/term, student count, and click-to-enter behavior. This replaces the current dashboard layout.

### Badge counts

Existing inline `search_count()` calls for sidebar badges become `badge_method` callables on registry records. Example: the `classrooms` sidebar item points its `badge_method` at `edu.classroom.portal_teacher_open_badge` — a new **model method** (not a Python `@classmethod`) returning the count for the current user. Each model owns the badge math for its own domain.

Badge resolution happens inside `build_portal_context()` at page-render time. Counts therefore refresh **only on full page loads** — not reactively via HTMX polling. This is an intentional simplification; per-badge live refresh is out of scope.

All teacher-side badge methods must filter by `self.env.user` (not employee id) — see the `teacher_id` field-type note in §"Shared guard helper".

## Stream — `edu.classroom.post`

The only genuinely new feature.

### Model

| Field | Type | Notes |
|---|---|---|
| `classroom_id` | M2O `edu.classroom` | required, `ondelete='cascade'` |
| `author_id` | M2O `res.users` | default = current user, set at create |
| `author_employee_id` | M2O `hr.employee` | `related='author_id.employee_id'`, `store=True` — for avatar/name in feed |
| `body` | Html | rich-text announcement body |
| `pinned` | Boolean | pinned posts sort to top |
| `posted_at` | Datetime | default now, not editable after create |
| `active` | Boolean | soft-delete (audit trail) |

Inherits `mail.thread` + `mail.activity.mixin` for free attachment storage via `message_main_attachment_id`.

`res.users.employee_id` is provided by the `hr` module (singular, company-scoped). `edu_portal` must list `hr` as a direct manifest dependency (it is currently only a transitive dependency).

### Access rules

- Teachers create/edit/archive posts on classrooms they own (ACL + record rule on `classroom_id.teacher_id == user`)
- Students read-only on posts whose classroom section matches their active progression history
- No student create/write permissions
- `group_education_admin` can do everything (moderation)

### Teacher UI

- Top of page: compact composer ("Announce something to your class") that expands on focus, with attachment picker and a "Pin" checkbox
- Submit via HTMX `POST` with `csrf=False` on the endpoint (matches the existing attendance/marks pattern — the portal is internal-only, `auth='user'`, and every POST endpoint re-validates teacher ownership via `guard_classroom_access`)
- Below composer: pinned posts section, then chronological feed
- Each post card: author avatar + name + timestamp + body + attachments + (for author) pin/unpin toggle + archive button with confirmation modal

### Student UI

Same layout, no composer, no controls. Pinned section + chronological feed, read-only.

### Empty state

Reuses existing `edu_portal.empty_state_component`:
- Students: "No announcements yet"
- Teachers: "Post your first announcement" with gentle CTA

### Out of scope

Comments, reactions, replies, @mentions, scheduled posts, push notifications, email digest, per-post visibility overrides.

## File Layout

```
edu_portal/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── edu_classroom_post.py           NEW — Stream announcement model
│   ├── edu_portal_sidebar_item.py      NEW — registry
│   ├── edu_portal_classroom_tab.py     NEW — registry
│   ├── edu_classroom.py                NEW — adds portal_teacher_open_badge classmethod
│   ├── edu_exam_paper.py               NEW — adds portal_marks_pending_badge classmethod
│   ├── edu_student.py                  (existing)
│   ├── edu_guardian.py                 (existing)
│   ├── hr_employee.py                  (existing)
│   ├── res_users.py                    (existing)
│   └── portal_mail.py                  (existing)
├── controllers/
│   ├── __init__.py
│   ├── main.py                         (existing — login/redirect only)
│   ├── helpers.py                      REWRITTEN — build_portal_context, guard_classroom_access, _resolve_portal_registry
│   ├── teacher.py                      SHRUNK — only home (grid) + profile
│   ├── teacher_classroom.py            NEW — all 6 tab handlers for teacher
│   ├── student.py                      SHRUNK — only home (grid) + profile
│   ├── student_classroom.py            NEW — all 6 tab handlers for student
│   └── parent.py                       (existing — unchanged)
├── data/
│   ├── portal_sidebar_data.xml         NEW — seed sidebar items
│   └── portal_classroom_tabs_data.xml  NEW — seed classroom tabs
├── security/
│   ├── security.xml                    (existing + groups for post write)
│   └── ir.model.access.csv             (existing + rows for new models)
├── views/
│   ├── portal_layout.xml               (existing)
│   ├── components.xml                  EXTENDED — classroom_tabs_component, post_card_component
│   ├── teacher_templates.xml           SHRUNK — home + profile only
│   ├── teacher_classroom_templates.xml NEW — 6 tab templates
│   ├── student_templates.xml           SHRUNK — home + profile only
│   ├── student_classroom_templates.xml NEW — 6 tab templates
│   ├── parent_templates.xml            (existing — unchanged)
│   ├── edu_classroom_post_views.xml    NEW — backend form/tree for admin moderation
│   └── <existing backend view files>   (unchanged)
└── static/src/
    ├── css/portal.css                  EXTENDED — classroom card grid, tab bar, post card, composer
    └── js/                             (existing + small HTMX helpers if needed)
```

## Migration & Compatibility

- Old flat routes are removed without redirect shims (portal is internal-only).
- The `_teacher_sidebar_items()` / `_student_sidebar_items()` methods are deleted.
- `base_context()` is replaced by `build_portal_context()`. All callers updated in the same change.
- Schema additions ship via module update (`-u edu_portal`); seed data loads on update.
- Existing teacher/student home/profile URLs are preserved — only their implementation changes (home becomes grid-only).
- The `hr` module is promoted from transitive to direct dependency in `__manifest__.py` to support the `author_employee_id` related field.

### Prerequisites (landed before the refactor starts)

- `fix(edu_exam): match exam papers by batch and curriculum, not classroom_id` — clean count/marks-entry behavior on `edu.classroom`.
- `fix(edu_portal): rename groups_id to group_ids for Odoo 19 compatibility` — portal access provisioning works at runtime.

Both are landed on `staging` before the portal refactor begins, so the refactor starts from a clean, functional baseline.

## Testing Approach

The repo has no automated tests (per `CLAUDE.md`); testing is manual via `TESTING_PLAN.md`. The new portal work gets a dedicated section covering:

1. **Registry rendering** — install `edu_portal`, verify built-in sidebar items and classroom tabs render per role. Toggle `active=False` on a record in the backend, reload, confirm it disappears.
2. **Orphaned-record safety** — manually insert a registry record with a `badge_method` pointing at a non-existent model, reload, confirm no crash, tab renders without a badge.
3. **Classroom grid home** — log in as teacher with multiple classrooms, confirm card grid, click card → land on Stream tab.
4. **Tab navigation** — walk all 6 tabs on both teacher and student. Confirm guard rejects foreign classrooms (404).
5. **Stream CRUD** — post, pin, unpin, archive, attach. Student-side read-only verification.
6. **Badge counts** — create an exam paper in `marks_entry` state, confirm marks-pending badge updates.
7. **Future-extension smoke test** — hand-craft a sidebar item and a classroom tab record via the backend UI, confirm it renders in the portal (proves a bridge module would work without actually building one).

## Deferred Work

- First real bridge module (e.g. `edu_assignment_portal`) — designed for, not built here.
- Push notifications / email digest for announcements.
- Mobile-specific responsive polish.
- Role-switcher / multi-role UX changes (current behavior preserved).
- Stream comments, reactions, scheduled posts.
