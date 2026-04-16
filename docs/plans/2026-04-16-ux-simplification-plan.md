# EMIS UX Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce user friction across 8 EMIS modules — collapse admission from 8 to 4 states, CRM from 5 to 3 stages, enrollment from 3 to 2 states, assessment from 3 to 2 states; add Odoo Sign offer letters, register flow presets, attendance auto-start, and promotion staged close.

**Architecture:** Changes are scoped to existing modules only. Admission register gets flow-preset configuration (presets + boolean toggles) that control which stages the linked applications go through. Odoo Sign integration uses `sign.request` with a completion callback. All state collapses maintain backward-compatible data via pre_init_hook migration scripts.

**Tech Stack:** Odoo 19, Python 3.12+, XML views, PostgreSQL (for migration SQL)

**Spec:** `docs/specs/2026-04-16-ux-simplification-design.md`

---

## File Map

### edu_admission (Phase 1-3)
- Modify: `edu_admission/models/edu_admission_register.py` — add flow preset + toggle fields
- Modify: `edu_admission/models/edu_admission_application.py` — collapse state machine (8→4), add payment_received, sign fields
- Modify: `edu_admission/views/edu_admission_register_views.xml` — preset UI
- Modify: `edu_admission/views/edu_admission_application_views.xml` — full form redesign (notebooks + smart buttons)
- Modify: `edu_admission/__manifest__.py` — add `sign` to optional dependencies
- Create: `edu_admission/data/pre_init_hook.py` — SQL migration for state mapping (or use `pre_init_hook` in `__manifest__`)
- Modify: `edu_admission/models/edu_admission_scholarship_review.py` — minor: adjust visibility logic
- Create: `edu_admission/tests/test_flow_presets.py` — test preset onchange + toggle behavior
- Create: `edu_admission/tests/test_state_collapse.py` — test new 4-state transitions

### edu_enrollment (Phase 4)
- Modify: `edu_enrollment/models/edu_enrollment.py` — collapse states (3→2), merge confirm+activate
- Modify: `edu_enrollment/views/edu_enrollment_views.xml` — update buttons/statusbar
- Modify: `edu_student/models/edu_enrollment.py` — move student creation from action_confirm to action_activate

### edu_pre_admission_crm (Phase 5)
- Modify: `edu_pre_admission_crm/models/crm_lead.py` — collapse stages (5→3), enhance qualify/convert
- Modify: `edu_pre_admission_crm/views/crm_lead_views.xml` — update buttons/statusbar, add inline applicant tab

### edu_attendance (Phase 6)
- Modify: `edu_attendance/models/edu_attendance_sheet.py` — auto-start on write, bulk status buttons
- Modify: `edu_attendance/views/edu_attendance_sheet_views.xml` — replace Start Session with bulk buttons

### edu_assessment (Phase 6)
- Modify: `edu_assessment/models/edu_continuous_assessment_record.py` — collapse states (3→2)
- Modify: `edu_assessment/views/edu_continuous_assessment_record_views.xml` — inline marks, bulk confirm

### edu_academic_progression (Phase 6)
- Modify: `edu_academic_progression/wizard/edu_batch_promotion_wizard.py` — staged close
- Modify: `edu_academic_progression/wizard/edu_section_assignment_wizard.py` — single step, simplify toggles
- Modify: `edu_academic_progression/views/edu_progression_backfill_wizard_views.xml` — update if needed
- Modify: `edu_academic_progression/views/edu_section_assignment_wizard_views.xml` — single-step layout

### edu_classroom (Phase 6)
- Modify: `edu_classroom/models/edu_batch.py` — success notification instead of error

---

## Phase 1: Admission Register Flow Configuration

### Task 1: Add flow preset and toggle fields to admission register

**Files:**
- Modify: `edu_admission/models/edu_admission_register.py`
- Modify: `edu_admission/views/edu_admission_register_views.xml`
- Create: `edu_admission/tests/test_flow_presets.py`

- [ ] **Step 1: Write test for preset onchange behavior**

```python
# edu_admission/tests/test_flow_presets.py
from odoo.tests.common import TransactionCase


class TestFlowPresets(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env['edu.program'].create({'name': 'Test Program'})
        cls.year = cls.env['edu.academic.year'].create({
            'name': '2030-2031', 'code': '2030',
            'date_start': '2030-01-01', 'date_end': '2030-12-31',
            'state': 'open',
        })

    def _create_register(self, **kwargs):
        vals = {
            'name': 'Test Register',
            'program_id': self.program.id,
            'academic_year_id': self.year.id,
        }
        vals.update(kwargs)
        return self.env['edu.admission.register'].create(vals)

    def test_fast_track_preset_disables_all(self):
        reg = self._create_register(flow_preset='fast_track')
        reg._onchange_flow_preset()
        self.assertFalse(reg.require_academic_review)
        self.assertFalse(reg.require_scholarship_review)
        self.assertFalse(reg.require_offer_letter)
        self.assertFalse(reg.require_odoo_sign)
        self.assertFalse(reg.require_payment_confirmation)

    def test_standard_preset(self):
        reg = self._create_register(flow_preset='standard')
        reg._onchange_flow_preset()
        self.assertTrue(reg.require_academic_review)
        self.assertFalse(reg.require_scholarship_review)
        self.assertTrue(reg.require_offer_letter)
        self.assertFalse(reg.require_odoo_sign)
        self.assertTrue(reg.require_payment_confirmation)

    def test_full_preset_enables_all(self):
        reg = self._create_register(flow_preset='full')
        reg._onchange_flow_preset()
        self.assertTrue(reg.require_academic_review)
        self.assertTrue(reg.require_scholarship_review)
        self.assertTrue(reg.require_offer_letter)
        self.assertTrue(reg.require_odoo_sign)
        self.assertTrue(reg.require_payment_confirmation)

    def test_custom_preset_no_change(self):
        reg = self._create_register(
            flow_preset='custom',
            require_academic_review=True,
            require_scholarship_review=True,
            require_offer_letter=False,
        )
        reg._onchange_flow_preset()
        # Custom should not override existing values
        self.assertTrue(reg.require_academic_review)
        self.assertTrue(reg.require_scholarship_review)
        self.assertFalse(reg.require_offer_letter)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/custom_addons/education
python -m pytest edu_admission/tests/test_flow_presets.py -v 2>&1 | head -30
```
Expected: FAIL — fields don't exist yet.

- [ ] **Step 3: Add flow preset and toggle fields to register model**

Add these fields to `edu_admission/models/edu_admission_register.py` after the existing `note` field (~line 127):

```python
    # ── Flow Configuration ─────────────────────────────────────
    flow_preset = fields.Selection(
        [
            ('fast_track', 'Fast Track'),
            ('standard', 'Standard'),
            ('full', 'Full'),
            ('custom', 'Custom'),
        ],
        string='Admission Flow',
        default='standard',
        required=True,
        tracking=True,
        help="Controls which stages applications in this register go through.",
    )
    require_academic_review = fields.Boolean(
        string='Require Academic Review',
        default=True,
        tracking=True,
        help="If disabled, applications skip the review stage and go directly to approval.",
    )
    require_scholarship_review = fields.Boolean(
        string='Require Scholarship Review',
        default=False,
        tracking=True,
        help="If enabled, scholarship review is required before approval.",
    )
    require_offer_letter = fields.Boolean(
        string='Require Offer Letter',
        default=True,
        tracking=True,
        help="If enabled, an offer letter must be generated before enrollment.",
    )
    require_odoo_sign = fields.Boolean(
        string='Require Digital Signature',
        default=False,
        tracking=True,
        help="If enabled, offer letter must be signed via Odoo Sign before enrollment.",
    )
    require_payment_confirmation = fields.Boolean(
        string='Require Payment Confirmation',
        default=True,
        tracking=True,
        help="If enabled, payment must be confirmed before enrollment.",
    )
    sign_template_id = fields.Many2one(
        'sign.template',
        string='Offer Letter Sign Template',
        ondelete='set null',
        help="Odoo Sign template used for offer letter digital signatures.",
    )
```

Add onchange method:

