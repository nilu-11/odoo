from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EduBatchPromotionWizard(models.TransientModel):
    """Controlled wizard for promoting an entire batch to the next progression.

    Promotion sequence (all inside one transaction):
      1. Validate all inputs.
      2. Collect active progression histories for the batch.
      3. Close each old record (state=promoted, end_date=effective_date).
      4. Create new progression histories (state=active) for every student.
      5. Link promoted_to_id ↔ promoted_from_id between old and new records.
      6. Advance batch.current_program_term_id to the next term.
      7. Update student.current_program_term_id (and section if clearing).
      8. Post a chatter note on the batch.
    """
    _name = 'edu.batch.promotion.wizard'
    _description = 'Batch Promotion Wizard'

    # ── Batch & current state (read-only display) ─────────────────────────────

    batch_id = fields.Many2one(
        'edu.batch', string='Batch',
        required=True, ondelete='cascade',
        domain=[('state', '=', 'active')],
        default=lambda self: self.env.context.get('default_batch_id'),
    )
    current_program_term_id = fields.Many2one(
        'edu.program.term',
        related='batch_id.current_program_term_id',
        string='Current Progression', readonly=True,
    )
    batch_program_id = fields.Many2one(
        'edu.program',
        related='batch_id.program_id',
        string='Program', readonly=True,
    )
    current_progression_no = fields.Integer(
        related='batch_id.current_program_term_id.progression_no',
        string='Current Progression No', readonly=True,
    )

    # ── Target progression ────────────────────────────────────────────────────

    next_program_term_id = fields.Many2one(
        'edu.program.term', string='Promote To',
        required=True,
        domain="[('program_id', '=', batch_program_id), "
               " ('progression_no', '>',  current_progression_no)]",
    )

    # ── Promotion context ─────────────────────────────────────────────────────

    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        default=fields.Date.today,
    )
    new_academic_year_id = fields.Many2one(
        'edu.academic.year',
        string='New Academic Year',
        help='Academic year for the new progression records. '
             'If left blank, the currently open academic year is used; '
             'if none is open, the existing year is carried forward.',
    )
    section_mode = fields.Selection([
        ('keep_same_section', 'Keep Current Section'),
        ('clear_section',     'Clear Section (Assign Later)'),
    ], string='Section Assignment',
       required=True, default='keep_same_section',
    )

    # ── Preview ───────────────────────────────────────────────────────────────

    active_progression_count = fields.Integer(
        compute='_compute_active_progression_count',
        string='Students to Promote',
    )

    @api.depends('batch_id')
    def _compute_active_progression_count(self):
        ProgressionHistory = self.env['edu.student.progression.history']
        for wiz in self:
            if wiz.batch_id:
                wiz.active_progression_count = ProgressionHistory.search_count([
                    ('batch_id', '=', wiz.batch_id.id),
                    ('state', '=', 'active'),
                ])
            else:
                wiz.active_progression_count = 0

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        """Clear incompatible next term when the batch changes."""
        self.next_program_term_id = False

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_promotion_inputs(self):
        """Raise UserError / ValidationError if the promotion cannot proceed."""
        if not self.current_program_term_id:
            raise UserError(_(
                'Batch "%s" has no current progression configured. '
                'Set "Current Progression" on the batch before running a promotion.'
            ) % self.batch_id.name)

        if self.next_program_term_id == self.current_program_term_id:
            raise UserError(_('Cannot promote to the same progression term.'))

        if self.next_program_term_id.progression_no <= self.current_program_term_id.progression_no:
            raise UserError(_(
                'Next progression (%s, no. %d) must be numerically greater than '
                'current progression (%s, no. %d).'
            ) % (
                self.next_program_term_id.progression_label,
                self.next_program_term_id.progression_no,
                self.current_program_term_id.progression_label,
                self.current_program_term_id.progression_no,
            ))

        if self.next_program_term_id.program_id != self.batch_id.program_id:
            raise ValidationError(_(
                'Next progression term "%s" does not belong to program "%s".'
            ) % (self.next_program_term_id.name, self.batch_id.program_id.name))

        if not self.active_progression_count:
            raise UserError(_(
                'No active progression records found for batch "%s". '
                'There are no students to promote.'
            ) % self.batch_id.name)

    def _resolve_academic_year(self, fallback_year_id):
        """Determine the academic year to use on new progression records.

        Priority: explicit wizard input → currently open year → fallback (existing).
        """
        if self.new_academic_year_id:
            return self.new_academic_year_id
        open_year = self.env['edu.academic.year'].search([
            ('state', '=', 'open'),
            ('company_id', '=', self.batch_id.company_id.id),
        ], limit=1)
        return open_year or self.env['edu.academic.year'].browse(fallback_year_id)

    # ── Main action ───────────────────────────────────────────────────────────

    def action_promote(self):
        """Execute the batch promotion (all steps in one transaction)."""
        self.ensure_one()
        self._validate_promotion_inputs()

        ProgressionHistory = self.env['edu.student.progression.history']

        # ── 1. Fetch active progression records for this batch ────────────────
        active_histories = ProgressionHistory.search([
            ('batch_id', '=', self.batch_id.id),
            ('state', '=', 'active'),
        ])
        if not active_histories:
            raise UserError(_(
                'No active progression records found for batch "%s".'
            ) % self.batch_id.name)

        # ── 2. Close all active records first (prevents constraint collision) ─
        for history in active_histories:
            history._close_for_promotion(self.effective_date)

        # ── 3. Build and create new progression histories in bulk ─────────────
        new_vals_list = []
        for old in active_histories:
            academic_year = self._resolve_academic_year(old.academic_year_id.id)
            section_id = (
                old.section_id.id
                if self.section_mode == 'keep_same_section' and old.section_id
                else False
            )
            new_vals_list.append({
                'student_id':      old.student_id.id,
                'enrollment_id':   old.enrollment_id.id,
                'batch_id':        self.batch_id.id,
                'program_id':      self.batch_id.program_id.id,
                'academic_year_id': academic_year.id,
                'program_term_id': self.next_program_term_id.id,
                'section_id':      section_id,
                'start_date':      self.effective_date,
                'state':           'active',
                'promoted_from_id': old.id,
            })
        new_histories = ProgressionHistory.create(new_vals_list)

        # ── 4. Cross-link the promotion chain ─────────────────────────────────
        for old, new in zip(active_histories, new_histories):
            old.promoted_to_id = new.id

        # ── 5. Advance batch current progression ──────────────────────────────
        self.batch_id.current_program_term_id = self.next_program_term_id

        # ── 6. Update each student's live academic placement ──────────────────
        for new in new_histories:
            student_vals = {'current_program_term_id': self.next_program_term_id.id}
            if self.section_mode == 'clear_section':
                student_vals['section_id'] = False
            new.student_id.write(student_vals)

        # ── 7. Chatter note on the batch ──────────────────────────────────────
        section_label = dict(self._fields['section_mode'].selection).get(
            self.section_mode, self.section_mode,
        )
        self.batch_id.message_post(
            body=_(
                '<b>Batch Promoted</b><br/>'
                'From: <b>%s</b> &rarr; To: <b>%s</b><br/>'
                'Effective date: %s &nbsp;|&nbsp; Students promoted: <b>%d</b><br/>'
                'Section: %s%s'
            ) % (
                self.current_program_term_id.name,
                self.next_program_term_id.name,
                self.effective_date,
                len(new_histories),
                section_label,
                (' &nbsp;|&nbsp; New academic year: <b>%s</b>'
                 % self.new_academic_year_id.name)
                if self.new_academic_year_id else '',
            ),
            subtype_xmlid='mail.mt_note',
        )

        # ── 8. Success notification ───────────────────────────────────────────
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Promotion Successful'),
                'message': _(
                    '%d student(s) promoted from %s to %s.'
                ) % (
                    len(new_histories),
                    self.current_program_term_id.progression_label,
                    self.next_program_term_id.progression_label,
                ),
                'type': 'success',
                'sticky': False,
            },
        }
