import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EduProgressionBackfillWizard(models.TransientModel):
    """Wizard to create missing progression history records for enrolled students.

    Use this when students were created before the progression module was installed,
    or when progression history wasn't auto-created for some reason.
    """

    _name = 'edu.progression.backfill.wizard'
    _description = 'Create Missing Progression Histories'

    batch_id = fields.Many2one(
        'edu.batch', string='Batch',
        required=True,
        domain=[('state', '=', 'active')],
        help='Batch for which to backfill progression histories.',
    )
    program_term_id = fields.Many2one(
        'edu.program.term', string='Program Term',
        required=True,
        domain="[('program_id', '=', batch_program_id)]",
        help='Program term for the progression records.',
    )
    batch_program_id = fields.Many2one(
        'edu.program',
        related='batch_id.program_id',
        readonly=True, store=False,
    )

    # Results
    eligible_count = fields.Integer(
        string='Eligible Enrollments',
        compute='_compute_eligible_count',
    )
    existing_count = fields.Integer(
        string='Already Have Progression',
        compute='_compute_eligible_count',
    )
    to_create_count = fields.Integer(
        string='Will Create',
        compute='_compute_eligible_count',
    )

    @api.depends('batch_id', 'program_term_id')
    def _compute_eligible_count(self):
        for wiz in self:
            if not wiz.batch_id or not wiz.program_term_id:
                wiz.eligible_count = 0
                wiz.existing_count = 0
                wiz.to_create_count = 0
                continue

            # Find all enrollments for this batch
            enrollments = self.env['edu.enrollment'].search([
                ('batch_id', '=', wiz.batch_id.id),
                ('state', 'in', ['active', 'completed']),
            ])
            wiz.eligible_count = len(enrollments)

            # Find students who already have progression for this term
            histories = self.env['edu.student.progression.history'].search([
                ('batch_id', '=', wiz.batch_id.id),
                ('program_term_id', '=', wiz.program_term_id.id),
            ])
            existing_student_ids = set(histories.mapped('student_id').ids)
            wiz.existing_count = len(existing_student_ids)
            wiz.to_create_count = wiz.eligible_count - wiz.existing_count

    def action_backfill(self):
        """Create missing progression histories for all eligible students."""
        self.ensure_one()

        if not self.batch_id or not self.program_term_id:
            raise UserError(_('Select batch and program term.'))

        # Find all enrollments for this batch
        enrollments = self.env['edu.enrollment'].search([
            ('batch_id', '=', self.batch_id.id),
            ('state', 'in', ['active', 'completed']),
        ])

        if not enrollments:
            raise UserError(_(
                'No active or completed enrollments found for batch "%s".'
            ) % self.batch_id.name)

        # Find students who already have progression for this term
        histories = self.env['edu.student.progression.history'].search([
            ('batch_id', '=', self.batch_id.id),
            ('program_term_id', '=', self.program_term_id.id),
        ])
        existing_student_ids = set(histories.mapped('student_id').ids)

        # Prepare vals for new progression records
        vals_list = []
        for enrollment in enrollments:
            student = enrollment.student_id
            if not student:
                _logger.warning(
                    'Enrollment %s has no student record (skipping)',
                    enrollment.enrollment_no
                )
                continue

            if student.id in existing_student_ids:
                continue  # Already has progression for this term

            vals_list.append({
                'student_id': student.id,
                'enrollment_id': enrollment.id,
                'batch_id': self.batch_id.id,
                'program_id': self.batch_id.program_id.id,
                'academic_year_id': self.batch_id.academic_year_id.id,
                'program_term_id': self.program_term_id.id,
                'section_id': False,
                'start_date': enrollment.enrollment_date or fields.Date.today(),
                'state': 'active',
            })

        if not vals_list:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to Create'),
                    'message': _('All students already have progression records for this term.'),
                    'type': 'info',
                    'sticky': False,
                },
            }

        # Create all at once
        created = self.env['edu.student.progression.history'].create(vals_list)

        # Audit message on the batch
        self.batch_id.message_post(
            body=_(
                '<b>Progression History Backfill</b><br/>'
                'Created <b>%d</b> progression record(s) for term <b>%s</b>.'
            ) % (len(created), self.program_term_id.name),
            subtype_xmlid='mail.mt_note',
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Backfill Complete'),
                'message': _(
                    'Created %d progression history record(s) for %d student(s).'
                ) % (len(created), len(created)),
                'type': 'success',
                'sticky': False,
            },
        }