```python
    _PRESET_MAP = {
        'fast_track': {
            'require_academic_review': False,
            'require_scholarship_review': False,
            'require_offer_letter': False,
            'require_odoo_sign': False,
            'require_payment_confirmation': False,
        },
        'standard': {
            'require_academic_review': True,
            'require_scholarship_review': False,
            'require_offer_letter': True,
            'require_odoo_sign': False,
            'require_payment_confirmation': True,
        },
        'full': {
            'require_academic_review': True,
            'require_scholarship_review': True,
            'require_offer_letter': True,
            'require_odoo_sign': True,
            'require_payment_confirmation': True,
        },
    }

    @api.onchange('flow_preset')
    def _onchange_flow_preset(self):
        preset_vals = self._PRESET_MAP.get(self.flow_preset)
        if preset_vals:
            for field_name, value in preset_vals.items():
                setattr(self, field_name, value)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /opt/custom_addons/education
python -m pytest edu_admission/tests/test_flow_presets.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Add flow configuration UI to register form view**

In `edu_admission/views/edu_admission_register_views.xml`, add a new notebook page inside the form view after the Fee Configuration section (~line 182). Add a "Flow Configuration" group before the notebook:

```xml
<!-- After Fee Configuration & System groups, before notebook -->
<group string="Admission Flow">
    <group>
        <field name="flow_preset" widget="radio" options="{'horizontal': true}"/>
    </group>
    <group attrs="{'invisible': [('flow_preset', '!=', 'custom')]}">
        <field name="require_academic_review"/>
        <field name="require_scholarship_review"/>
        <field name="require_offer_letter"/>
        <field name="require_odoo_sign" attrs="{'invisible': [('require_offer_letter', '=', False)]}"/>
        <field name="require_payment_confirmation"/>
    </group>
    <group attrs="{'invisible': ['|', ('require_odoo_sign', '=', False), ('flow_preset', '=', 'fast_track')]}">
        <field name="sign_template_id"/>
    </group>
</group>
```

Also show toggle summary when not in custom mode:

```xml
<div attrs="{'invisible': [('flow_preset', '=', 'custom')]}">
    <field name="require_academic_review" invisible="1"/>
    <field name="require_scholarship_review" invisible="1"/>
    <field name="require_offer_letter" invisible="1"/>
    <field name="require_odoo_sign" invisible="1"/>
    <field name="require_payment_confirmation" invisible="1"/>
</div>
```

- [ ] **Step 6: Commit**

```bash
git add edu_admission/models/edu_admission_register.py \
        edu_admission/views/edu_admission_register_views.xml \
        edu_admission/tests/test_flow_presets.py
