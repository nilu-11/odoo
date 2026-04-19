# Pre-Admission CRM Robustness Overhaul — Design Spec

**Date:** 2026-04-19
**Module:** edu_pre_admission_crm
**Status:** Approved

---

## Overview

Overhaul the edu_pre_admission_crm module across four dimensions: data quality, workflow completeness, reporting/visibility, and UX. The module is built on Odoo's CRM but customized for schools and colleges.

Three design pillars:
1. **Structured Interaction System** — hybrid Odoo activities + interaction log
2. **Data Quality Gates** — constraints, auto-assignment, profile completeness scoring
3. **Dashboards & Kanban Improvements** — redesigned cards, graph/pivot views

---

## 1. Interaction Log Model & Activity Integration

### 1.1 New Model: `edu.interaction.log`

| Field | Type | Notes |
|-------|------|-------|
| `lead_id` | Many2one → crm.lead | Required, ondelete=cascade, indexed |
| `applicant_profile_id` | Many2one (related from lead) | Stored, for reporting |
| `interaction_type` | Selection | call, campus_visit, counseling_session, parent_meeting, email, walk_in, video_call, other |
| `date` | Datetime | Default=now |
| `duration_minutes` | Integer | Optional |
| `counselor_id` | Many2one → res.users | Default=current user |
| `outcome` | Selection | positive, neutral, negative |
| `summary` | Char | One-line summary, shown on kanban/timeline |
| `note` | Text | Detailed notes |
| `activity_id` | Many2one → mail.activity | Back-link if created from activity completion |

Order: `lead_id, date desc`

### 1.2 Activity Integration

Override `activity_feedback` on `crm.lead`. When a completed activity's type matches a custom education activity type, auto-create an `edu.interaction.log` entry:
- `interaction_type` mapped from the activity type
- `summary` from the feedback text
- `counselor_id` from the user who completed it
- `activity_id` linked back

### 1.3 Custom Activity Types (seed data, noupdate=1)

| Name | Internal Type | Icon |
|------|--------------|------|
| Follow-up Call | call | fa-phone |
| Campus Visit | campus_visit | fa-university |
| Counseling Session | counseling_session | fa-comments |
| Parent Meeting | parent_meeting | fa-users |

These are `mail.activity.type` records with `category='default'` and `res_model='crm.lead'`.

### 1.4 Computed Fields on crm.lead

| Field | Type | Notes |
|-------|------|-------|
| `interaction_log_ids` | One2many → edu.interaction.log | Reverse relation |
| `interaction_count` | Integer, computed, stored | Count of interactions |
| `last_interaction_date` | Datetime, computed, stored | Most recent interaction date |
| `last_interaction_summary` | Char, computed | e.g. "Campus Visit - 2 days ago" |
| `days_since_last_interaction` | Integer, computed | For aging |

---

## 2. Form View Redesign

### 2.1 Interaction Timeline Section

Placed below main fields, above the notebook. Shows:
- Last 5 interactions as a compact list: type icon + summary + relative date + counselor
- "View All" link expanding to full history

### 2.2 Quick Schedule Row

Inline at the top of the interaction section:
- Activity type dropdown (pre-filtered to education types)
- Date picker (default tomorrow)
- "Schedule" button

One click to schedule a follow-up. Replaces the need for Odoo's multi-step activity popup for common actions.

### 2.3 "Next Step" Guidance Banner

A contextual `div` below the header that changes based on lead state and data completeness:

| Status | Condition | Message |
|--------|-----------|---------|
| Inquiry | No profile | "Create an applicant profile to proceed" |
| Inquiry | No program | "Select a program of interest" |
| Inquiry | No interactions | "Schedule a follow-up call or campus visit" |
| Inquiry | Profile + program set | "Ready to qualify — review and click Qualify" |
| Qualified | Not converted | "Review profile completeness, then Convert to Application" |
| Converted | — | Hidden |

Implemented as a computed `Html` field with conditional logic.

### 2.4 Applicant Profile Inline

Instead of a readonly tab:
- Guardian list (editable inline) in a collapsible group on the main form page
- Academic history inline similarly
- Profile completeness progress bar at the top of this section
- Only visible when `applicant_profile_id` is set

### 2.5 Simplified Tabs

1. **Notes** — counseling_note, qualification_note
2. **Source & Marketing** — medium_id, campaign_id, source_id, referred_by_id (moved from main form body)

---

## 3. Data Quality Gates

### 3.1 Hard Constraints

- **Phone or email required**: Python `@api.constrains` on `phone`, `email_from` — at least one must be set. Applied on create and write.

