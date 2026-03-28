import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduStudent(models.Model):
    _inherit = 'edu.student'

    # ── Progression History ───────────────────────────────────────────────────

    progression_history_ids = fields.One2many(
        'edu.student.progression.history',
        'student_id',
        string='Progression History',
    )
    progression_history_count = fields.Integer(
        compute='_compute_progression_history_count',
        store=True,
        string='Progressions',
    )

    @api.depends('progression_history_ids')
    def _compute_progression_history_count(self):
        for student in self:
            student.progression_history_count = len(student.progression_history_ids)

    # ── ORM Override ──────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create the initial progression history record on student creation.

        Runs after the student record is committed. The guard condition ensures
        this only fires when a complete enrollment context is present, so direct
        creation (data migration, demo data) without an enrollment is unaffected.
        Any failure is logged as a warning rather than blocking student creation,
        because the student record itself is always valid; the progression record
        can be created manually if auto-creation fails.
        """
        students = super().create(vals_list)
        for student in students:
            if student.current_enrollment_id and student.current_program_term_id:
                try:
                    student._create_initial_progression_history()
                except Exception as exc:
                    _logger.warning(
                        'edu_academic_progression: failed to auto-create initial '
                        'progression history for student %s (id=%d): %s',
                        student.student_no, student.id, exc,
                    )
        return students

    # ── Initial Progression Helpers ───────────────────────────────────────────

    def _has_progression_history(self):
        """Return True if this student already has any progression record."""
        self.ensure_one()
        return bool(self.env['edu.student.progression.history'].search(
            [('student_id', '=', self.id)], limit=1,
        ))

    def _prepare_initial_progression_history_vals(self):
        """Build the vals dict for the student's first progression history record.

        Override in downstream modules if the initial record needs extra fields.
        """
        self.ensure_one()
        enrollment = self.current_enrollment_id
        return {
            'student_id': self.id,
            'enrollment_id': enrollment.id,
            'batch_id': enrollment.batch_id.id,
            'program_id': enrollment.program_id.id,
            'academic_year_id': enrollment.academic_year_id.id,
            'program_term_id': enrollment.current_program_term_id.id,
            'section_id': self.section_id.id if self.section_id else False,
            'start_date': enrollment.enrollment_date or fields.Date.today(),
            'state': 'active',
        }

    def _create_initial_progression_history(self):
        """Create the initial progression history record for this student.

        Called automatically from create(). Returns the new record, or an empty
        recordset if a progression record already exists (idempotent).
        """
        self.ensure_one()
        if self._has_progression_history():
            return self.env['edu.student.progression.history']
        vals = self._prepare_initial_progression_history_vals()
        history = self.env['edu.student.progression.history'].create(vals)
        history.message_post(
            body=_(
                'Initial progression history created: <b>%s</b> — %s.'
            ) % (self.display_name, history.program_term_id.name),
            subtype_xmlid='mail.mt_note',
        )
        return history

    # ── Public API for downstream modules ────────────────────────────────────

    def _get_active_progression_history(self):
        """Return this student's current active progression history record.

        This is the primary integration hook for future academic modules::

            history = student._get_active_progression_history()
            if history:
                context = history.get_academic_context()
                # use context to create attendance / exam / assignment records

        Returns an empty recordset if no active progression exists.
        """
        self.ensure_one()
        return self.env['edu.student.progression.history'].search([
            ('student_id', '=', self.id),
            ('state', '=', 'active'),
        ], limit=1)

    # ── Smart Button ──────────────────────────────────────────────────────────

    def action_view_progression_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Progression History — %s') % self.display_name,
            'res_model': 'edu.student.progression.history',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