git commit -m "feat(edu_admission): add flow presets and toggle fields to register"
```

---

### Task 2: Collapse admission application state machine (8 → 4 states)

**Files:**
- Modify: `edu_admission/models/edu_admission_application.py`
- Create: `edu_admission/tests/test_state_collapse.py`

This is the largest single change. The state field changes from 8 values to 4+rejected.

- [ ] **Step 1: Write tests for new state transitions**

```python
# edu_admission/tests/test_state_collapse.py
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestStateCollapse(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env['edu.program'].create({'name': 'Test Program'})
        cls.year = cls.env['edu.academic.year'].create({
            'name': '2031-2032', 'code': '2031',
            'date_start': '2031-01-01', 'date_end': '2031-12-31',
            'state': 'open',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test Applicant'})
        cls.profile = cls.env['edu.applicant.profile'].create({
            'partner_id': cls.partner.id,
        })
        cls.register = cls.env['edu.admission.register'].create({
            'name': 'Test Register',
            'program_id': cls.program.id,
            'academic_year_id': cls.year.id,
            'flow_preset': 'fast_track',
        })
        cls.register._onchange_flow_preset()
        cls.register.action_open()

    def _create_app(self, **kwargs):
        vals = {
            'applicant_profile_id': self.profile.id,
            'admission_register_id': self.register.id,
            'program_id': self.program.id,
            'academic_year_id': self.year.id,
        }
        vals.update(kwargs)
        return self.env['edu.admission.application'].create(vals)

    def test_fast_track_draft_to_enrolled(self):
        """Fast track: submit auto-skips review, approve, enroll."""
        app = self._create_app()
        self.assertEqual(app.state, 'draft')
        app.action_submit()
        # With fast_track, review is skipped → goes to approved
        self.assertEqual(app.state, 'approved')
        app.action_enroll()
        self.assertEqual(app.state, 'enrolled')

    def test_standard_flow_requires_review(self):
        """Standard: submit → under_review → approve → enrolled."""
        self.register.write({
            'flow_preset': 'custom',
            'require_academic_review': True,
            'require_offer_letter': False,
            'require_payment_confirmation': False,
        })
        app = self._create_app()
        app.action_submit()
        self.assertEqual(app.state, 'under_review')
        app.action_approve()
        self.assertEqual(app.state, 'approved')
        app.action_enroll()
        self.assertEqual(app.state, 'enrolled')

    def test_payment_gate_blocks_enrollment(self):
        """Payment required: cannot enroll without payment_received."""
        self.register.write({
            'flow_preset': 'custom',
            'require_academic_review': False,
            'require_offer_letter': False,
            'require_payment_confirmation': True,
        })
        app = self._create_app()
        app.action_submit()
        self.assertEqual(app.state, 'approved')
        with self.assertRaises(UserError):
            app.action_enroll()
        app.payment_received = True
        app.action_enroll()
        self.assertEqual(app.state, 'enrolled')

    def test_reject_from_any_state(self):
        app = self._create_app()
        app.action_submit()
        app.action_reject()
        self.assertEqual(app.state, 'rejected')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest edu_admission/tests/test_state_collapse.py -v 2>&1 | head -30
```
Expected: FAIL — new states and methods don't exist yet.

- [ ] **Step 3: Rewrite the state field and transition methods**

In `edu_admission/models/edu_admission_application.py`:

**Replace the state Selection field** (~line 290) with:

```python
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('under_review', 'Under Review'),
            ('approved', 'Approved'),
            ('enrolled', 'Enrolled'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
```

**Add payment_received field** after offer fields:

```python
    payment_received = fields.Boolean(
        string='Payment Received',
        tracking=True,
        copy=False,
        help="Manually toggled by admin to confirm payment has been received.",
    )
```

**Add sign integration fields** (after payment_received):

```python
    sign_request_id = fields.Many2one(
        'sign.request',
        string='Sign Request',
        ondelete='set null',
        copy=False,
        readonly=True,
    )
    sign_status = fields.Selection(
        related='sign_request_id.state',
        string='Signature Status',
        store=True,
    )
```

**Rewrite transition methods:**

Replace `action_submit`, `action_start_review`, `action_start_scholarship_review`, `action_mark_review_complete`, `action_generate_offer`, `action_accept_offer`, `action_reject_offer`, `action_mark_ready_for_enrollment`, `action_enroll` with:

```python
    def action_submit(self):
        """Submit application. Auto-skips review if not required."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft applications can be submitted."))
        if not self.applicant_profile_id or not self.program_id:
            raise UserError(_("Applicant profile and program are required."))

        register = self.admission_register_id
        if register.require_academic_review:
            self.state = 'under_review'
        else:
            self.state = 'approved'

    def action_approve(self):
        """Approve application after review. Validates sub-reviews if required."""
        self.ensure_one()
        if self.state != 'under_review':
            raise UserError(_("Only applications under review can be approved."))

        register = self.admission_register_id
        if register.require_scholarship_review:
            # Check all scholarship reviews are finalized
            pending = self.scholarship_review_ids.filtered(
                lambda r: r.state in ('draft', 'under_review')
            )
            if pending:
                raise UserError(_(
                    "%(count)s scholarship review(s) are still pending. "
                    "Please finalize all reviews before approving.",
                    count=len(pending),
                ))
        self.state = 'approved'

    def action_enroll(self):
        """Enroll the application. Checks all gates configured on register."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Only approved applications can be enrolled."))

        register = self.admission_register_id
        blocks = []

        if register.require_offer_letter and not self.offer_letter_generated:
            blocks.append(_("Offer letter has not been generated."))

        if register.require_odoo_sign and self.sign_status != 'signed':
            blocks.append(_("Offer letter has not been digitally signed."))

        if register.require_payment_confirmation and not self.payment_received:
            blocks.append(_("Payment has not been confirmed."))

        if blocks:
            raise UserError("\n".join(blocks))

        self.state = 'enrolled'
        self._create_enrollment_on_enroll()

    def action_reject(self):
        """Reject application from any non-terminal state."""
        self.ensure_one()
        if self.state in ('enrolled', 'rejected'):
            raise UserError(_("Cannot reject an enrolled or already-rejected application."))
        self.state = 'rejected'

    def action_reset_draft(self):
        """Reset rejected/draft applications back to draft."""
        self.ensure_one()
        if self.state not in ('rejected',):
            raise UserError(_("Only rejected applications can be reset to draft."))
        self.state = 'draft'
        self.review_complete = False
        self.offer_letter_generated = False
        self.offer_status = 'not_generated'
        self.payment_received = False
```

**Add helper for enrollment creation:**

```python
    def _create_enrollment_on_enroll(self):
        """Create enrollment record when application is enrolled.
        Overridden by edu_enrollment module for full implementation."""
        pass
```

**Update frozen states:**

```python
    _FROZEN_STATES = frozenset({'enrolled'})
```

**Update computed flags** — replace `_compute_process_flags` and `_compute_enrollment_readiness` with simpler logic that reads from register toggles.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest edu_admission/tests/test_state_collapse.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Update scholarship review flow to work within under_review state**

In `edu_admission/models/edu_admission_application.py`, update `action_view_scholarship_reviews` to work from `under_review` state. The scholarship review tab is visible when `require_scholarship_review=True` on the register, and reviews happen inside the `under_review` state (no separate `scholarship_review` state).

Remove methods: `action_start_scholarship_review`, `action_mark_review_complete`, `action_mark_ready_for_enrollment`.

Update `action_generate_offer` to work from `approved` state:

```python
    def action_generate_offer(self):
        """Generate offer letter in approved state."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Offer can only be generated for approved applications."))
        if not self.admission_register_id.require_offer_letter:
            raise UserError(_("Offer letters are not required for this register."))

        self._finalize_scholarship_if_needed()
        self.offer_letter_generated = True
        self.offer_letter_date = fields.Date.today()
        self.offer_status = 'sent'
```

- [ ] **Step 6: Commit**

```bash
git add edu_admission/models/edu_admission_application.py \
        edu_admission/tests/test_state_collapse.py
git commit -m "feat(edu_admission): collapse application states from 8 to 4

States: draft → under_review → approved → enrolled (+ rejected)
Scholarship review happens within under_review state.
Offer letter, sign, payment are optional gates within approved state."
```

---

### Task 3: Redesign application form view with notebooks and smart buttons

**Files:**
- Modify: `edu_admission/views/edu_admission_application_views.xml`

- [ ] **Step 1: Rewrite form header buttons for new states**

Replace the header section (~lines 95-133) with buttons matching the new state machine:

```xml
<header>
    <button name="action_submit" string="Submit"
            type="object" class="btn-primary"
            attrs="{'invisible': [('state', '!=', 'draft')]}"/>
    <button name="action_approve" string="Approve"
            type="object" class="btn-primary"
            attrs="{'invisible': [('state', '!=', 'under_review')]}"/>
    <button name="action_generate_offer" string="Generate Offer"
            type="object" class="btn-secondary"
            attrs="{'invisible': ['|',
                ('state', '!=', 'approved'),
                ('show_offer_button', '=', False)]}"/>
    <button name="action_send_sign_request" string="Send for Signing"
            type="object" class="btn-secondary"
            attrs="{'invisible': ['|',
                ('state', '!=', 'approved'),
                ('show_sign_button', '=', False)]}"/>
    <button name="action_enroll" string="Enroll"
            type="object" class="btn-primary"
            attrs="{'invisible': [('state', '!=', 'approved')]}"
            confirm="Enroll this applicant? This will create an enrollment record."/>
    <button name="action_reject" string="Reject"
            type="object" class="btn-danger"
            attrs="{'invisible': [('state', 'in', ('enrolled', 'rejected', 'draft'))]}"/>
    <button name="action_reset_draft" string="Reset to Draft"
            type="object"
            attrs="{'invisible': [('state', '!=', 'rejected')]}"/>
    <field name="state" widget="statusbar"
           statusbar_visible="draft,under_review,approved,enrolled"/>
</header>
```

- [ ] **Step 2: Add smart buttons row**

Replace existing smart buttons (~lines 137-167):

```xml
<div name="button_box" position="inside">
    <button name="action_view_scholarship_reviews"
            type="object" class="oe_stat_button"
            icon="fa-gift"
            attrs="{'invisible': [('show_scholarship_button', '=', False)]}">
        <field name="scholarship_review_count" widget="statinfo" string="Scholarships"/>
    </button>
    <button name="action_print_offer_letter"
            type="object" class="oe_stat_button"
            icon="fa-file-text"
            attrs="{'invisible': [('offer_letter_generated', '=', False)]}">
        <field name="offer_status" widget="badge"/>
        <span>Offer Letter</span>
    </button>
    <button name="action_view_enrollment"
            type="object" class="oe_stat_button"
            icon="fa-graduation-cap"
            attrs="{'invisible': [('enrollment_count', '=', 0)]}">
        <field name="enrollment_count" widget="statinfo" string="Enrollment"/>
    </button>
    <button name="action_view_student"
            type="object" class="oe_stat_button"
            icon="fa-user"
            attrs="{'invisible': [('student_id', '=', False)]}">
        <span>Student</span>
    </button>
</div>
```

- [ ] **Step 3: Rewrite form body with notebook pages**

Replace the main form body with notebook-organized layout:

```xml
<sheet>
    <!-- Smart buttons -->
    <div name="button_box" class="oe_button_box">
        <!-- (smart buttons from step 2) -->
    </div>
    <widget name="web_ribbon" title="Enrolled" bg_color="text-bg-success"
            attrs="{'invisible': [('state', '!=', 'enrolled')]}"/>
    <widget name="web_ribbon" title="Rejected" bg_color="text-bg-danger"
            attrs="{'invisible': [('state', '!=', 'rejected')]}"/>

    <div class="oe_title">
        <h1><field name="application_no" readonly="1"/></h1>
    </div>

    <!-- Top-level: applicant + register context -->
    <group>
        <group string="Applicant">
            <field name="applicant_profile_id"
                   attrs="{'readonly': [('state', '!=', 'draft')]}"/>
            <field name="partner_id" invisible="1"/>
            <field name="assigned_user_id"/>
        </group>
        <group string="Admission">
            <field name="admission_register_id"
                   attrs="{'readonly': [('state', '!=', 'draft')]}"/>
            <field name="program_id"
                   attrs="{'readonly': [('state', '!=', 'draft')]}"/>
            <field name="academic_year_id"
                   attrs="{'readonly': [('state', '!=', 'draft')]}"/>
            <field name="batch_id"
                   attrs="{'readonly': [('state', '!=', 'draft')]}"/>
        </group>
    </group>

    <notebook>
        <!-- Tab 1: Personal Info -->
        <page string="Personal Info" name="personal_info">
            <group>
                <group string="Contact">
                    <!-- Related fields from applicant_profile -->
                    <field name="partner_id" string="Contact" readonly="1"/>
                </group>
                <group string="Demographics">
                    <field name="department_id" readonly="1"/>
                </group>
            </group>
        </page>

        <!-- Tab 2: Academic -->
        <page string="Academic" name="academic">
            <group>
                <group string="Program Details">
                    <field name="program_id" readonly="1"/>
                    <field name="batch_id" readonly="1"/>
                    <field name="academic_year_id" readonly="1"/>
                    <field name="department_id" readonly="1"/>
                </group>
            </group>
        </page>

        <!-- Tab 3: Guardian -->
        <page string="Guardian" name="guardian">
            <!-- Guardian one2many from applicant profile -->
        </page>

        <!-- Tab 4: Financial -->
        <page string="Financial" name="financial">
            <group>
                <group string="Fee Structure">
                    <field name="fee_structure_id" readonly="1"/>
                    <field name="currency_id" invisible="1"/>
                    <field name="base_total_fee" readonly="1"/>
                    <field name="scholarship_eligible_total" readonly="1"/>
                </group>
                <group string="Payment">
                    <field name="selected_payment_plan_id"/>
                    <field name="net_fee_after_scholarship" readonly="1"/>
                    <field name="payment_received"
                           attrs="{'invisible': [('state', '!=', 'approved')]}"/>
                </group>
            </group>
            <group string="Scholarship Summary"
                   attrs="{'invisible': [('scholarship_review_count', '=', 0)]}">
                <field name="scholarship_status" widget="badge" readonly="1"/>
                <field name="total_scholarship_discount_amount" readonly="1"/>
                <field name="scholarship_cap_applied" readonly="1"/>
            </group>
            <field name="fee_summary_display" readonly="1"/>
        </page>

        <!-- Tab 5: Documents -->
        <page string="Documents" name="documents">
            <!-- Attachment widget or document list -->
        </page>

        <!-- Tab 6: Notes -->
        <page string="Notes" name="notes">
            <group>
                <field name="internal_note" placeholder="Internal notes..."/>
            </group>
            <group>
                <field name="note" placeholder="General notes..."/>
            </group>
        </page>
    </notebook>
</sheet>
<chatter/>
```

- [ ] **Step 4: Update search view filters for new states**

Replace state filters in search view (~lines 24-37):

```xml
<filter name="filter_draft" string="Draft"
        domain="[('state', '=', 'draft')]"/>
<filter name="filter_under_review" string="Under Review"
        domain="[('state', '=', 'under_review')]"/>
<filter name="filter_approved" string="Approved"
        domain="[('state', '=', 'approved')]"/>
<filter name="filter_enrolled" string="Enrolled"
        domain="[('state', '=', 'enrolled')]"/>
<filter name="filter_rejected" string="Rejected"
        domain="[('state', '=', 'rejected')]"/>
```

- [ ] **Step 5: Update list view badge decorations**

```xml
<field name="state" widget="badge"
       decoration-info="state == 'draft'"
       decoration-warning="state == 'under_review'"
       decoration-success="state in ('approved', 'enrolled')"
       decoration-danger="state == 'rejected'"/>
```

- [ ] **Step 6: Add computed visibility helpers to model**

In `edu_admission/models/edu_admission_application.py`, add:

```python
    show_offer_button = fields.Boolean(compute='_compute_button_visibility')
    show_sign_button = fields.Boolean(compute='_compute_button_visibility')
    show_scholarship_button = fields.Boolean(compute='_compute_button_visibility')

    @api.depends('state', 'admission_register_id.require_offer_letter',
                 'admission_register_id.require_odoo_sign',
                 'admission_register_id.require_scholarship_review',
                 'offer_letter_generated')
    def _compute_button_visibility(self):
        for app in self:
            reg = app.admission_register_id
            app.show_offer_button = (
                app.state == 'approved'
                and reg.require_offer_letter
                and not app.offer_letter_generated
            )
            app.show_sign_button = (
                app.state == 'approved'
                and reg.require_odoo_sign
                and app.offer_letter_generated
                and not app.sign_request_id
            )
            app.show_scholarship_button = bool(
                reg.require_scholarship_review
            )
```

- [ ] **Step 7: Commit**

```bash
git add edu_admission/views/edu_admission_application_views.xml \
        edu_admission/models/edu_admission_application.py
git commit -m "feat(edu_admission): redesign application form with notebooks and smart buttons

Tabs: Personal Info, Academic, Guardian, Financial, Documents, Notes.
Smart buttons: Scholarships, Offer Letter, Enrollment, Student."
```

---

### Task 4: Odoo Sign integration for offer letters

**Files:**
- Modify: `edu_admission/models/edu_admission_application.py`
- Modify: `edu_admission/__manifest__.py`

- [ ] **Step 1: Add sign module as optional dependency**

In `__manifest__.py`, the `sign` module should NOT be a hard dependency (it's a paid module). Instead, check at runtime:

```python
# In __manifest__.py, do NOT add sign to depends.
# Instead, use try/except in the model.
```

In the application model, add the sign request method:

```python
    def action_send_sign_request(self):
        """Create and send Odoo Sign request for offer letter."""
        self.ensure_one()
        if not self.env['ir.module.module'].sudo().search(
            [('name', '=', 'sign'), ('state', '=', 'installed')], limit=1
        ):
            raise UserError(_("Odoo Sign module is not installed."))

        register = self.admission_register_id
        if not register.sign_template_id:
            raise UserError(_("No sign template configured on the admission register."))

        if not self.offer_letter_generated:
            raise UserError(_("Generate the offer letter before sending for signature."))

        SignRequest = self.env['sign.request']
        sign_request = SignRequest.create({
            'template_id': register.sign_template_id.id,
            'reference': _("Offer Letter - %s", self.application_no),
            'request_item_ids': [(0, 0, {
                'partner_id': self.partner_id.id,
                'role_id': self.env.ref('sign.sign_item_role_customer').id,
            })],
        })
        sign_request.action_sent()
        self.sign_request_id = sign_request.id
        self.offer_status = 'sent'
```

- [ ] **Step 2: Add sign completion callback**

Override `write` on `sign.request` or use the sign module's built-in callback mechanism. In Odoo, `sign.request` fires an action when completed. We intercept via override on the application model:

```python
    @api.depends('sign_request_id.state')
    def _compute_sign_status_sync(self):
        """Auto-enroll when sign request is completed and all other gates pass."""
        for app in self:
            if (app.sign_request_id
                    and app.sign_request_id.state == 'signed'
                    and app.state == 'approved'):
                try:
                    app.action_enroll()
                except UserError:
                    pass  # Other gates not met yet
```

- [ ] **Step 3: Hide sign fields if module not installed**

In the register form view, make `sign_template_id` and `require_odoo_sign` conditionally visible. Since we can't use `attrs` for module detection, use groups or a computed field:

```python
    sign_module_installed = fields.Boolean(
        compute='_compute_sign_module_installed',
    )

    def _compute_sign_module_installed(self):
        installed = bool(self.env['ir.module.module'].sudo().search(
            [('name', '=', 'sign'), ('state', '=', 'installed')], limit=1
        ))
        for rec in self:
            rec.sign_module_installed = installed
```

- [ ] **Step 4: Commit**

```bash
git add edu_admission/models/edu_admission_application.py \
        edu_admission/models/edu_admission_register.py \
        edu_admission/__manifest__.py
git commit -m "feat(edu_admission): add Odoo Sign integration for offer letters

Sign request created from register template, sent to applicant.
Auto-enrolls when signed + other gates met. Gracefully hidden if sign not installed."
```

---

## Phase 2: Enrollment Simplification

### Task 5: Collapse enrollment states (3 → 2) and move student creation

**Files:**
- Modify: `edu_enrollment/models/edu_enrollment.py`
- Modify: `edu_enrollment/views/edu_enrollment_views.xml`
- Modify: `edu_student/models/edu_enrollment.py`

- [ ] **Step 1: Update enrollment state field**

In `edu_enrollment/models/edu_enrollment.py`, change the state Selection (~line 243):

```python
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('cancelled', 'Cancelled'),
            ('completed', 'Completed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
```

- [ ] **Step 2: Merge confirm + activate into single action_activate**

Replace `action_confirm` and `action_activate` with a single method:

```python
    def action_activate(self):
        """Activate enrollment — single step from draft to active.
        Creates student record and portal user if edu_student is installed."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft enrollments can be activated."))

        # Check checklist if any items exist
        if self.checklist_line_ids:
            required_pending = self.checklist_line_ids.filtered(
                lambda l: l.required and not l.complete
            )
            if required_pending:
                raise UserError(_(
                    "%(count)s required checklist item(s) are incomplete.",
                    count=len(required_pending),
                ))

        self.write({
            'state': 'active',
            'activated_by_user_id': self.env.uid,
            'activated_on': fields.Datetime.now(),
            'confirmed_by_user_id': self.env.uid,
            'confirmed_on': fields.Datetime.now(),
        })
