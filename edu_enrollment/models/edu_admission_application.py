import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduAdmissionApplication(models.Model):
    """
    Extend edu.admission.application with reverse enrollment linkage.

    This extension is defined in edu_enrollment so that all fields and methods
    referencing edu.enrollment only exist when that module is installed,
    avoiding circular dependency.

    Fields added:
    - enrollment_ids: reverse One2many (application -> enrollments)
    - enrollment_id:  computed convenience Many2one to the active enrollment
    - enrollment_count: smart button badge count

    Methods overridden:
    - _create_enrollment_on_enroll(): hook called by base action_enroll();
      creates enrollment record, handles duplicates, returns form action
    - action_view_enrollment(): open active enrollment form cleanly
    """

    _inherit = 'edu.admission.application'

    # -- Reverse linkage -------------------------------------------------------
    enrollment_ids = fields.One2many(
        comodel_name='edu.enrollment',
        inverse_name='application_id',
        string='Enrollments',
        readonly=True,
    )
    enrollment_count = fields.Integer(
        string='Enrollment Count',
        compute='_compute_enrollment_count',
        help='Number of enrollment records linked to this application.',
    )
    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Primary Enrollment',
        compute='_compute_enrollment_id',
        help='Convenience link to the active (non-cancelled) enrollment. '
             'Derived from enrollment_ids. Use enrollment_ids for the full list.',
    )

    def _compute_enrollment_count(self):
        """Efficient count using _read_group to avoid N+1 queries."""
        data = self.env['edu.enrollment']._read_group(
            [('application_id', 'in', self.ids)],
            ['application_id'],
            ['__count'],
        )
        mapped = {app.id: count for app, count in data}
        for rec in self:
            rec.enrollment_count = mapped.get(rec.id, 0)

    @api.depends('enrollment_ids', 'enrollment_ids.state')
    def _compute_enrollment_id(self):
        """
        Resolve the primary active (non-cancelled) enrollment for this
        application. Returns False if no active enrollment exists.
        """
        for rec in self:
            active = rec.enrollment_ids.filtered(lambda e: e.state != 'cancelled')
            rec.enrollment_id = active[0] if active else False

    # -- Override enrollment creation hook ------------------------------------
    def _create_enrollment_on_enroll(self):
        """
        Hook override: create the enrollment record and return a form action.

        Called by the base action_enroll() after state/readiness validation.
        State is advanced to 'enrolled' by the caller (base action_enroll).

        Duplicate protection:
        - If an active (non-cancelled) enrollment already exists, opens it
          instead of creating another. This handles rapid double-clicks and
          re-visits gracefully.
        - The DB UNIQUE constraint on enrollment.application_id is the final
          safety net.
        """
        self.ensure_one()

        # Duplicate guard: if an active enrollment already exists, open it
        active_enrollment = self.enrollment_ids.filtered(
            lambda e: e.state != 'cancelled'
        )
        if active_enrollment:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Enrollment for {self.application_no}',
                'res_model': 'edu.enrollment',
                'res_id': active_enrollment[0].id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Delegate to edu.enrollment canonical creation method
        enrollment = self.env['edu.enrollment'].action_create_from_application(self)

        # Auto-confirm if enrollment is immediately ready (no required
        # fees blocking).  This creates the student record and portal
        # user in one step, saving manual button clicks.
        if enrollment.can_confirm:
            try:
                enrollment.action_confirm()
            except UserError:
                _logger.info(
                    'Auto-confirm skipped for enrollment %s — not ready.',
                    enrollment.enrollment_no,
                )

        return {
            'type': 'ir.actions.act_window',
            'name': f'Enrollment for {self.application_no}',
            'res_model': 'edu.enrollment',
            'res_id': enrollment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # -- Smart button ----------------------------------------------------------
    def action_view_enrollment(self):
        """
        Open enrollment record(s) linked to this application.

        - No enrollments -> UserError
        - Exactly one enrollment -> form view
        - Multiple enrollments -> list/form view filtered by application
        """
        self.ensure_one()
        enrollments = self.enrollment_ids
        if not enrollments:
            raise UserError(
                f'Application "{self.application_no}" has no linked enrollments.'
            )
        if len(enrollments) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Enrollment for {self.application_no}',
                'res_model': 'edu.enrollment',
                'res_id': enrollments[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': f'Enrollments for {self.application_no}',
            'res_model': 'edu.enrollment',
            'view_mode': 'list,form',
            'domain': [('application_id', '=', self.id)],
        }
