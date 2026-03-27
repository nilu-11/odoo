from odoo import api, fields, models
from odoo.exceptions import UserError


class EduEnrollment(models.Model):
    """
    Extend edu.enrollment to integrate with edu.student.

    Changes:
      - Redefine ``student_id`` from its placeholder (res.partner)
        to point to the real ``edu.student`` model.
      - Override ``_prepare_student_vals()`` and ``action_create_student()``
        to delegate to ``edu.student.action_create_from_enrollment()``.
      - Recompute ``student_created`` based on the new field.
    """

    _inherit = 'edu.enrollment'

    # ── Redefine student_id to point to edu.student ──
    student_id = fields.Many2one(
        'edu.student', string='Student Record',
        ondelete='set null', tracking=True, index=True,
        help='The official student master record created from this enrollment.',
    )

    # ── Recompute student_created ──
    @api.depends('student_id')
    def _compute_student_created(self):
        for rec in self:
            rec.student_created = bool(rec.student_id)

    # ── Student count helper ──
    student_count = fields.Integer(
        compute='_compute_student_count', string='Students',
    )

    def _compute_student_count(self):
        for rec in self:
            rec.student_count = 1 if rec.student_id else 0

    # ── Override student creation ──
    def _prepare_student_vals(self):
        """Delegate to edu.student's preparation method."""
        self.ensure_one()
        return self.env['edu.student']._prepare_student_vals_from_enrollment(self)

    def action_create_student(self):
        """
        Create an edu.student record from this active enrollment.
        If a student already exists, navigate to it instead of creating a duplicate.
        """
        self.ensure_one()

        if self.state != 'active':
            raise UserError(
                'Student record can only be created from an active enrollment.'
            )

        # If student already exists, open it
        if self.student_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.student',
                'res_id': self.student_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Also check by enrollment link (safety net)
        existing = self.env['edu.student'].search(
            [('current_enrollment_id', '=', self.id)], limit=1,
        )
        if existing:
            self.student_id = existing.id
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.student',
                'res_id': existing.id,
                'view_mode': 'form',
                'target': 'current',
            }

        student = self.env['edu.student'].action_create_from_enrollment(self)
        self.student_id = student.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.student',
            'res_id': student.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_student(self):
        """Navigate to the linked student record."""
        self.ensure_one()
        if not self.student_id:
            raise UserError(
                f'Enrollment "{self.enrollment_no}" has no linked student record.'
            )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.student',
            'res_id': self.student_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