```

Remove `action_confirm` method. Remove `can_confirm` computed field.

- [ ] **Step 3: Move student creation to action_activate**

In `edu_student/models/edu_enrollment.py`, override `action_activate` instead of `action_confirm`:

```python
    def action_activate(self):
        """Override to auto-create student and portal user on activation."""
        result = super().action_activate()
        for enrollment in self:
            if not enrollment.student_id:
                enrollment.action_create_student()
            enrollment._ensure_portal_user()
        return result
```

Remove the `action_confirm` override from this file.

- [ ] **Step 4: Update enrollment form view**

In `edu_enrollment/views/edu_enrollment_views.xml`, update header buttons:

```xml
<header>
    <button name="action_activate" string="Activate"
            type="object" class="btn-primary"
            attrs="{'invisible': [('state', '!=', 'draft')]}"
            confirm="Activate this enrollment? A student record will be created."/>
    <button name="action_complete" string="Complete"
            type="object"
            attrs="{'invisible': [('state', '!=', 'active')]}"/>
    <button name="action_cancel" string="Cancel"
            type="object"
            attrs="{'invisible': [('state', 'not in', ('draft',))]}"/>
    <button name="action_force_cancel" string="Force Cancel"
            type="object" groups="edu_enrollment.group_enrollment_admin"
            attrs="{'invisible': [('state', 'not in', ('active',))]}"/>
    <button name="action_reset_draft" string="Reset to Draft"
            type="object"
            attrs="{'invisible': [('state', '!=', 'cancelled')]}"/>
    <field name="state" widget="statusbar"
           statusbar_visible="draft,active"/>
