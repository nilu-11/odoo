from odoo import api, fields, models


class EduAdmissionApplication(models.Model):
    """
    Extend admission application with reverse enrollment linkage.

    Adds:
    - enrollment_ids / enrollment_count for smart button navigation
    - Override action_enroll() to delegate to edu.enrollment
    """

    _inherit = 'edu.admission.application'

    # ── Reverse linkage ──────────────────────────────────────────────────────
    enrollment_ids = fields.One2many(
        comodel_name='edu.enrollment',
        inverse_name='application_id',
        string='Enrollments',
    )
    enrollment_count = fields.Integer(
        string='Enrollments',
        compute='_compute_enrollment_count',
    )

    def _compute_enrollment_count(self):
        data = self.env['edu.enrollment']._read_group(
            [('application_id', 'in', self.ids)],
            ['application_id'],
            ['__count'],
        )
        mapped = {app.id: count for app, count in data}
        for rec in self:
            rec.enrollment_count = mapped.get(rec.id, 0)

    # ── Override enrollment handoff ──────────────────────────────────────────
    def action_enroll(self):
        """
        Override: create enrollment via edu.enrollment model then
        transition application to enrolled state.
        """
        Enrollment = self.env['edu.enrollment']
        for rec in self:
            if rec.state != 'ready_for_enrollment':
                from odoo.exceptions import UserError
                raise UserError(
                    f'Application "{rec.application_no}" is not ready '
                    'for enrollment.'
                )
            Enrollment.action_create_from_application(rec)
        self.write({'state': 'enrolled'})

    # ── Smart button ─────────────────────────────────────────────────────────
    def action_view_enrollment(self):
        self.ensure_one()
        enrollments = self.enrollment_ids
        if len(enrollments) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.enrollment',
                'res_id': enrollments.id,
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': f'Enrollments — {self.application_no}',
            'res_model': 'edu.enrollment',
            'view_mode': 'list,form',
            'domain': [('application_id', '=', self.id)],
        }
