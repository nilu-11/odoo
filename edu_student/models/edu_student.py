from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduStudent(models.Model):
    """
    Official institutional student master record.

    Created exclusively from a valid, active edu.enrollment record.
    Serves as the long‑term anchor for:
      - academic placement and progression
      - future billing, attendance, exam, library, hostel, transport, and portal modules

    Identity design:
      - partner_id       → res.partner         (contact / portal identity)
      - applicant_profile_id → edu.applicant.profile (demographics, guardians, academic history)
      - current_enrollment_id → edu.enrollment  (the enrollment that activated this student)

    Identifier design:
      - student_no   → globally unique institutional identifier  (STU/2026/00001)
      - roll_number  → academic identifier scoped per batch       (2026-BCA-0001)

    Field provenance:
      - partner_id, applicant_profile_id   → direct relational links (never change)
      - program_id, batch_id, academic_year_id, current_program_term_id
            → **snapshot** copies from enrollment at creation; updated as
              the student progresses (promotion, batch transfer, etc.)
      - section_id                          → optional, assigned after creation
      - department_id                       → stored related from program_id
      - admission_date                      → snapshot of enrollment.enrollment_date
    """

    _name = 'edu.student'
    _description = 'Student'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'student_no desc, id desc'
    _rec_name = 'display_name'

    # ─── Locking configuration ───
    _IDENTITY_FIELDS = frozenset({
        'partner_id', 'applicant_profile_id', 'student_no',
    })

    # ═══════════════════════════════════════════════════════
    #  Identity / Linkage
    # ═══════════════════════════════════════════════════════
    student_no = fields.Char(
        string='Student No.', required=True, readonly=True,
        copy=False, index=True, tracking=True,
        help='Globally unique institutional student identifier. Auto‑generated.',
    )
    roll_number = fields.Char(
        string='Roll Number', required=True, readonly=True,
        copy=False, index=True, tracking=True,
        help='Academic roll number tied to batch context. Format: YEAR‑PROGCODE‑SEQ.',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related='program_id.company_id', string='Company',
        store=True, index=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Contact', required=True,
        ondelete='restrict', tracking=True, index=True,
        help='The res.partner identity — used for portal, communication, and invoicing.',
    )
    applicant_profile_id = fields.Many2one(
        'edu.applicant.profile', string='Applicant Profile', required=True,
        ondelete='restrict', tracking=True, index=True,
        help='Link to the full applicant profile (demographics, guardians, academic history).',
    )

    # ── Enrollment linkage ──
    current_enrollment_id = fields.Many2one(
        'edu.enrollment', string='Current Enrollment', required=True,
        ondelete='restrict', tracking=True, index=True,
        help='The enrollment record that activated (or currently governs) this student.',
    )
    enrollment_ids = fields.One2many(
        'edu.enrollment', 'student_id', string='Enrollment History',
        help='All enrollment records linked to this student (current and historical).',
    )

    # ── Related helpers ──
    lead_id = fields.Many2one(
        related='current_enrollment_id.crm_lead_id', string='CRM Lead',
        store=True, readonly=True,
    )
    image_1920 = fields.Image(
        related='applicant_profile_id.image_1920',
        string='Photo', readonly=False,
    )
    image_128 = fields.Image(
        related='applicant_profile_id.image_128',
        string='Photo (Thumbnail)', readonly=True,
    )

    # ═══════════════════════════════════════════════════════
    #  Academic Placement (current status — snapshotted from enrollment,
    #  then updated on promotion / transfer)
    # ═══════════════════════════════════════════════════════
    program_id = fields.Many2one(
        'edu.program', string='Program', required=True,
        ondelete='restrict', tracking=True, index=True,
    )
    batch_id = fields.Many2one(
        'edu.batch', string='Batch', required=True,
        ondelete='restrict', tracking=True, index=True,
    )
    academic_year_id = fields.Many2one(
        'edu.academic.year', string='Academic Year', required=True,
        ondelete='restrict', tracking=True, index=True,
    )
    current_program_term_id = fields.Many2one(
        'edu.program.term', string='Current Program Term', required=True,
        ondelete='restrict', tracking=True, index=True,
    )
    department_id = fields.Many2one(
        related='program_id.department_id', string='Department',
        store=True, index=True,
    )
    section_id = fields.Many2one(
        'edu.section', string='Section', ondelete='set null',
        tracking=True, index=True,
        domain="[('batch_id', '=', batch_id)]",
        help='Assigned section within the batch (optional, can be set after enrolment).',
    )

    # ═══════════════════════════════════════════════════════
    #  Key Dates
    # ═══════════════════════════════════════════════════════
    admission_date = fields.Date(
        string='Admission Date', required=True, tracking=True,
        help='Date the student was officially admitted (snapshot of enrollment date).',
    )
    current_status_date = fields.Date(
        string='Current Status Since', tracking=True,
        help='Date since the current lifecycle state is effective.',
    )
    graduation_date = fields.Date(string='Graduation Date', tracking=True)
    withdrawal_date = fields.Date(string='Withdrawal Date', tracking=True)
    suspension_date = fields.Date(string='Suspension Date', tracking=True)
    alumni_date = fields.Date(string='Alumni Date', tracking=True)

    # ═══════════════════════════════════════════════════════
    #  Lifecycle
    # ═══════════════════════════════════════════════════════
    state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('on_leave', 'On Leave'),
            ('suspended', 'Suspended'),
            ('withdrawn', 'Withdrawn'),
            ('graduated', 'Graduated'),
            ('alumni', 'Alumni'),
            ('inactive', 'Inactive'),
        ],
        string='Status', default='active', required=True,
        tracking=True, index=True, copy=False,
    )

    # ═══════════════════════════════════════════════════════
    #  Administrative / Notes
    # ═══════════════════════════════════════════════════════
    note = fields.Text(string='Notes')
    internal_note = fields.Html(string='Internal Notes')
    student_created_by = fields.Many2one(
        'res.users', string='Created By', readonly=True, copy=False,
    )
    student_created_on = fields.Datetime(
        string='Created On', readonly=True, copy=False,
    )

    # ═══════════════════════════════════════════════════════
    #  Computed / Helper Fields
    # ═══════════════════════════════════════════════════════
    display_name = fields.Char(
        compute='_compute_display_name', store=True, precompute=True,
    )
    guardian_count = fields.Integer(
        compute='_compute_guardian_count', string='Guardians',
    )
    enrollment_count = fields.Integer(
        compute='_compute_enrollment_count', string='Enrollments',
    )
    has_active_enrollment = fields.Boolean(
        compute='_compute_enrollment_count',
    )
    current_program_term_name = fields.Char(
        related='current_program_term_id.name',
        string='Current Term', readonly=True,
    )
    status_history_count = fields.Integer(
        compute='_compute_status_history_count', string='Status Changes',
    )

    # ═══════════════════════════════════════════════════════
    #  SQL Constraints
    # ═══════════════════════════════════════════════════════
    _sql_constraints = [
        (
            'student_no_unique',
            'UNIQUE(student_no)',
            'Student number must be globally unique.',
        ),
        (
            'roll_number_batch_unique',
            'UNIQUE(roll_number, batch_id)',
            'Roll number must be unique within the batch.',
        ),
        (
            'enrollment_unique',
            'UNIQUE(current_enrollment_id)',
            'A student record already exists for this enrollment.',
        ),
    ]

    # ═══════════════════════════════════════════════════════
    #  CRUD
    # ═══════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Datetime.now()
        uid = self.env.uid
        for vals in vals_list:
            if not vals.get('student_no') or vals['student_no'] == '/':
                vals['student_no'] = self._generate_student_no()
            if not vals.get('roll_number') or vals['roll_number'] == '/':
                vals['roll_number'] = self._generate_roll_number(vals)
            vals.setdefault('student_created_by', uid)
            vals.setdefault('student_created_on', today)
            vals.setdefault('current_status_date', fields.Date.context_today(self))
        records = super().create(vals_list)
        for rec in records:
            rec._post_creation_validation()
        return records

    def write(self, vals):
        # Protect identity fields from casual edits
        identity_change = self._IDENTITY_FIELDS & set(vals.keys())
        if identity_change:
            for rec in self:
                if rec.state not in ('inactive',):
                    raise UserError(
                        'Cannot modify identity fields (%s) on student "%s" '
                        '— only allowed on inactive records or by system.'
                        % (', '.join(identity_change), rec.student_no)
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'inactive':
                raise UserError(
                    f'Cannot delete student "{rec.student_no}" — '
                    'only inactive students may be deleted.'
                )
        return super().unlink()

    # ═══════════════════════════════════════════════════════
    #  Display Name
    # ═══════════════════════════════════════════════════════
    @api.depends('student_no', 'partner_id', 'partner_id.name')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.student_no or '']
            if rec.partner_id:
                parts.append(rec.partner_id.name or '')
            rec.display_name = ' — '.join(filter(None, parts)) or 'New'

    # ═══════════════════════════════════════════════════════
    #  Computed Fields
    # ═══════════════════════════════════════════════════════
    def _compute_guardian_count(self):
        for rec in self:
            profile = rec.applicant_profile_id
            rec.guardian_count = len(profile.guardian_rel_ids) if profile else 0

    @api.depends('enrollment_ids', 'enrollment_ids.state')
    def _compute_enrollment_count(self):
        for rec in self:
            enrollments = rec.enrollment_ids
            rec.enrollment_count = len(enrollments)
            rec.has_active_enrollment = any(
                e.state == 'active' for e in enrollments
            )

    def _compute_status_history_count(self):
        History = self.env['edu.student.status.history']
        data = History._read_group(
            [('student_id', 'in', self.ids)],
            ['student_id'], ['__count'],
        )
        mapped = {student.id: count for student, count in data}
        for rec in self:
            rec.status_history_count = mapped.get(rec.id, 0)

    # ═══════════════════════════════════════════════════════
    #  Identifier Generation
    # ═══════════════════════════════════════════════════════
    def _generate_student_no(self):
        """
        Generate a globally unique institutional student number.
        Format: STU/YYYY/NNNNN  (e.g. STU/2026/00001)
        Uses ir.sequence ``edu.student`` for uniqueness and gap‑free numbering.
        """
        return self.env['ir.sequence'].next_by_code('edu.student') or '/'

    def _generate_roll_number(self, vals):
        """
        Generate an academic roll number scoped to the batch.

        Format: YEAR-PROGCODE-NNNN  (e.g. 2026-BCA-0001)

        Components:
          - YEAR      → academic year start‑year from batch's academic_year_id
          - PROGCODE  → program.code
          - NNNN      → running 4‑digit sequence within the batch (ir.sequence per batch)

        The sequence resets per batch so each batch starts from 0001.
        A new ir.sequence record is created on demand for each batch.
        """
        batch_id = vals.get('batch_id')
        if not batch_id:
            return '/'

        batch = self.env['edu.batch'].browse(batch_id)
        if not batch.exists():
            return '/'

        program = batch.program_id
        academic_year = batch.academic_year_id

        # Derive the year component from academic year start date
        year_str = str(academic_year.date_start.year) if academic_year.date_start else academic_year.name[:4]
        prog_code = program.code or 'PROG'

        # Construct a per‑batch sequence code
        seq_code = f'edu.student.roll.{batch.id}'
        seq = self.env['ir.sequence'].sudo().search(
            [('code', '=', seq_code)], limit=1,
        )
        if not seq:
            seq = self.env['ir.sequence'].sudo().create({
                'name': f'Student Roll — {batch.name}',
                'code': seq_code,
                'padding': 4,
                'number_increment': 1,
                'number_next': 1,
                'company_id': False,
            })
        seq_val = seq.next_by_code(seq_code) or '0001'

        return f'{year_str}-{prog_code}-{seq_val}'

    # ═══════════════════════════════════════════════════════
    #  Creation from Enrollment
    # ═══════════════════════════════════════════════════════
    @api.model
    def _prepare_student_vals_from_enrollment(self, enrollment):
        """
        Build the vals dict for creating an edu.student from an enrollment.

        Snapshotted fields:
          - program_id, batch_id, academic_year_id, current_program_term_id
          - admission_date (from enrollment.enrollment_date)

        Relational links (never change after creation):
          - partner_id, applicant_profile_id, current_enrollment_id
        """
        enrollment.ensure_one()
        return {
            # Identity / linkage
            'partner_id': enrollment.partner_id.id,
            'applicant_profile_id': enrollment.applicant_profile_id.id,
            'current_enrollment_id': enrollment.id,
            # Academic placement (snapshot)
            'program_id': enrollment.program_id.id,
            'batch_id': enrollment.batch_id.id,
            'academic_year_id': enrollment.academic_year_id.id,
            'current_program_term_id': enrollment.current_program_term_id.id,
            # Dates
            'admission_date': enrollment.enrollment_date or fields.Date.context_today(self),
        }

    @api.model
    def action_create_from_enrollment(self, enrollment):
        """
        Main entry point: create a student record from a validated enrollment.

        Pre‑conditions:
          - enrollment must be in 'active' state
          - no existing student for this enrollment
          - all required academic context must be populated

        Returns the created edu.student record or redirects to existing one.
        """
        enrollment.ensure_one()
        self._validate_enrollment_for_student_creation(enrollment)

        vals = self._prepare_student_vals_from_enrollment(enrollment)
        student = self.create(vals)
        return student

    @api.model
    def _validate_enrollment_for_student_creation(self, enrollment):
        """
        Raise UserError if the enrollment is not ready for student creation.
        """
        enrollment.ensure_one()
        blocks = []

        if enrollment.state != 'active':
            blocks.append(
                f'Enrollment "{enrollment.enrollment_no}" is in '
                f'"{enrollment.state}" state — must be "active".'
            )

        if not enrollment.partner_id:
            blocks.append('Enrollment has no linked contact (partner).')
        if not enrollment.applicant_profile_id:
            blocks.append('Enrollment has no linked applicant profile.')
        if not enrollment.program_id:
            blocks.append('Enrollment has no program assigned.')
        if not enrollment.batch_id:
            blocks.append('Enrollment has no batch assigned.')
        if not enrollment.academic_year_id:
            blocks.append('Enrollment has no academic year assigned.')
        if not enrollment.current_program_term_id:
            blocks.append('Enrollment has no current program term assigned.')

        # Check for duplicate: same enrollment
        existing = self.search(
            [('current_enrollment_id', '=', enrollment.id)], limit=1,
        )
        if existing:
            blocks.append(
                f'A student record ({existing.student_no}) already exists '
                f'for enrollment "{enrollment.enrollment_no}".'
            )

        if blocks:
            raise UserError(
                'Cannot create student from enrollment '
                f'"{enrollment.enrollment_no}":\n'
                + '\n'.join(f'  • {b}' for b in blocks)
            )

    # ═══════════════════════════════════════════════════════
    #  Post‑creation Validation
    # ═══════════════════════════════════════════════════════
    def _post_creation_validation(self):
        """Basic integrity check after student creation."""
        self.ensure_one()
        if not self.partner_id:
            raise ValidationError('Student must have a contact (partner_id).')
        if not self.applicant_profile_id:
            raise ValidationError('Student must have an applicant profile.')
        if not self.current_enrollment_id:
            raise ValidationError('Student must have a current enrollment.')
        if self.applicant_profile_id.partner_id != self.partner_id:
            raise ValidationError(
                'Student partner does not match applicant profile partner.'
            )

    # ═══════════════════════════════════════════════════════
    #  Lifecycle Actions
    # ═══════════════════════════════════════════════════════
    _ALLOWED_TRANSITIONS = {
        'active': {'on_leave', 'suspended', 'withdrawn', 'graduated', 'inactive'},
        'on_leave': {'active', 'withdrawn', 'inactive'},
        'suspended': {'active', 'withdrawn', 'inactive'},
        'withdrawn': {'inactive'},
        'graduated': {'alumni', 'inactive'},
        'alumni': {'inactive'},
        'inactive': {'active'},
    }

    def _do_transition(self, new_state, date_field=None, reason=False):
        """
        Generic lifecycle transition with validation, date stamping,
        and history logging.
        """
        today = fields.Date.context_today(self)
        for rec in self:
            allowed = self._ALLOWED_TRANSITIONS.get(rec.state, set())
            if new_state not in allowed:
                raise UserError(
                    f'Cannot transition student "{rec.student_no}" from '
                    f'"{rec.state}" to "{new_state}". '
                    f'Allowed transitions: {", ".join(sorted(allowed)) or "none"}.'
                )
            old_state = rec.state
            vals = {
                'state': new_state,
                'current_status_date': today,
            }
            if date_field:
                vals[date_field] = today
            rec.write(vals)

            # Log to status history
            self.env['edu.student.status.history'].sudo().create({
                'student_id': rec.id,
                'old_state': old_state,
                'new_state': new_state,
                'reason': reason or False,
            })

    def action_set_active(self):
        self._do_transition('active', reason='Reactivated')

    def action_put_on_leave(self):
        self._do_transition('on_leave', reason='Put on leave')

    def action_suspend(self):
        self._do_transition('suspended', date_field='suspension_date', reason='Suspended')

    def action_withdraw(self):
        self._do_transition('withdrawn', date_field='withdrawal_date', reason='Withdrawn')

    def action_graduate(self):
        self._do_transition('graduated', date_field='graduation_date', reason='Graduated')

    def action_mark_alumni(self):
        self._do_transition('alumni', date_field='alumni_date', reason='Marked as alumni')

    def action_deactivate(self):
        self._do_transition('inactive', reason='Deactivated')

    # ═══════════════════════════════════════════════════════
    #  Smart Button Actions
    # ═══════════════════════════════════════════════════════
    def action_view_applicant_profile(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.applicant.profile',
            'res_id': self.applicant_profile_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_guardians(self):
        self.ensure_one()
        name = self.applicant_profile_id.full_name or self.partner_id.name
        return {
            'type': 'ir.actions.act_window',
            'name': f'Guardians — {name}',
            'res_model': 'edu.applicant.guardian.rel',
            'view_mode': 'list,form',
            'domain': [
                ('applicant_profile_id', '=', self.applicant_profile_id.id),
            ],
            'target': 'current',
        }

    def action_view_enrollments(self):
        self.ensure_one()
        enrollments = self.enrollment_ids
        if len(enrollments) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.enrollment',
                'res_id': enrollments[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': f'Enrollments — {self.student_no}',
            'res_model': 'edu.enrollment',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'target': 'current',
        }

    def action_view_current_enrollment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.enrollment',
            'res_id': self.current_enrollment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_status_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Status History — {self.student_no}',
            'res_model': 'edu.student.status.history',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'target': 'current',
        }