</header>
```

- [ ] **Step 5: Commit**

```bash
git add edu_enrollment/models/edu_enrollment.py \
        edu_enrollment/views/edu_enrollment_views.xml \
        edu_student/models/edu_enrollment.py
git commit -m "feat(edu_enrollment): collapse states from 3 to 2 (draft → active)

Merge confirm + activate into single action. Student + portal user
auto-created on activation."
```

---

## Phase 3: Pre-Admission CRM Simplification

### Task 6: Collapse CRM stages (5 → 3) and enhance qualify/convert

**Files:**
- Modify: `edu_pre_admission_crm/models/crm_lead.py`
- Modify: `edu_pre_admission_crm/views/crm_lead_views.xml`

- [ ] **Step 1: Update lead_education_status Selection**

In `crm_lead.py` (~line 26), change to:

```python
    lead_education_status = fields.Selection(
        [
            ('inquiry', 'Inquiry'),
            ('qualified', 'Qualified'),
            ('converted', 'Converted'),
            ('lost', 'Lost'),
        ],
        string='Education Status',
        default='inquiry',
        tracking=True,
        index=True,
        group_expand='_group_expand_lead_education_status',
    )
```

- [ ] **Step 2: Rewrite transition methods**

Remove `action_set_prospect` and `action_set_ready_for_application`.

Enhance `action_set_qualified`:

```python
    def action_set_qualified(self):
        """Qualify the lead. Auto-creates applicant profile if needed."""
        self.ensure_one()
        if self.lead_education_status not in ('inquiry',):
            raise UserError(_("Only inquiries can be qualified."))

        # Auto-create profile from quick name if needed
        if not self.applicant_profile_id and self.quick_applicant_name:
            self._create_profile_from_quick_name()

        if not self.applicant_profile_id:
            raise UserError(_("An applicant profile is required to qualify this lead."))
        if not self.interested_program_id:
            raise UserError(_("A program of interest is required."))

        self.lead_education_status = 'qualified'
