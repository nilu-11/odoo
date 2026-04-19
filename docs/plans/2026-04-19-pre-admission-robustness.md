# Pre-Admission CRM Robustness Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul edu_pre_admission_crm with structured interaction logging, data quality gates, redesigned kanban cards, a next-step guidance banner, inline profile editing, and pipeline reporting views.

**Architecture:** New `edu.interaction.log` model captures structured interaction history. Activity completion auto-creates log entries via `_action_done` override on `mail.activity`. Profile completeness is a weighted computed field on `edu.applicant.profile`. Kanban and form views are redesigned with new computed fields. Graph/pivot views added for reporting.

**Tech Stack:** Odoo 19, Python, XML (QWeb views), mail.activity integration

**Spec:** `docs/specs/2026-04-19-pre-admission-robustness-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `models/edu_interaction_log.py` | Create | Interaction log model |
| `models/mail_activity.py` | Create | Override `_action_done` to auto-create interaction logs |
| `models/crm_lead.py` | Modify | Add interaction computed fields, auto-assign counselor, phone/email constraint, next-step banner, kanban counts |
| `models/edu_applicant_profile.py` | Modify | Add `profile_completeness` computed field |
| `models/__init__.py` | Modify | Register new models |
| `data/edu_activity_type_data.xml` | Create | Seed 4 custom activity types |
| `views/edu_interaction_log_views.xml` | Create | List, search, graph, pivot views |
| `views/crm_lead_views.xml` | Modify | Redesign kanban card, form (timeline, banner, inline profile), add graph/pivot |
| `views/menu_views.xml` | Modify | Add "Interactions" menu item |
| `security/ir.model.access.csv` | Modify | Add access rules for edu.interaction.log |
| `__manifest__.py` | Modify | Register new data/view files |

---

### Task 1: Interaction Log Model

**Files:**
- Create: `edu_pre_admission_crm/models/edu_interaction_log.py`
- Modify: `edu_pre_admission_crm/models/__init__.py`

- [ ] **Step 1: Create the interaction log model**

```python
# edu_pre_admission_crm/models/edu_interaction_log.py
from odoo import api, fields, models