### 3.2 Auto-Assign Counselor

On `create()`: if `counselor_id` is empty, set from the CRM team's default `user_id` (the team leader). Uses existing Odoo CRM sales team logic.

### 3.3 Profile Completeness Score

Computed `Integer` field on `edu.applicant.profile`:

| Check | Weight |
|-------|--------|
| Has first + last name | 15% |
| Has DOB | 10% |
| Has gender | 10% |
| Has nationality | 10% |
| Has phone (from partner) | 15% |
| Has email (from partner) | 15% |
| Has at least 1 guardian | 15% |
| Has at least 1 academic history | 10% |

- Field: `profile_completeness` (Integer, 0-100)
- Shown as progress bar on lead form (related from applicant_profile_id)
- **Conversion gate**: `action_convert_to_admission_application()` blocks if completeness < 60%

### 3.4 Duplicate Detection Improvements

Extend current phone/email matching to also check:
- `applicant_profile_id.full_name` — case-insensitive match with stripped whitespace
- On create: if duplicates found, show non-blocking warning notification (not a hard blocker)

---

## 4. Kanban Card Redesign

### 4.1 Card Layout

```
+------------------------------+
| Applicant Name          ***  |  priority stars
| BCA Program                  |  interested_program_id
| phone number                 |
|                              |
| phone:3 visit:1 session:2   |  interaction count badges
|                              |
| Last: Campus Visit - 2d ago  |  last_interaction_summary
| Next: Call Follow-up - Tmrw  |  next activity with type
|                              |
| Tag1 Tag2        Counselor   |  tags + counselor
| [=========>    ] 70%         |  profile completeness bar
+------------------------------+
```

### 4.2 Computed Fields for Kanban

| Field | Notes |
|-------|-------|
| `call_count` | Count of interactions where type=call |
| `visit_count` | Count where type=campus_visit |
| `session_count` | Count where type=counseling_session |
| `last_interaction_summary` | Char, e.g. "Campus Visit - 2 days ago" |
| `profile_completeness` | Related from applicant_profile_id |
| `next_activity_summary` | Computed: type + name + relative date of next planned activity |

---

## 5. Dashboards & Reporting

### 5.1 Graph & Pivot Views on crm.lead

Add to the pre-admission pipeline action:
- **Graph view**: default bar chart, lead count by `lead_education_status`, group-by options for program, counselor, source, month
- **Pivot view**: rows=program or counselor, columns=status, measure=count

View mode updated to: `kanban,list,form,activity,graph,pivot`

### 5.2 Interaction Log Views

Standalone action "Interactions" under Pre-Admission menu:

- **List view**: all interactions across leads, columns: date, lead, type, summary, counselor, outcome
- **Search view**: filter by type, counselor, outcome, date range; group by type, counselor, month
- **Graph view**: interaction counts by type/counselor/month
- **Pivot view**: counselor (rows) x type (columns) = activity volume

### 5.3 Menu Additions

Under Pre-Admission root menu:
- "Interactions" menu item → interaction log action (after Guardians, seq 40)

---

## 6. Security

### edu.interaction.log Access

| Group | Read | Write | Create | Delete |
|-------|------|-------|--------|--------|
| education_admin | Y | Y | Y | Y |
| pre_admission_officer | Y | Y | Y | N |
| pre_admission_viewer | Y | N | N | N |

---

## 7. Models Not Changed

- `edu.guardian` — no changes
- `edu.applicant.guardian.rel` — no changes
- `edu.applicant.academic.history` — no changes
- `edu.relationship.type` — no changes
- `edu.qualification` — no changes
- `edu.team.member` — no changes
- `mail.message` — no changes
- `hr.employee` — no changes

---

## 8. Summary of Changes

| Component | Action |
|-----------|--------|
| `edu.interaction.log` | New model |
| `mail.activity.type` seed data | New data (4 activity types) |
| `crm.lead` model | Add interaction computed fields, override activity_feedback, auto-assign counselor, phone/email constraint |
| `edu.applicant.profile` model | Add profile_completeness computed field |
| CRM lead form view | Redesign: interaction timeline, quick schedule, next-step banner, inline profile, simplified tabs |
| CRM lead kanban view | Redesign: interaction badges, last interaction, next activity, completeness bar |
| CRM lead graph view | New |
| CRM lead pivot view | New |
| Interaction log views | New: list, search, graph, pivot |
| Menu | Add "Interactions" menu item |
| Security | Add access rules for edu.interaction.log |
| Conversion gate | Block if profile completeness < 60% |