```

Enhance `action_convert_to_admission_application` — add register selection dialog:

```python
    def action_convert_to_admission_application(self):
        """Convert qualified lead to admission application with register selection."""
        self.ensure_one()
        self._check_conversion_readiness()

        register = self._suggest_admission_register()
        # If multiple registers found, could show wizard — for now use best match
        vals = self._prepare_admission_application_vals(register=register)
        application = self.env['edu.admission.application'].create(vals)

        self.write({
            'is_converted_to_application': True,
            'conversion_date': fields.Datetime.now(),
            'lead_education_status': 'converted',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Application'),
            'res_model': 'edu.admission.application',
            'res_id': application.id,
            'view_mode': 'form',
            'target': 'current',
        }
```

- [ ] **Step 3: Update CRM form view buttons**

In `crm_lead_views.xml`, replace header buttons (~lines 120-150):

```xml
<button name="action_set_qualified" string="Qualify"
        type="object" class="btn-primary"
        attrs="{'invisible': [('lead_education_status', '!=', 'inquiry')]}"/>
<button name="action_convert_to_admission_application"
        string="Convert to Application"
        type="object" class="btn-primary"
        attrs="{'invisible': [('lead_education_status', '!=', 'qualified')]}"/>
<field name="lead_education_status" widget="statusbar"
       statusbar_visible="inquiry,qualified,converted"/>
```

Remove "Mark as Prospect" and "Ready for Application" buttons.

- [ ] **Step 4: Add inline applicant data tab**

Add a notebook page showing key applicant profile fields inline:

```xml
<page string="Applicant Details" name="applicant_details"
      attrs="{'invisible': [('applicant_profile_id', '=', False)]}">
    <group>
        <group string="Personal">
            <field name="applicant_profile_id" readonly="1"/>
            <!-- Related fields from applicant profile shown inline -->
        </group>
        <group string="Contact">
            <field name="phone"/>
            <field name="email_from"/>
        </group>
    </group>
</page>
```

- [ ] **Step 5: Update search view filters**

Remove `prospect` and `ready_for_application` filters:

```xml
<filter name="filter_inquiry" string="Inquiry"
        domain="[('lead_education_status', '=', 'inquiry')]"/>
<filter name="filter_qualified" string="Qualified"
        domain="[('lead_education_status', '=', 'qualified')]"/>
<filter name="filter_converted" string="Converted"
        domain="[('lead_education_status', '=', 'converted')]"/>
```

- [ ] **Step 6: Update group_expand method**

```python
    @api.model
    def _group_expand_lead_education_status(self, statuses, domain):
        return ['inquiry', 'qualified', 'converted', 'lost']
```

- [ ] **Step 7: Commit**

```bash
git add edu_pre_admission_crm/models/crm_lead.py \
        edu_pre_admission_crm/views/crm_lead_views.xml
git commit -m "feat(edu_pre_admission_crm): collapse CRM stages from 5 to 3

Stages: inquiry → qualified → converted. Auto-creates profile on qualify.
Removed prospect and ready_for_application stages."
```

---

### Task 7: CRM duplicate merge

**Files:**
- Modify: `edu_pre_admission_crm/models/crm_lead.py`
- Create: `edu_pre_admission_crm/wizard/edu_lead_merge_wizard.py`
- Create: `edu_pre_admission_crm/wizard/edu_lead_merge_wizard_views.xml`
- Modify: `edu_pre_admission_crm/views/crm_lead_views.xml`

- [ ] **Step 1: Create merge wizard model**

```python
# edu_pre_admission_crm/wizard/edu_lead_merge_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduLeadMergeWizard(models.TransientModel):
    _name = 'edu.lead.merge.wizard'
    _description = 'Merge Duplicate Leads'

    lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade')
    duplicate_lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade')
    keep_phone_from = fields.Selection(
        [('lead', 'Current Lead'), ('duplicate', 'Duplicate Lead')],
        default='lead',
    )
    keep_email_from = fields.Selection(
        [('lead', 'Current Lead'), ('duplicate', 'Duplicate Lead')],
        default='lead',
    )
    keep_program_from = fields.Selection(
        [('lead', 'Current Lead'), ('duplicate', 'Duplicate Lead')],
        default='lead',
    )

    def action_merge(self):
        self.ensure_one()
        target = self.lead_id
        source = self.duplicate_lead_id

        vals = {}
        if self.keep_phone_from == 'duplicate' and source.phone:
            vals['phone'] = source.phone
        if self.keep_email_from == 'duplicate' and source.email_from:
            vals['email_from'] = source.email_from
        if self.keep_program_from == 'duplicate' and source.interested_program_id:
            vals['interested_program_id'] = source.interested_program_id.id

        if vals:
            target.write(vals)

        # Move messages and activities from source to target
        source.message_ids.write({'res_id': target.id})

        # Archive source
        source.write({'active': False, 'lead_education_status': 'lost'})

        target.message_post(body=_(
            "Merged with duplicate lead <b>%s</b>.",
            source.display_name,
        ))
```

- [ ] **Step 2: Create wizard view**

```xml
<!-- edu_pre_admission_crm/wizard/edu_lead_merge_wizard_views.xml -->
<odoo>
    <record id="view_edu_lead_merge_wizard_form" model="ir.ui.view">
        <field name="name">edu.lead.merge.wizard.form</field>
        <field name="model">edu.lead.merge.wizard</field>
        <field name="arch" type="xml">
            <form>
                <group>
                    <group string="Current Lead">
                        <field name="lead_id" readonly="1"/>
                    </group>
                    <group string="Duplicate Lead">
                        <field name="duplicate_lead_id" readonly="1"/>
                    </group>
                </group>
                <group string="Keep Values From">
                    <field name="keep_phone_from" widget="radio"/>
                    <field name="keep_email_from" widget="radio"/>
                    <field name="keep_program_from" widget="radio"/>
                </group>
                <footer>
                    <button name="action_merge" string="Merge"
                            type="object" class="btn-primary"/>
                    <button string="Cancel" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>
</odoo>
```

- [ ] **Step 3: Add merge button to lead form**

In `crm_lead_views.xml`, add a "Merge" button near the duplicate detection area:

```python
    # In crm_lead.py, add merge action method
    def action_open_merge_wizard(self):
        self.ensure_one()
        duplicates = self.duplicate_phone_lead_ids | self.duplicate_email_lead_ids
        if not duplicates:
            raise UserError(_("No duplicate leads detected."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Merge Duplicate Lead'),
            'res_model': 'edu.lead.merge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_duplicate_lead_id': duplicates[0].id,
            },
        }
```

- [ ] **Step 4: Update manifest and __init__ files**

Add wizard to `__init__.py` and data file to `__manifest__.py`.

- [ ] **Step 5: Commit**

```bash
git add edu_pre_admission_crm/
git commit -m "feat(edu_pre_admission_crm): add duplicate lead merge wizard

Side-by-side comparison, pick field values from either lead,
moves messages, archives source lead."
```

---

## Phase 4: Quick Wins (Attendance, Assessment, Progression, Classroom)

### Task 8: Attendance auto-start and bulk status buttons

**Files:**
- Modify: `edu_attendance/models/edu_attendance_sheet.py`
- Modify: `edu_attendance/views/edu_attendance_sheet_views.xml`

- [ ] **Step 1: Add auto-start on write**

In `edu_attendance_sheet.py`, modify the `write` method (~line 335):

```python
    def write(self, vals):
        # Auto-start: if a line status is being changed and sheet is draft, start it
        if 'line_ids' in vals:
            for sheet in self:
                if sheet.state == 'draft':
                    sheet.state = 'in_progress'
                    if not sheet.line_ids:
                        sheet.action_generate_lines()
        return super().write(vals)
```

Also override `write` on `edu.attendance.sheet.line` to trigger auto-start:

```python
# In edu_attendance/models/edu_attendance_sheet_line.py (or wherever lines are defined)
    def write(self, vals):
        if 'status' in vals:
            draft_sheets = self.mapped('sheet_id').filtered(
                lambda s: s.state == 'draft'
            )
            if draft_sheets:
                draft_sheets.write({'state': 'in_progress'})
                for sheet in draft_sheets:
                    if not sheet.line_ids:
                        sheet.action_generate_lines()
        return super().write(vals)
```

- [ ] **Step 2: Add bulk status buttons**

In `edu_attendance_sheet.py`, add methods:

```python
    def action_mark_all_absent(self):
        """Mark all students absent."""
        self.ensure_one()
        if self.state == 'draft':
            self.action_start()
        self.line_ids.write({'status': 'absent'})

    def action_mark_all_late(self):
        """Mark all students late."""
        self.ensure_one()
        if self.state == 'draft':
            self.action_start()
        self.line_ids.write({'status': 'late'})
```

- [ ] **Step 3: Update attendance sheet form view**

In `edu_attendance_sheet_views.xml`, remove "Start Session" button (~line 94-98) and add bulk buttons:

```xml
<!-- Remove Start Session button. Replace with: -->
<button name="action_mark_all_present" string="All Present"
        type="object" class="btn-success"
        attrs="{'invisible': [('state', '=', 'submitted')]}"/>
<button name="action_mark_all_absent" string="All Absent"
        type="object" class="btn-warning"
        attrs="{'invisible': [('state', '=', 'submitted')]}"/>
<button name="action_mark_all_late" string="All Late"
        type="object" class="btn-info"
        attrs="{'invisible': [('state', '=', 'submitted')]}"/>
```

- [ ] **Step 4: Commit**

```bash
git add edu_attendance/
git commit -m "feat(edu_attendance): auto-start on edit + bulk status buttons

Removes explicit Start Session click. Sheet auto-starts when teacher
marks any student. Adds All Present/Absent/Late bulk buttons."
```

---

### Task 9: Assessment state collapse and inline marks

**Files:**
- Modify: `edu_assessment/models/edu_continuous_assessment_record.py`
- Modify: `edu_assessment/views/edu_continuous_assessment_record_views.xml`

- [ ] **Step 1: Collapse states from 3 to 2**

In `edu_continuous_assessment_record.py`, update state field (~line 190):

```python
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
```

Remove `action_lock` method. Update `action_confirm` to also lock:

```python
    def action_confirm(self):
        """Confirm and lock the assessment record."""
        draft = self.filtered(lambda r: r.state == 'draft')
        if not draft:
            raise UserError(_("Only draft records can be confirmed."))
        draft.write({'state': 'confirmed'})
```

Update `action_reset_draft` to check for `confirmed`:

```python
    def action_reset_draft(self):
        """Admin: reset confirmed records to draft."""
        confirmed = self.filtered(lambda r: r.state == 'confirmed')
        if not confirmed:
            raise UserError(_("Only confirmed records can be reset."))
        confirmed.write({'state': 'draft'})
```

Update `write` to use `confirmed` instead of `locked` for field protection.

- [ ] **Step 2: Add bulk confirm action**

```python
    def action_bulk_confirm(self):
        """Confirm all selected draft records."""
        draft = self.filtered(lambda r: r.state == 'draft')
        if draft:
            draft.write({'state': 'confirmed'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Confirmed'),
                'message': _('%s records confirmed.', len(draft)),
                'type': 'success',
            },
        }
```

- [ ] **Step 3: Update views for inline marks and 2-state flow**

In `edu_continuous_assessment_record_views.xml`:

Make `marks_obtained` editable in list view (~line 83):

```xml
<field name="marks_obtained" sum="Total Marks" optional="show"/>
```

The list is already `editable="bottom"`, so this should work.

Replace `action_lock` button with nothing (confirm does both):

```xml
<!-- Remove action_lock button. Only keep: -->
<button name="action_confirm" string="Confirm" type="object"
        attrs="{'invisible': [('state', '!=', 'draft')]}"
        class="btn-link text-success"/>
```

Add bulk confirm button to the list view header (server action binding):

```xml
<record id="action_edu_assessment_bulk_confirm" model="ir.actions.server">
    <field name="name">Confirm Selected</field>
    <field name="model_id" ref="edu_assessment.model_edu_continuous_assessment_record"/>
    <field name="binding_model_id" ref="edu_assessment.model_edu_continuous_assessment_record"/>
    <field name="binding_view_types">list</field>
    <field name="state">code</field>
    <field name="code">records.action_bulk_confirm()</field>
</record>
```

Update statusbar:

```xml
<field name="state" widget="statusbar" statusbar_visible="draft,confirmed"/>
```

- [ ] **Step 4: Commit**

```bash
git add edu_assessment/
git commit -m "feat(edu_assessment): collapse states to 2, add inline marks and bulk confirm

States: draft → confirmed (merged confirm + lock). Marks editable
inline on list view. Bulk confirm via list selection."
```

---

### Task 10: Academic progression — staged close before promotion

**Files:**
- Modify: `edu_academic_progression/wizard/edu_batch_promotion_wizard.py`

- [ ] **Step 1: Add open records summary to wizard**

Replace the hard block in `_check_open_records_before_archive` (~line 135) with a summary + auto-close approach:

```python
    open_attendance_count = fields.Integer(
        compute='_compute_open_records',
    )
    open_assessment_count = fields.Integer(
        compute='_compute_open_records',
    )
    open_exam_count = fields.Integer(
        compute='_compute_open_records',
    )
    has_open_records = fields.Boolean(
        compute='_compute_open_records',
    )
    open_records_closed = fields.Boolean(default=False)
    admin_override = fields.Boolean(
        string='Override: Promote Without Closing',
        default=False,
    )

    @api.depends('batch_id')
    def _compute_open_records(self):
        for wiz in self:
            if not wiz.batch_id:
                wiz.open_attendance_count = 0
                wiz.open_assessment_count = 0
                wiz.open_exam_count = 0
                wiz.has_open_records = False
                continue
            classrooms = self.env['edu.classroom'].search([
                ('batch_id', '=', wiz.batch_id.id),
                ('active', '=', True),
            ])
            if not classrooms:
                wiz.open_attendance_count = 0
                wiz.open_assessment_count = 0
                wiz.open_exam_count = 0
                wiz.has_open_records = False
                continue

            wiz.open_attendance_count = self.env['edu.attendance.sheet'].search_count([
                ('classroom_id', 'in', classrooms.ids),
                ('state', '!=', 'submitted'),
            ])
            wiz.open_assessment_count = self.env['edu.continuous.assessment.record'].search_count([
                ('classroom_id', 'in', classrooms.ids),
                ('state', '=', 'draft'),
            ])
            wiz.open_exam_count = self.env['edu.exam.paper'].search_count([
                ('classroom_id', 'in', classrooms.ids),
                ('state', 'not in', ('published', 'closed')),
            ])
            wiz.has_open_records = bool(
                wiz.open_attendance_count
                or wiz.open_assessment_count
                or wiz.open_exam_count
            )

    def action_auto_close_open_records(self):
        """Bulk-close all open attendance sheets and assessment records."""
        self.ensure_one()
        classrooms = self.env['edu.classroom'].search([
            ('batch_id', '=', self.batch_id.id),
            ('active', '=', True),
        ])

        # Auto-submit open attendance sheets
        open_sheets = self.env['edu.attendance.sheet'].search([
            ('classroom_id', 'in', classrooms.ids),
            ('state', '!=', 'submitted'),
        ])
        for sheet in open_sheets:
            if sheet.state == 'draft':
                sheet.action_start()
            if sheet.line_ids:
                sheet.action_submit()

        # Auto-confirm draft assessments
        draft_assessments = self.env['edu.continuous.assessment.record'].search([
            ('classroom_id', 'in', classrooms.ids),
            ('state', '=', 'draft'),
        ])
        if draft_assessments:
            draft_assessments.action_confirm()

        self.open_records_closed = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Records Closed'),
                'message': _('Closed %s attendance sheets and %s assessment records.',
                             len(open_sheets), len(draft_assessments)),
                'type': 'success',
                'sticky': False,
            },
        }