class EduInteractionLog(models.Model):
    _name = 'edu.interaction.log'
    _description = 'Interaction Log'
    _order = 'date desc, id desc'
    _rec_name = 'summary'

    lead_id = fields.Many2one(
        comodel_name='crm.lead',
        string='Lead',
        required=True,
        ondelete='cascade',
        index=True,
    )
    applicant_profile_id = fields.Many2one(
        related='lead_id.applicant_profile_id',
        string='Applicant',
        store=True,
        index=True,
    )
    interaction_type = fields.Selection(
        selection=[
            ('call', 'Call'),
            ('campus_visit', 'Campus Visit'),
            ('counseling_session', 'Counseling Session'),
            ('parent_meeting', 'Parent Meeting'),
            ('email', 'Email'),
            ('walk_in', 'Walk-in'),
            ('video_call', 'Video Call'),
            ('other', 'Other'),
        ],
        string='Type',
        required=True,
        default='call',
        index=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    duration_minutes = fields.Integer(string='Duration (min)')
    counselor_id = fields.Many2one(
        comodel_name='res.users',
        string='Counselor',
        default=lambda self: self.env.user,
        index=True,
    )
    outcome = fields.Selection(
        selection=[
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
        ],
        string='Outcome',
    )
    summary = fields.Char(string='Summary')
    note = fields.Text(string='Notes')
    activity_id = fields.Many2one(
        comodel_name='mail.activity',
        string='Source Activity',
        ondelete='set null',
        index=True,
    )
    company_id = fields.Many2one(
        related='lead_id.company_id',
        store=True,
        index=True,
    )
```

- [ ] **Step 2: Register in `__init__.py`**

Add after `from . import crm_lead`:

```python
from . import edu_interaction_log
from . import mail_activity
```

- [ ] **Step 3: Commit**

```bash
git add edu_pre_admission_crm/models/edu_interaction_log.py edu_pre_admission_crm/models/__init__.py
git commit -m "feat(pre_admission): add edu.interaction.log model"
```

---

### Task 2: Activity Type Seed Data

**Files:**
- Create: `edu_pre_admission_crm/data/edu_activity_type_data.xml`
- Modify: `edu_pre_admission_crm/__manifest__.py`

- [ ] **Step 1: Create activity type seed data**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="mail_activity_type_followup_call" model="mail.activity.type">
        <field name="name">Follow-up Call</field>
        <field name="res_model">crm.lead</field>
        <field name="category">default</field>
        <field name="icon">fa-phone</field>
        <field name="delay_count">1</field>
        <field name="delay_unit">days</field>
        <field name="sequence">100</field>
    </record>
    <record id="mail_activity_type_campus_visit" model="mail.activity.type">
        <field name="name">Campus Visit</field>
        <field name="res_model">crm.lead</field>
        <field name="category">default</field>
        <field name="icon">fa-university</field>
        <field name="delay_count">3</field>
        <field name="delay_unit">days</field>
        <field name="sequence">101</field>
    </record>
    <record id="mail_activity_type_counseling_session" model="mail.activity.type">
        <field name="name">Counseling Session</field>
        <field name="res_model">crm.lead</field>
        <field name="category">default</field>
        <field name="icon">fa-comments</field>
        <field name="delay_count">2</field>
        <field name="delay_unit">days</field>
        <field name="sequence">102</field>
    </record>
    <record id="mail_activity_type_parent_meeting" model="mail.activity.type">
        <field name="name">Parent Meeting</field>
        <field name="res_model">crm.lead</field>
        <field name="category">default</field>
        <field name="icon">fa-users</field>
        <field name="delay_count">3</field>
        <field name="delay_unit">days</field>
        <field name="sequence">103</field>
    </record>
</odoo>
```

- [ ] **Step 2: Add to `__manifest__.py` data list**

Add after `'data/edu_relationship_type_data.xml'`:

```python
'data/edu_activity_type_data.xml',
```

- [ ] **Step 3: Commit**

```bash
git add edu_pre_admission_crm/data/edu_activity_type_data.xml edu_pre_admission_crm/__manifest__.py
git commit -m "feat(pre_admission): seed 4 custom education activity types"
```

---

### Task 3: Mail Activity Override — Auto-Create Interaction Log

**Files:**
- Create: `edu_pre_admission_crm/models/mail_activity.py`

The `_action_done` method on `mail.activity` is the hook point. When an activity is completed on a `crm.lead`, if its type matches one of our education activity types, auto-create an `edu.interaction.log` entry.

- [ ] **Step 1: Create mail_activity.py**

```python
# edu_pre_admission_crm/models/mail_activity.py
from odoo import models


# Mapping from mail.activity.type XML ID suffix to interaction_type selection key
_ACTIVITY_TYPE_MAP = {
    'mail_activity_type_followup_call': 'call',
    'mail_activity_type_campus_visit': 'campus_visit',
    'mail_activity_type_counseling_session': 'counseling_session',
    'mail_activity_type_parent_meeting': 'parent_meeting',
}


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _action_done(self, feedback=False, attachment_ids=None):
        """Override to auto-create interaction log when education activities are completed."""
        # Collect education activities before they get archived by super()
        log_vals_list = []
        edu_type_ids = {}
        for xml_id_suffix, interaction_type in _ACTIVITY_TYPE_MAP.items():
            ref = self.env.ref(
                f'edu_pre_admission_crm.{xml_id_suffix}',
                raise_if_not_found=False,
            )
            if ref:
                edu_type_ids[ref.id] = interaction_type

        if edu_type_ids:
            for activity in self:
                if (
                    activity.res_model == 'crm.lead'
                    and activity.activity_type_id.id in edu_type_ids
                ):
                    log_vals_list.append({
                        'lead_id': activity.res_id,
                        'interaction_type': edu_type_ids[activity.activity_type_id.id],
                        'date': activity.date_deadline,
                        'counselor_id': self.env.uid,
                        'summary': feedback or activity.summary or activity.activity_type_id.name,
                        'activity_id': activity.id,
                    })

        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)

        if log_vals_list:
            self.env['edu.interaction.log'].sudo().create(log_vals_list)

        return result
```

- [ ] **Step 2: Commit**

```bash
git add edu_pre_admission_crm/models/mail_activity.py
git commit -m "feat(pre_admission): auto-create interaction log on activity completion"
```

---

### Task 4: CRM Lead — Interaction Computed Fields & Data Quality

**Files:**
- Modify: `edu_pre_admission_crm/models/crm_lead.py`

Add interaction computed fields, kanban count fields, next-step banner, auto-assign counselor, and phone/email constraint.

- [ ] **Step 1: Add interaction fields and computed methods**

Add these fields after the `conversion_date` field (after line 221):

```python
    # ── Interaction Log ──────────────────────────────────────────────────────
    interaction_log_ids = fields.One2many(
        comodel_name='edu.interaction.log',
        inverse_name='lead_id',
        string='Interactions',
    )
    interaction_count = fields.Integer(
        string='Interactions',
        compute='_compute_interaction_stats',
        store=True,
    )
    last_interaction_date = fields.Datetime(
        string='Last Interaction',
        compute='_compute_interaction_stats',
        store=True,
    )
    last_interaction_summary = fields.Char(
        string='Last Interaction Summary',
        compute='_compute_interaction_stats',
    )
    days_since_last_interaction = fields.Integer(
        string='Days Since Last Interaction',
        compute='_compute_interaction_stats',
    )
    call_count = fields.Integer(
        compute='_compute_interaction_stats',
        store=True,
    )
    visit_count = fields.Integer(
        compute='_compute_interaction_stats',
        store=True,
    )
    session_count = fields.Integer(
        compute='_compute_interaction_stats',
        store=True,
    )
    next_activity_summary = fields.Char(
        string='Next Activity',
        compute='_compute_next_activity_summary',
    )
    profile_completeness = fields.Integer(
        related='applicant_profile_id.profile_completeness',
        string='Profile Completeness',
    )
    next_step_banner = fields.Html(
        string='Next Step',
        compute='_compute_next_step_banner',
        sanitize=False,
    )
```

- [ ] **Step 2: Add the compute methods**

Add after `_compute_is_referral_source` (after line 192):

```python
    @api.depends('interaction_log_ids', 'interaction_log_ids.interaction_type',
                 'interaction_log_ids.date', 'interaction_log_ids.summary')
    def _compute_interaction_stats(self):
        for rec in self:
            logs = rec.interaction_log_ids
            rec.interaction_count = len(logs)
            rec.call_count = len(logs.filtered(lambda l: l.interaction_type == 'call'))
            rec.visit_count = len(logs.filtered(lambda l: l.interaction_type == 'campus_visit'))
            rec.session_count = len(logs.filtered(lambda l: l.interaction_type == 'counseling_session'))
            if logs:
                latest = logs.sorted('date', reverse=True)[0]
                rec.last_interaction_date = latest.date
                type_labels = dict(self.env['edu.interaction.log']._fields['interaction_type'].selection)
                type_label = type_labels.get(latest.interaction_type, latest.interaction_type)
                if latest.date:
                    delta = fields.Datetime.now() - latest.date
                    days = delta.days
                    if days == 0:
                        ago = 'today'
                    elif days == 1:
                        ago = 'yesterday'
                    else:
                        ago = f'{days}d ago'
                    rec.last_interaction_summary = f'{type_label} - {ago}'
                else:
                    rec.last_interaction_summary = type_label
                rec.days_since_last_interaction = (fields.Datetime.now() - latest.date).days if latest.date else 0
            else:
                rec.last_interaction_date = False
                rec.last_interaction_summary = False
                rec.days_since_last_interaction = 0

    @api.depends('activity_ids', 'activity_ids.date_deadline',
                 'activity_ids.activity_type_id', 'activity_ids.summary')
    def _compute_next_activity_summary(self):
        for rec in self:
            upcoming = rec.activity_ids.sorted('date_deadline')
            if upcoming:
                act = upcoming[0]
                name = act.summary or act.activity_type_id.name or 'Activity'
                delta = (act.date_deadline - fields.Date.today()).days
                if delta == 0:
                    when = 'Today'
                elif delta == 1:
                    when = 'Tomorrow'
                elif delta < 0:
                    when = f'{abs(delta)}d overdue'
                else:
                    when = f'in {delta}d'
                rec.next_activity_summary = f'{name} - {when}'
            else:
                rec.next_activity_summary = False

    @api.depends('lead_education_status', 'applicant_profile_id',
                 'interested_program_id', 'interaction_count',
                 'is_converted_to_application', 'profile_completeness')
    def _compute_next_step_banner(self):
        for rec in self:
            if rec.lead_education_status == 'converted' or rec.is_converted_to_application:
                rec.next_step_banner = False
                continue
            if rec.lead_education_status == 'inquiry':
                if not rec.applicant_profile_id:
                    msg = 'Create an applicant profile to proceed'
                    icon = 'fa-user-plus'
                elif not rec.interested_program_id:
                    msg = 'Select a program of interest'
                    icon = 'fa-graduation-cap'
                elif rec.interaction_count == 0:
                    msg = 'Schedule a follow-up call or campus visit'
                    icon = 'fa-phone'
                else:
                    msg = 'Ready to qualify — review and click Qualify'
                    icon = 'fa-check-circle'
            elif rec.lead_education_status == 'qualified':
                pct = rec.profile_completeness or 0
                msg = f'Review profile completeness ({pct}%), then Convert to Application'
                icon = 'fa-arrow-right'
            else:
                rec.next_step_banner = False
                continue
            rec.next_step_banner = (
                f'<div class="alert alert-info py-2 px-3 mb-0 d-flex align-items-center">'
                f'<i class="fa {icon} me-2"/><span>{msg}</span></div>'
            )
```

- [ ] **Step 3: Add phone/email constraint**

Add after the `_check_conversion_readiness` method:

```python
    @api.constrains('phone', 'email_from')
    def _check_phone_or_email(self):
        for rec in self:
            if not rec.phone and not rec.email_from:
                raise UserError(
                    _("At least a phone number or email address is required.")
                )
```

- [ ] **Step 4: Add auto-assign counselor in create()**

Modify the existing `create` method to add counselor auto-assignment. Replace the existing `create` method (lines 345-353):

```python
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            applicant_id = vals.get('applicant_profile_id')
            if applicant_id:
                applicant = self.env['edu.applicant.profile'].browse(applicant_id)
                if applicant.exists() and applicant.partner_id:
                    vals['partner_id'] = applicant.partner_id.id
            # Auto-assign counselor from sales team
            if not vals.get('counselor_id'):
                team_id = vals.get('team_id')
                if team_id:
                    team = self.env['crm.team'].browse(team_id)
                    if team.user_id:
                        vals['counselor_id'] = team.user_id.id
        return super().create(vals_list)
```

- [ ] **Step 5: Add conversion gate for profile completeness**

In `_check_conversion_readiness` method, add after the `is_converted_to_application` check (after line 401):

```python
        completeness = self.applicant_profile_id.profile_completeness or 0
        if completeness < 60:
            raise UserError(
                _(
                    "Applicant profile is only %(pct)s%% complete. "
                    "At least 60%% is required before conversion.",
                    pct=completeness,
                )
            )
```

- [ ] **Step 6: Enhance duplicate detection with name matching**

In `_compute_duplicate_leads`, add name-based matching after the email check block (after line 326). Add before the `rec.is_duplicate` line:

```python
            # Name-based duplicate detection
            name_dupes = self.env['crm.lead']
            if rec.applicant_profile_id and rec.applicant_profile_id.full_name:
                clean_name = rec.applicant_profile_id.full_name.strip().lower()
                if clean_name:
                    all_leads = self.search([
                        ('id', '!=', rec._origin.id or rec.id),
                        ('applicant_profile_id', '!=', False),
                    ])
                    name_dupes = all_leads.filtered(
                        lambda l: l.applicant_profile_id.full_name
                        and l.applicant_profile_id.full_name.strip().lower() == clean_name
                    )
```

Then update the existing lines:

```python
            rec.is_duplicate = rec.has_duplicate_phone or rec.has_duplicate_email or bool(name_dupes)
            rec.duplicate_lead_count = len(phone_dupes | email_dupes | name_dupes)
```

- [ ] **Step 7: Commit**

```bash
git add edu_pre_admission_crm/models/crm_lead.py
git commit -m "feat(pre_admission): interaction stats, data quality gates, next-step banner"
```

---

### Task 5: Profile Completeness on Applicant Profile

**Files:**
- Modify: `edu_pre_admission_crm/models/edu_applicant_profile.py`

- [ ] **Step 1: Add `profile_completeness` computed field**

Add the field after `lead_count` (after line 85):

```python
    profile_completeness = fields.Integer(
        string='Profile Completeness',
        compute='_compute_profile_completeness',
        store=True,
    )
```

- [ ] **Step 2: Add the compute method**

Add after `_compute_lead_count` (after line 136):

```python
    @api.depends('first_name', 'last_name', 'date_of_birth', 'gender',
                 'nationality_id', 'partner_id.phone', 'partner_id.email',
                 'guardian_rel_ids', 'academic_history_ids')
    def _compute_profile_completeness(self):
        for rec in self:
            score = 0
            if rec.first_name and rec.last_name:
                score += 15
            if rec.date_of_birth:
                score += 10
            if rec.gender:
                score += 10
            if rec.nationality_id:
                score += 10
            if rec.partner_id and rec.partner_id.phone:
                score += 15
            if rec.partner_id and rec.partner_id.email:
                score += 15
            if rec.guardian_rel_ids:
                score += 15
            if rec.academic_history_ids:
                score += 10
            rec.profile_completeness = score
```

- [ ] **Step 3: Commit**

```bash
git add edu_pre_admission_crm/models/edu_applicant_profile.py
git commit -m "feat(pre_admission): profile completeness scoring (weighted 0-100)"
```

---

### Task 6: Interaction Log Views

**Files:**
- Create: `edu_pre_admission_crm/views/edu_interaction_log_views.xml`
- Modify: `edu_pre_admission_crm/__manifest__.py`

- [ ] **Step 1: Create interaction log views**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ══════════════════════════════════════════════════════
         Interaction Log — Search
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_interaction_log_search" model="ir.ui.view">
        <field name="name">edu.interaction.log.search</field>
        <field name="model">edu.interaction.log</field>
        <field name="arch" type="xml">
            <search string="Interactions">
                <field name="lead_id"/>
                <field name="applicant_profile_id"/>
                <field name="summary"/>
                <field name="counselor_id"/>
                <separator/>
                <filter string="Calls" name="calls"
                        domain="[('interaction_type', '=', 'call')]"/>
                <filter string="Campus Visits" name="visits"
                        domain="[('interaction_type', '=', 'campus_visit')]"/>
                <filter string="Counseling" name="sessions"
                        domain="[('interaction_type', '=', 'counseling_session')]"/>
                <filter string="Parent Meetings" name="parent_meetings"
                        domain="[('interaction_type', '=', 'parent_meeting')]"/>
                <separator/>
                <filter string="Positive" name="positive"
                        domain="[('outcome', '=', 'positive')]"/>
                <filter string="Negative" name="negative"
                        domain="[('outcome', '=', 'negative')]"/>
                <separator/>
                <filter string="Today" name="today"
                        domain="[('date', '>=', datetime.datetime.combine(context_today(), datetime.time(0,0,0))),
                                 ('date', '&lt;', datetime.datetime.combine(context_today() + relativedelta(days=1), datetime.time(0,0,0)))]"/>
                <filter string="This Week" name="this_week"
                        domain="[('date', '>=', (context_today() - relativedelta(weekday=0, weeks=1)).strftime('%Y-%m-%d'))]"/>
                <filter string="This Month" name="this_month"
                        domain="[('date', '>=', context_today().strftime('%Y-%m-01'))]"/>
                <group name="group_by">
                    <filter string="Type" name="group_type"
                            context="{'group_by': 'interaction_type'}"/>
                    <filter string="Counselor" name="group_counselor"
                            context="{'group_by': 'counselor_id'}"/>
                    <filter string="Outcome" name="group_outcome"
                            context="{'group_by': 'outcome'}"/>
                    <filter string="Month" name="group_month"
                            context="{'group_by': 'date:month'}"/>
                    <filter string="Lead" name="group_lead"
                            context="{'group_by': 'lead_id'}"/>
                </group>
            </search>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Interaction Log — List
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_interaction_log_list" model="ir.ui.view">
        <field name="name">edu.interaction.log.list</field>
        <field name="model">edu.interaction.log</field>
        <field name="arch" type="xml">
            <list string="Interactions"
                  decoration-success="outcome == 'positive'"
                  decoration-danger="outcome == 'negative'">
                <field name="date" widget="datetime"/>
                <field name="lead_id"/>
                <field name="applicant_profile_id" optional="show"/>
                <field name="interaction_type" widget="badge"/>
                <field name="summary"/>
                <field name="counselor_id" widget="many2one_avatar_user"/>
                <field name="outcome" widget="badge"
                       decoration-success="outcome == 'positive'"
                       decoration-warning="outcome == 'neutral'"
                       decoration-danger="outcome == 'negative'"
                       optional="show"/>
                <field name="duration_minutes" string="Min" optional="show"/>
            </list>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Interaction Log — Form
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_interaction_log_form" model="ir.ui.view">
        <field name="name">edu.interaction.log.form</field>
        <field name="model">edu.interaction.log</field>
        <field name="arch" type="xml">
            <form string="Interaction">
                <sheet>
                    <group>
                        <group string="Interaction">
                            <field name="lead_id"/>
                            <field name="interaction_type"/>
                            <field name="date"/>
                            <field name="duration_minutes"/>
                            <field name="counselor_id"/>
                            <field name="outcome"/>
                        </group>
                        <group string="Details">
                            <field name="summary"/>
                            <field name="applicant_profile_id" readonly="1"/>
                            <field name="activity_id" readonly="1"/>
                        </group>
                    </group>
                    <group string="Notes">
                        <field name="note" nolabel="1"
                               placeholder="Detailed notes from the interaction..."/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Interaction Log — Graph
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_interaction_log_graph" model="ir.ui.view">
        <field name="name">edu.interaction.log.graph</field>
        <field name="model">edu.interaction.log</field>
        <field name="arch" type="xml">
            <graph string="Interactions" type="bar">
                <field name="interaction_type"/>
                <field name="counselor_id"/>
            </graph>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Interaction Log — Pivot
    ══════════════════════════════════════════════════════ -->
    <record id="view_edu_interaction_log_pivot" model="ir.ui.view">
        <field name="name">edu.interaction.log.pivot</field>
        <field name="model">edu.interaction.log</field>
        <field name="arch" type="xml">
            <pivot string="Interactions">
                <field name="counselor_id" type="row"/>
                <field name="interaction_type" type="col"/>
            </pivot>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Interaction Log — Action
    ══════════════════════════════════════════════════════ -->
    <record id="action_edu_interaction_log" model="ir.actions.act_window">
        <field name="name">Interactions</field>
        <field name="res_model">edu.interaction.log</field>
        <field name="view_mode">list,graph,pivot,form</field>
        <field name="search_view_id" ref="view_edu_interaction_log_search"/>
        <field name="context">{'search_default_group_type': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">No interactions recorded yet</p>
            <p>Interactions are automatically logged when education activities (calls, visits, counseling sessions) are completed.</p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Add to manifest**

In `__manifest__.py` data list, add after `'views/crm_lead_views.xml'`:

```python
'views/edu_interaction_log_views.xml',
```

- [ ] **Step 3: Commit**

```bash
git add edu_pre_admission_crm/views/edu_interaction_log_views.xml edu_pre_admission_crm/__manifest__.py
git commit -m "feat(pre_admission): interaction log views (list, search, graph, pivot)"
```

---

### Task 7: Security — Interaction Log Access Rules

**Files:**
- Modify: `edu_pre_admission_crm/security/ir.model.access.csv`

- [ ] **Step 1: Add access rules**

Append these lines to `ir.model.access.csv`:

```csv
access_interaction_log_admin,edu.interaction.log admin,model_edu_interaction_log,edu_academic_structure.group_education_admin,1,1,1,1
access_interaction_log_officer,edu.interaction.log officer,model_edu_interaction_log,group_pre_admission_officer,1,1,1,0
access_interaction_log_viewer,edu.interaction.log viewer,model_edu_interaction_log,group_pre_admission_viewer,1,0,0,0
```

- [ ] **Step 2: Commit**

```bash
git add edu_pre_admission_crm/security/ir.model.access.csv
git commit -m "feat(pre_admission): access rules for edu.interaction.log"
```

---

### Task 8: Kanban Card Redesign

**Files:**
- Modify: `edu_pre_admission_crm/views/crm_lead_views.xml`

- [ ] **Step 1: Replace the kanban view**

Replace the entire `view_pre_admission_lead_kanban` record (lines 8-63) with:

```xml
    <record id="view_pre_admission_lead_kanban" model="ir.ui.view">
        <field name="name">crm.lead.kanban.pre_admission</field>
        <field name="model">crm.lead</field>
        <field name="arch" type="xml">
            <kanban default_group_by="lead_education_status"
                    group_create="false"
                    group_delete="false"
                    group_edit="false"
                    archivable="false"
                    sample="1">
                <field name="lead_education_status"/>
                <field name="priority"/>
                <field name="color"/>
                <field name="activity_state"/>
                <field name="activity_ids"/>
                <field name="partner_id"/>
                <field name="phone"/>
                <field name="interested_program_id"/>
                <field name="tag_ids"/>
                <field name="counselor_name"/>
                <field name="is_duplicate"/>
                <field name="call_count"/>
                <field name="visit_count"/>
                <field name="session_count"/>
                <field name="last_interaction_summary"/>
                <field name="next_activity_summary"/>
                <field name="profile_completeness"/>
                <progressbar field="activity_state"
                             colors='{"planned": "success", "today": "warning", "overdue": "danger"}'/>
                <templates>
                    <t t-name="card">
                        <!-- Name + priority -->
                        <div class="d-flex justify-content-between align-items-start mb-1">
                            <field name="name" class="fw-bold text-truncate"/>
                            <field name="priority" widget="priority" class="ms-1 flex-shrink-0"/>
                        </div>

                        <!-- Program -->
                        <div t-if="record.interested_program_id.value" class="text-muted small text-truncate">
                            <i class="fa fa-graduation-cap me-1"/><field name="interested_program_id"/>
                        </div>

                        <!-- Phone -->
                        <div t-if="record.phone.value" class="small mt-1">
                            <field name="phone" widget="phone"/>
                        </div>

                        <!-- Interaction badges -->
                        <div class="d-flex gap-2 mt-2 small">
                            <span t-if="record.call_count.raw_value" class="badge bg-primary-subtle text-primary-emphasis"
                                  title="Calls">
                                <i class="fa fa-phone me-1"/><field name="call_count"/>
                            </span>
                            <span t-if="record.visit_count.raw_value" class="badge bg-success-subtle text-success-emphasis"
                                  title="Campus Visits">
                                <i class="fa fa-university me-1"/><field name="visit_count"/>
                            </span>
                            <span t-if="record.session_count.raw_value" class="badge bg-info-subtle text-info-emphasis"
                                  title="Counseling Sessions">
                                <i class="fa fa-comments me-1"/><field name="session_count"/>
                            </span>
                            <span class="badge bg-warning ms-auto" t-if="record.is_duplicate.raw_value">Dup</span>
                        </div>

                        <!-- Last interaction -->
                        <div t-if="record.last_interaction_summary.value"
                             class="small text-muted mt-1 text-truncate">
                            <i class="fa fa-history me-1"/><field name="last_interaction_summary"/>
                        </div>

                        <!-- Next activity -->
                        <div t-if="record.next_activity_summary.value"
                             class="small mt-1 text-truncate">
                            <i class="fa fa-clock-o me-1 text-primary"/><field name="next_activity_summary"/>
                        </div>

                        <!-- Tags + counselor -->
                        <div class="d-flex justify-content-between align-items-center mt-2">
                            <field name="tag_ids" widget="many2many_tags"
                                   options="{'color_field': 'color'}"/>
                            <field name="counselor_name" widget="many2one_avatar" class="ms-auto"/>
                        </div>

                        <!-- Profile completeness bar -->
                        <div t-if="record.profile_completeness.raw_value" class="mt-2">
                            <div class="progress" style="height: 4px;" t-att-title="record.profile_completeness.value + '%'">
                                <div class="progress-bar"
                                     role="progressbar"
                                     t-att-style="'width: ' + record.profile_completeness.value + '%'"
                                     t-att-class="record.profile_completeness.raw_value &gt;= 60 ? 'bg-success' : 'bg-warning'"/>
                            </div>
                        </div>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>
```

- [ ] **Step 2: Commit**

```bash
git add edu_pre_admission_crm/views/crm_lead_views.xml
git commit -m "feat(pre_admission): redesign kanban card with interaction badges and completeness bar"
```

---

### Task 9: Form View Redesign — Banner, Timeline, Inline Profile

**Files:**
- Modify: `edu_pre_admission_crm/views/crm_lead_views.xml`

- [ ] **Step 1: Add next-step banner**

In the form view inheritance (`view_crm_lead_form_pre_admission`), add after the `lead_education_status` statusbar field (after line 139, inside the `<xpath expr="//header" position="inside">` block):

After the closing `</xpath>` for the header block (line 140), add a new xpath:

```xml
            <!-- Next step guidance banner -->
            <xpath expr="//sheet" position="after">
                <field name="next_step_banner" readonly="1" nolabel="1"
                       invisible="lead_education_status in ('converted', 'lost')"
                       class="w-100"/>
            </xpath>
```

Note: In Odoo, placing it after `//sheet` but before chatter puts it between them. Alternatively, place inside sheet at the top. Let's put it inside sheet, before the button box:

```xml
            <!-- Next step guidance banner -->
            <xpath expr="//div[@name='button_box']" position="before">
                <field name="next_step_banner" readonly="1" nolabel="1"
                       invisible="lead_education_status in ('converted', 'lost')"
                       class="w-100" widget="html"/>
            </xpath>
```

- [ ] **Step 2: Replace the "Status & Activities" section with interaction timeline**

Replace the existing "Status & Activities" group and the "Pending Call Activities" / "Done Call Activities" sections (lines 328-351) with:

```xml
                <!-- ── Interaction Timeline ── -->
                <div class="o_horizontal_separator mt-4 mb-3">Interactions</div>

                <div class="mb-3">
                    <button name="action_quick_schedule"
                            type="object"
                            string="Schedule Activity"
                            class="btn-secondary btn-sm"
                            icon="fa-plus"
                            invisible="lead_education_status in ('converted', 'lost')"/>
                    <button name="action_log_interaction"
                            type="object"
                            string="Log Interaction"
                            class="btn-secondary btn-sm ms-1"
                            icon="fa-pencil"
                            invisible="lead_education_status in ('converted', 'lost')"/>
                </div>

                <field name="interaction_log_ids" nolabel="1" mode="list" readonly="1">
                    <list string="Interactions" create="0" edit="0" delete="0"
                          decoration-success="outcome == 'positive'"
                          decoration-danger="outcome == 'negative'"
                          limit="5">
                        <field name="date" widget="datetime"/>
                        <field name="interaction_type" widget="badge"/>
                        <field name="summary"/>
                        <field name="counselor_id" widget="many2one_avatar_user"/>
                        <field name="outcome" widget="badge"
                               decoration-success="outcome == 'positive'"
                               decoration-warning="outcome == 'neutral'"
                               decoration-danger="outcome == 'negative'"/>
                    </list>
                </field>
```

- [ ] **Step 3: Replace the Applicant Profile tab with inline sections**

Replace the existing "Applicant Profile" notebook page (lines 383-407) with guardians and academic history displayed inline:

```xml
            <xpath expr="//sheet/notebook" position="inside">
                <page string="Guardians &amp; Academic History"
                      invisible="not applicant_profile_id">
                    <group string="Guardians">
                        <field name="applicant_profile_id" invisible="1"/>
                        <field name="profile_completeness" widget="progressbar"
                               options="{'editable': false}" colspan="2"/>
                    </group>
                    <!-- Guardian list is readonly here; edit via Applicant Profile form -->
                    <label for="applicant_profile_id" string="Guardians" class="fw-bold"/>
                    <field name="applicant_profile_id" invisible="1"/>
                    <!-- We cannot directly embed One2many of a related record in Odoo views.
                         Instead, show a link to open the profile for editing. -->
                    <div class="mb-2">
                        <button name="action_open_applicant_profile"
                                type="object"
                                string="Open Applicant Profile"
                                class="btn-link btn-sm ps-0"
                                icon="fa-external-link"/>
                    </div>
                </page>
                <page string="Source &amp; Marketing">
                    <group>
                        <group string="Marketing">
                            <field name="medium_id"/>
                            <field name="campaign_id"/>
                            <field name="source_id"/>
                            <field name="referred_by_id" invisible="not is_referral_source"/>
                        </group>
                        <group string="Conversion">
                            <field name="is_converted_to_application" readonly="1"/>
                            <field name="conversion_date" readonly="1"
                                   invisible="not is_converted_to_application"/>
                        </group>
                    </group>
                </page>
            </xpath>
```

- [ ] **Step 4: Add helper action methods on crm.lead**

In `crm_lead.py`, add these methods:

```python
    def action_quick_schedule(self):
        """Open a simplified activity scheduling dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Activity'),
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'crm.lead',
                'default_res_id': self.id,
                'default_user_id': self.counselor_id.id or self.env.uid,
            },
        }

    def action_log_interaction(self):
        """Open a form to manually log an interaction."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Interaction'),
            'res_model': 'edu.interaction.log',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_counselor_id': self.env.uid,
            },
        }

    def action_open_applicant_profile(self):
        """Open the linked applicant profile form."""
        self.ensure_one()
        if not self.applicant_profile_id:
            raise UserError(_("No applicant profile linked to this lead."))
        return {
            'type': 'ir.actions.act_window',
            'name': self.applicant_profile_id.full_name,
            'res_model': 'edu.applicant.profile',
            'res_id': self.applicant_profile_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
```

- [ ] **Step 5: Commit**

```bash
git add edu_pre_admission_crm/views/crm_lead_views.xml edu_pre_admission_crm/models/crm_lead.py
git commit -m "feat(pre_admission): form redesign — banner, interaction timeline, inline profile"
```

---

### Task 10: Graph & Pivot Views for Pipeline

**Files:**
- Modify: `edu_pre_admission_crm/views/crm_lead_views.xml`

- [ ] **Step 1: Add graph and pivot views**

Add before the action record (`action_pre_admission_pipeline`):

```xml
    <!-- ══════════════════════════════════════════════════════
         Pre-Admission Pipeline — Graph
    ══════════════════════════════════════════════════════ -->
    <record id="view_pre_admission_lead_graph" model="ir.ui.view">
        <field name="name">crm.lead.graph.pre_admission</field>
        <field name="model">crm.lead</field>
        <field name="arch" type="xml">
            <graph string="Pipeline" type="bar">
                <field name="lead_education_status"/>
                <field name="interested_program_id"/>
            </graph>
        </field>
    </record>

    <!-- ══════════════════════════════════════════════════════
         Pre-Admission Pipeline — Pivot
    ══════════════════════════════════════════════════════ -->
    <record id="view_pre_admission_lead_pivot" model="ir.ui.view">
        <field name="name">crm.lead.pivot.pre_admission</field>
        <field name="model">crm.lead</field>
        <field name="arch" type="xml">
            <pivot string="Pipeline">
                <field name="interested_program_id" type="row"/>
                <field name="lead_education_status" type="col"/>
            </pivot>
        </field>
    </record>
```

- [ ] **Step 2: Update the action view_mode**

Change the action `view_mode` (line 71) from:

```xml
<field name="view_mode">kanban,list,form,activity</field>
```

To:

```xml
<field name="view_mode">kanban,list,form,activity,graph,pivot</field>
```

- [ ] **Step 3: Add view bindings for graph and pivot**

Add after the existing `action_pre_admission_pipeline_view_list` record:

```xml
    <record id="action_pre_admission_pipeline_view_graph" model="ir.actions.act_window.view">
        <field name="sequence" eval="10"/>
        <field name="view_mode">graph</field>
        <field name="view_id" ref="view_pre_admission_lead_graph"/>
        <field name="act_window_id" ref="action_pre_admission_pipeline"/>
    </record>

    <record id="action_pre_admission_pipeline_view_pivot" model="ir.actions.act_window.view">
        <field name="sequence" eval="11"/>
        <field name="view_mode">pivot</field>
        <field name="view_id" ref="view_pre_admission_lead_pivot"/>
        <field name="act_window_id" ref="action_pre_admission_pipeline"/>
    </record>
```

- [ ] **Step 4: Add search filters for reporting**

In the search view extension (`view_crm_lead_search_pre_admission`), add group-by options:

```xml
                <separator/>
                <filter string="By Program" name="group_program"
                        context="{'group_by': 'interested_program_id'}"/>
                <filter string="By Counselor" name="group_counselor"
                        context="{'group_by': 'counselor_name'}"/>
                <filter string="By Source" name="group_source"
                        context="{'group_by': 'source_id'}"/>
                <filter string="By Medium" name="group_medium"
                        context="{'group_by': 'medium_id'}"/>
                <filter string="By Month" name="group_month"
                        context="{'group_by': 'inquiry_date:month'}"/>
```

- [ ] **Step 5: Commit**

```bash
git add edu_pre_admission_crm/views/crm_lead_views.xml
git commit -m "feat(pre_admission): graph, pivot views and reporting filters"
```

---

### Task 11: Menu & Manifest Updates

**Files:**
- Modify: `edu_pre_admission_crm/views/menu_views.xml`
- Modify: `edu_pre_admission_crm/__manifest__.py`

- [ ] **Step 1: Add Interactions menu item**

In `menu_views.xml`, add after the Guardians menu item:

```xml
    <menuitem id="menu_edu_interaction_log"
              name="Interactions"
              parent="menu_pre_admission_main"
              sequence="40"
              action="action_edu_interaction_log"
              groups="group_pre_admission_viewer,group_pre_admission_officer,edu_academic_structure.group_education_admin"/>
```

- [ ] **Step 2: Ensure all new files are in the manifest**

Verify `__manifest__.py` `data` list includes (in order):

```python
'data/edu_activity_type_data.xml',
```

(after `edu_relationship_type_data.xml`) and:

```python
'views/edu_interaction_log_views.xml',
```

(after `views/crm_lead_views.xml`)

- [ ] **Step 3: Commit**

```bash
git add edu_pre_admission_crm/views/menu_views.xml edu_pre_admission_crm/__manifest__.py
git commit -m "feat(pre_admission): add Interactions menu, finalize manifest"
```

---

### Task 12: Final Review & Version Bump

**Files:**
- Modify: `edu_pre_admission_crm/__manifest__.py`

- [ ] **Step 1: Bump module version**

Change version from `'19.0.2.0.0'` to `'19.0.3.0.0'`.

- [ ] **Step 2: Run a full module upgrade test**

```bash
# From the Odoo server, restart with module upgrade:
# ./odoo-bin -u edu_pre_admission_crm -d <dbname> --stop-after-init
```

Verify:
- Module installs without errors
- 4 activity types are created
- Interaction log model is accessible
- Kanban view loads with new card layout
- Form view shows next-step banner
- Graph and pivot views render
- Creating a lead without phone or email raises an error
- Completing an education activity creates an interaction log entry

- [ ] **Step 3: Commit version bump**

```bash
git add edu_pre_admission_crm/__manifest__.py
git commit -m "chore(pre_admission): bump version to 19.0.3.0.0 for robustness overhaul"
```
