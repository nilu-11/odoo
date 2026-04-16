# EMIS UX Simplification — Design Spec

**Date:** 2026-04-16
**Branch:** feat/emis
**Status:** Approved

## Objective

Reduce friction across the entire EMIS by collapsing unnecessary stages, adding smart defaults, and improving form layouts. No new modules — all changes are within existing modules.

---

## 1. Admission Flow Redesign

### 1.1 State Machine Collapse

**Current:** `draft → submitted → under_review → scholarship_review → offered → offer_accepted → ready_for_enrollment → enrolled` (8 states)

**New:** `draft → under_review → approved → enrolled → rejected` (4 states + rejected from any)

| State | Purpose | Button |
|-------|---------|--------|
| `draft` | Applicant fills form | "Submit" |
| `under_review` | Academic review + optional scholarship review happen here. Auto-skipped if `require_academic_review=False` | "Approve" |
| `approved` | Optional offer letter + Odoo Sign + payment gate. If none required, "Enroll" is immediately available | "Generate Offer" / "Enroll" |
| `enrolled` | Enrollment record auto-created. Terminal state. | Done |
| `rejected` | Rejection from any state | — |

### 1.2 Register Configuration — Presets + Toggles

New fields on `edu.admission.register`:

| Field | Type | Default |
|-------|------|---------|
| `flow_preset` | Selection: fast_track / standard / full / custom | standard |
| `require_academic_review` | Boolean | True |
| `require_scholarship_review` | Boolean | False |
| `require_offer_letter` | Boolean | True |
| `require_odoo_sign` | Boolean | False |
| `require_payment_confirmation` | Boolean | True |
| `sign_template_id` | Many2one → sign.template | — |

**Preset onchange mapping:**

| Preset | Review | Scholarship | Offer | Sign | Payment |
|--------|--------|-------------|-------|------|---------|
| Fast Track | Off | Off | Off | Off | Off |
| Standard | On | Off | On | Off | On |
| Full | On | On | On | On | On |
| Custom | (user toggles) | | | | |

### 1.3 Odoo Sign Integration

- Register has `sign_template_id` (Many2one to `sign.template`) — the offer letter template
- On "Generate Offer" in `approved` state:
  - System creates a `sign.request` from the template
  - Applicant's partner receives the signing email
  - Application tracks `sign_request_id` (Many2one to `sign.request`)
  - `sign_status` computed field: pending / signed / refused
- When signature is completed (Sign module callback), application auto-advances to `enrolled` (if all other gates — payment — are also met; otherwise stays in `approved` with `sign_status=signed`)
- If applicant refuses to sign, `sign_status=refused` — application stays in `approved`, admin can re-send or reject
- If `require_odoo_sign=False` but `require_offer_letter=True`, offer letter is generated as PDF only — "Accept Offer" button is shown on the form for manual acceptance

### 1.4 Payment Gate

- `payment_received` (Boolean) on `edu.admission.application`
- Visible in `approved` state when `require_payment_confirmation=True` on register
- Manually toggled by admin
- "Enroll" button is blocked until `payment_received=True` (when required)
- No fee plan validation, no invoice sync, no accounting bridge

### 1.5 Enrollment Simplification

**Current:** `draft → confirmed → active` (3 states)
**New:** `draft → active` (2 states)

- Confirmation + activation merged into single "Activate" click
- Student record + portal user auto-created on activation
- Checklist remains optional — if checklist items exist on the register/program, they must be completed before activation is allowed

### 1.6 Data Migration

Existing application records mapped as follows:

| Old State | New State |
|-----------|-----------|
| `draft` | `draft` |
| `submitted` | `under_review` |
| `under_review` | `under_review` |
| `scholarship_review` | `under_review` |
| `offered` | `approved` |
| `offer_accepted` | `approved` |
| `ready_for_enrollment` | `approved` |
| `enrolled` | `enrolled` |
| `rejected` | `rejected` |

Existing enrollment records:

| Old State | New State |
|-----------|-----------|
| `draft` | `draft` |
| `confirmed` | `active` |
| `active` | `active` |

### 1.7 Application Form Redesign

**Header:** State bar (`draft` / `under_review` / `approved` / `enrolled`) + action buttons

**Smart buttons row:**
- **Scholarships** (icon: gift, badge: count) — visible when `require_scholarship_review=True`
- **Offer Letter** (icon: file-text, badge: sent/signed/pending) — visible when `require_offer_letter=True`
- **Enrollment** (icon: graduation-cap) — visible after enrollment created
- **Student** (icon: user) — visible after student created

**Notebook pages:**

| Tab | Contents |
|-----|----------|
| Personal Info | Applicant profile fields inline: name, DOB, gender, contact, address, photo |
| Academic | Program, batch, academic year, previous qualifications, academic history |
| Guardian | Guardian details (embedded one2many) |
| Financial | Payment received checkbox, fee structure (read-only from register), scholarship summary (read-only computed) |
| Documents | Uploaded documents / attachments |
| Notes | Internal notes, counseling notes, chatter |