```

Update `action_promote` to check:

```python
    def action_promote(self):
        self.ensure_one()
        self._validate_promotion_inputs()

        if self.has_open_records and not self.open_records_closed and not self.admin_override:
            raise UserError(_(
                "Open records exist. Close them first or enable the override."
            ))

        # ... rest of existing promotion logic
```

- [ ] **Step 2: Update promotion wizard view**

Add open records summary and auto-close button to the wizard form:

```xml
<group attrs="{'invisible': [('has_open_records', '=', False)]}">
    <div class="alert alert-warning" role="alert">
        <h4>Open Records Found</h4>
        <ul>
            <li attrs="{'invisible': [('open_attendance_count', '=', 0)]}">
                <field name="open_attendance_count" class="oe_inline"/> attendance sheets
            </li>
            <li attrs="{'invisible': [('open_assessment_count', '=', 0)]}">
                <field name="open_assessment_count" class="oe_inline"/> assessment records
            </li>
            <li attrs="{'invisible': [('open_exam_count', '=', 0)]}">
                <field name="open_exam_count" class="oe_inline"/> exam papers
            </li>
        </ul>
        <button name="action_auto_close_open_records"
                string="Auto-Close All Open Records"
                type="object" class="btn-warning"
                attrs="{'invisible': [('open_records_closed', '=', True)]}"/>
        <field name="admin_override" groups="edu_academic_progression.group_education_admin"/>
    </div>
</group>
```

- [ ] **Step 3: Commit**

```bash
git add edu_academic_progression/
git commit -m "feat(edu_academic_progression): staged close before promotion

Shows open record counts. Auto-close button submits attendance and confirms
assessments. Admin override to promote without closing."
```

---

### Task 11: Section assignment — single step + toggle simplification

**Files:**
- Modify: `edu_academic_progression/wizard/edu_section_assignment_wizard.py`
- Modify: `edu_academic_progression/views/edu_section_assignment_wizard_views.xml`

- [ ] **Step 1: Replace two booleans with single selection**

In `edu_section_assignment_wizard.py`, replace `clear_existing_section` and `only_unassigned_students` (~lines 108-122) with:

```python
    assignment_scope = fields.Selection(
        [
            ('unassigned_only', 'Unassigned Students Only'),
            ('all_students', 'All Students (Reassign)'),
        ],
        string='Assignment Scope',
        default='unassigned_only',
        required=True,
    )
```

Update `_get_eligible_histories` to use `assignment_scope`:

```python
    def _get_eligible_histories(self):
        domain = [
            ('batch_id', '=', self.batch_id.id),
            ('program_term_id', '=', self.program_term_id.id),
            ('state', '=', 'active'),
        ]
        if self.assignment_scope == 'unassigned_only':
            domain.append(('section_id', '=', False))
        return self.env['edu.student.progression.history'].search(domain)
```

Remove `_onchange_only_unassigned` and `_onchange_clear_existing`.

- [ ] **Step 2: Merge config + preview into single step**

Remove `wizard_state` field. Make `line_ids` always visible. Use `@api.onchange` on config fields to auto-regenerate preview:

```python
    @api.onchange('batch_id', 'program_term_id', 'section_ids',
                  'assignment_method', 'sort_order', 'assignment_scope',
                  'respect_capacity')
    def _onchange_regenerate_preview(self):
        """Auto-regenerate preview when any config field changes."""
        if not (self.batch_id and self.program_term_id and self.section_ids):
            self.line_ids = [(5, 0, 0)]
            return

        try:
            self._validate_configuration()
        except UserError:
            self.line_ids = [(5, 0, 0)]
            return

        histories = self._get_eligible_histories()
        sorted_histories = self._sort_histories(histories)
        sections = self.section_ids.sorted('name')
        assignments = self._distribute_students(sorted_histories, sections)

        lines = []
        for i, (history, section) in enumerate(assignments):
            lines.append((0, 0, {
                'student_id': history.student_id.id,
                'enrollment_id': history.enrollment_id.id,
                'progression_history_id': history.id,
                'old_section_id': history.section_id.id,
                'new_section_id': section.id,
                'sequence_no': i + 1,
            }))
        self.line_ids = [(5, 0, 0)] + lines
```

Replace `action_generate_preview` and `action_back_to_config` with just `action_apply`:

```python
    def action_apply(self):
        """Apply section assignments directly."""
        self.ensure_one()
        self._validate_configuration()
        if not self.line_ids:
            raise UserError(_("No students to assign."))
        # ... existing apply logic from current action_apply
```

- [ ] **Step 3: Update wizard view — single form**

```xml
<form>
    <group>
        <group string="Configuration">
            <field name="batch_id"/>
            <field name="program_term_id"/>
            <field name="section_ids" widget="many2many_tags"/>
            <field name="assignment_method"/>
            <field name="sort_order"/>
            <field name="assignment_scope" widget="radio"/>
            <field name="respect_capacity"/>
        </group>
        <group string="Summary">
            <field name="student_count"/>
            <field name="reassignment_count"
                   attrs="{'invisible': [('assignment_scope', '=', 'unassigned_only')]}"/>
        </group>
    </group>
    <field name="line_ids">
        <list editable="bottom">
            <field name="sequence_no" readonly="1"/>
            <field name="student_id" readonly="1"/>
            <field name="old_section_id" readonly="1"/>
            <field name="new_section_id"/>
            <field name="is_reassignment" invisible="1"/>
            <field name="has_dependent_records" invisible="1"/>
        </list>
    </field>
    <footer>
        <button name="action_apply" string="Apply Assignment"
                type="object" class="btn-primary"/>
        <button string="Cancel" special="cancel"/>
    </footer>
</form>
```

- [ ] **Step 4: Commit**

```bash
git add edu_academic_progression/wizard/edu_section_assignment_wizard.py \
        edu_academic_progression/views/edu_section_assignment_wizard_views.xml
git commit -m "feat(edu_academic_progression): single-step section assignment

Merged config + preview into one form. Live preview on config change.
Replaced two confusing booleans with single assignment_scope selection."
```

---

### Task 12: Classroom generation — success notification instead of error

**Files:**
- Modify: `edu_classroom/models/edu_batch.py`

- [ ] **Step 1: Update action_generate_classrooms_wizard**

In `edu_batch.py`, find the part where it raises `UserError` when all classrooms exist (~line 110-115 area). Replace with:

```python
        if created_count == 0:
            # All classrooms already exist — show success instead of error
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('All Up to Date'),
                    'message': _('All %s classrooms already exist for this batch.', skipped_count),
                    'type': 'info',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'name': _('Classrooms'),
                        'res_model': 'edu.classroom',
                        'view_mode': 'list,form',
                        'domain': [('batch_id', '=', self.id)],
                    },
                },
            }
```

- [ ] **Step 2: Commit**

```bash
git add edu_classroom/models/edu_batch.py
git commit -m "fix(edu_classroom): show success notification instead of error when all classrooms exist"
```

---

## Phase 5: Data Migration

### Task 13: Write state migration for existing records

**Files:**
- Create: `edu_admission/migrations/19.0.2.0.0/pre-migrate.py`
- Create: `edu_enrollment/migrations/19.0.2.0.0/pre-migrate.py`
- Create: `edu_pre_admission_crm/migrations/19.0.2.0.0/pre-migrate.py`
- Create: `edu_assessment/migrations/19.0.2.0.0/pre-migrate.py`
- Update: `edu_admission/__manifest__.py` — bump version to 19.0.2.0.0
- Update: `edu_enrollment/__manifest__.py` — bump version
- Update: `edu_pre_admission_crm/__manifest__.py` — bump version
- Update: `edu_assessment/__manifest__.py` — bump version

- [ ] **Step 1: Admission application state migration**

```python
# edu_admission/migrations/19.0.2.0.0/pre-migrate.py
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating admission application states...")

    # Map old states to new states
    cr.execute("""
        UPDATE edu_admission_application SET state = 'under_review'
        WHERE state IN ('submitted', 'scholarship_review');
    """)
    cr.execute("""
        UPDATE edu_admission_application SET state = 'approved'
        WHERE state IN ('offered', 'offer_accepted', 'ready_for_enrollment');
    """)
    cr.execute("""
        UPDATE edu_admission_application SET state = 'rejected'
        WHERE state IN ('offer_rejected', 'cancelled');
    """)

    _logger.info("Admission application state migration complete.")
```

- [ ] **Step 2: Enrollment state migration**

```python
# edu_enrollment/migrations/19.0.2.0.0/pre-migrate.py
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating enrollment states...")

    cr.execute("""
        UPDATE edu_enrollment SET state = 'active'
        WHERE state = 'confirmed';
    """)

    _logger.info("Enrollment state migration complete.")
```

- [ ] **Step 3: CRM status migration**

```python
# edu_pre_admission_crm/migrations/19.0.2.0.0/pre-migrate.py
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating CRM lead education statuses...")

    cr.execute("""
        UPDATE crm_lead SET lead_education_status = 'qualified'
        WHERE lead_education_status IN ('prospect', 'ready_for_application');
    """)

    _logger.info("CRM lead status migration complete.")
```

- [ ] **Step 4: Assessment state migration**

```python
# edu_assessment/migrations/19.0.2.0.0/pre-migrate.py
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating assessment states...")

    cr.execute("""
        UPDATE edu_continuous_assessment_record SET state = 'confirmed'
        WHERE state = 'locked';
    """)

    _logger.info("Assessment state migration complete.")
```

- [ ] **Step 5: Bump all module versions**

Update `__manifest__.py` in all 4 modules: change `version` from `19.0.1.0.0` to `19.0.2.0.0`.

- [ ] **Step 6: Add default values for new register fields**

```python
# Add to edu_admission/migrations/19.0.2.0.0/pre-migrate.py

    # Add new columns with defaults before ORM loads
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS flow_preset VARCHAR DEFAULT 'standard';
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_academic_review BOOLEAN DEFAULT TRUE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_scholarship_review BOOLEAN DEFAULT FALSE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_offer_letter BOOLEAN DEFAULT TRUE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_odoo_sign BOOLEAN DEFAULT FALSE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_payment_confirmation BOOLEAN DEFAULT TRUE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_application
        ADD COLUMN IF NOT EXISTS payment_received BOOLEAN DEFAULT FALSE;
    """)
```

- [ ] **Step 7: Commit**

```bash
git add edu_admission/migrations/ edu_enrollment/migrations/ \
        edu_pre_admission_crm/migrations/ edu_assessment/migrations/ \
        edu_admission/__manifest__.py edu_enrollment/__manifest__.py \
        edu_pre_admission_crm/__manifest__.py edu_assessment/__manifest__.py
git commit -m "chore: add data migration scripts for state collapse

Maps old states to new states via SQL pre-migration.
Bumps module versions to 19.0.2.0.0 to trigger migration."
```

---

## Phase 6: Cross-Module Fixes

### Task 14: Update enrollment module's action_enroll override

**Files:**
- Modify: `edu_enrollment/models/edu_admission_application.py`

- [ ] **Step 1: Update the action_enroll override**

The `edu_enrollment` module overrides `action_enroll` on `edu.admission.application` to create enrollment records. Update it to work with the new state machine — it should override `_create_enrollment_on_enroll` instead:

```python
    def _create_enrollment_on_enroll(self):
        """Create enrollment record when application is enrolled."""
        for app in self:
            # Check for duplicate enrollments
            existing = self.env['edu.enrollment'].search([
                ('application_id', '=', app.id),
                ('state', '!=', 'cancelled'),
            ], limit=1)
            if existing:
                continue

            vals = self.env['edu.enrollment']._prepare_vals_from_application(app)
            enrollment = self.env['edu.enrollment'].create(vals)

            app.message_post(body=_(
                "Enrollment <b>%s</b> created.",
                enrollment.enrollment_no,
            ))
```

- [ ] **Step 2: Update smart buttons for enrollment/student visibility**

Ensure `action_view_enrollment` and `action_view_student` still work with the new states.

- [ ] **Step 3: Commit**

```bash
git add edu_enrollment/
git commit -m "refactor(edu_enrollment): update enrollment handoff for collapsed state machine

Overrides _create_enrollment_on_enroll instead of action_enroll."
```

---

### Task 15: Update register smart buttons for new states

**Files:**
- Modify: `edu_admission/models/edu_admission_register.py`
- Modify: `edu_admission/views/edu_admission_register_views.xml`

- [ ] **Step 1: Update computed state counts**

In `edu_admission_register.py`, update `_compute_application_state_counts` (~line 196) to count by new states:

```python
    under_review_count = fields.Integer(compute='_compute_application_state_counts')
    approved_count = fields.Integer(compute='_compute_application_state_counts')

    @api.depends('application_ids.state')
    def _compute_application_state_counts(self):
        data = self.env['edu.admission.application']._read_group(
            [('admission_register_id', 'in', self.ids)],
            ['admission_register_id', 'state'],
            ['__count'],
        )
        mapped = {}
        for register, state, count in data:
            mapped.setdefault(register.id, {})[state] = count
        for reg in self:
            counts = mapped.get(reg.id, {})
            reg.under_review_count = counts.get('under_review', 0)
            reg.approved_count = counts.get('approved', 0)
            reg.enrolled_count = counts.get('enrolled', 0)
            reg.cancelled_count = counts.get('rejected', 0)
```

Remove `submitted_count` and `offered_count` fields (no longer applicable).

- [ ] **Step 2: Update register view smart buttons**

Replace `submitted`, `offered` buttons with `under_review`, `approved`:

```xml
<button name="action_view_under_review" type="object"
        class="oe_stat_button" icon="fa-search"
        attrs="{'invisible': [('under_review_count', '=', 0)]}">
    <field name="under_review_count" widget="statinfo" string="Under Review"/>
</button>
<button name="action_view_approved" type="object"
        class="oe_stat_button" icon="fa-check"
        attrs="{'invisible': [('approved_count', '=', 0)]}">
    <field name="approved_count" widget="statinfo" string="Approved"/>
</button>
```

- [ ] **Step 3: Commit**

```bash
git add edu_admission/
git commit -m "refactor(edu_admission): update register smart buttons for new states"
```

---

## Execution Order

Tasks can be parallelized within phases:

1. **Phase 1 (sequential):** Task 1 → Task 2 → Task 3 → Task 4
2. **Phase 2 (independent):** Task 5
3. **Phase 3 (sequential):** Task 6 → Task 7
4. **Phase 4 (all independent, can parallelize):** Tasks 8, 9, 10, 11, 12
5. **Phase 5 (after all model changes):** Task 13
6. **Phase 6 (after phases 1-2):** Tasks 14, 15

Total: 15 tasks across 6 phases.