---

## 2. Pre-Admission CRM Simplification

### 2.1 Stage Collapse

**Current:** `inquiry → prospect → qualified → ready_for_application → converted` (5 stages)

**New:** `inquiry → qualified → converted` (3 stages)

- `prospect` removed — no meaningful gate between inquiry and qualification
- `ready_for_application` removed — qualification already validates readiness

### 2.2 "Qualify" Button Enhancement

Single click `inquiry → qualified`:
- If `quick_applicant_name` is filled but no `applicant_profile_id` exists, auto-create profile (no separate "Create Profile" click needed)
- Validates: `applicant_profile_id` + `interested_program_id` are set
- Auto-creates profile from quick name if missing

### 2.3 "Convert to Application" Enhancement

- Shows confirmation dialog with: matched register name, program, batch
- If multiple registers match, shows dropdown to pick one
- Single click: `qualified → converted` + application created + opens application form

### 2.4 Inline Applicant Data

- Add an expandable section/tab on the CRM lead form showing key applicant profile fields (name, DOB, gender, contact, guardian info)
- Editable inline without navigating to separate applicant profile form

### 2.5 Duplicate Merge

- When duplicates are detected, show "Merge Lead" button
- Opens side-by-side comparison of duplicate leads
- User picks which field values to keep from each lead
- Merges into single lead, archives the other

---

## 3. Attendance Simplification

### 3.1 Auto-Start on First Edit

- Remove explicit "Start Session" button
- When teacher changes any student's attendance status, auto-transition `draft → in_progress` via `write` override
- Sheet creation flow unchanged (from register)

### 3.2 Bulk Status Buttons

- Add buttons above student lines on the attendance sheet form:
  - "All Present" | "All Absent" | "All Late"
- Sets all lines at once; teacher then adjusts exceptions
- Common flow: click "All Present", mark 2-3 students absent

---

## 4. Assessment Simplification

### 4.1 State Collapse

**Current:** `draft → confirmed → locked` (3 states)
**New:** `draft → confirmed` (2 states)

- "Confirm" now locks the record in one click
- Admin can "Reset to Draft" for corrections

### 4.2 Inline Marks Entry

- Add `marks_obtained` as an editable column in assessment record list/tree view
- Teacher opens list filtered by classroom + assessment, enters marks directly in grid
- "Confirm All" button on list view — bulk-confirms all draft records in current view

---

## 5. Academic Progression Simplification

### 5.1 Staged Close Before Promotion

**Current:** Promotion fails with hard error if any open attendance/exam/assessment records exist.

**New behavior:**
1. Promotion wizard shows summary of open records with counts:
   - "5 attendance sheets open, 3 exam papers in marks_entry"
2. "Auto-Close All Open Records" button — bulk-submits attendance sheets, bulk-closes exam papers
3. "Promote" button enabled after records are closed
4. Admin override checkbox: promote without closing (for edge cases)

### 5.2 Section Assignment — Single Step

**Current:** Config step → Generate Preview → Preview step → Confirm (2 wizard states)

**New:** Single form with config options on top and live preview grid below.
- Preview auto-refreshes on config changes (onchange)
- Single "Apply Assignment" button
- One step instead of two

### 5.3 Toggle Simplification

**Current:** Two confusing booleans: `unassigned_only` + `include_already_assigned`

**New:** Single selection field `assignment_scope`:
- "Unassigned Students Only" (default)
- "All Students (Reassign)"

---

## 6. Other Quick Fixes

### 6.1 Classroom Generation — Success Instead of Error

- When all classrooms already exist, show success notification ("All classrooms up to date") + open classroom list
- Replace `UserError` with notification

### 6.2 CRM Duplicate Merge

(Covered in Section 2.5)

---

## 7. Out of Scope

- Excel import for timetable, exams, fees, marks (future work)
- Fee plan / invoice / accounting integration changes
- Portal redesign
- New module creation
- Timetable UX changes

---

## 8. Affected Modules

| Module | Changes |
|--------|---------|
| `edu_admission` | State machine collapse, register presets/toggles, Odoo Sign integration, payment checkbox, form redesign with notebooks + smart buttons |
| `edu_enrollment` | State collapse (draft → active), merge confirm + activate |
| `edu_pre_admission_crm` | Stage collapse, qualify enhancement, convert enhancement, inline applicant data, duplicate merge |
| `edu_attendance` | Auto-start, bulk status buttons |
| `edu_assessment` | State collapse, inline marks, bulk confirm |
| `edu_academic_progression` | Staged close, single-step section assignment, toggle simplification |
| `edu_classroom` | Success notification instead of error |
| `edu_student` | Minor: student creation triggered from enrollment activation instead of confirmation |

---

## 9. Dependencies

- `sign` module must be installed for Odoo Sign offer letter flow
- `require_odoo_sign` toggle on register should be hidden if `sign` module is not installed (conditional `attrs`)
