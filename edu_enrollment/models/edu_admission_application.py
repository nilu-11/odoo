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
    - action_enroll(): full readiness validation, duplicate protection,
      form return on success
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

    # -- Override enrollment handoff ------------------------------------------
    def action_enroll(self):
        """
        Override: validate, check for duplicates, create enrollment, advance
        application state, and return a form view action opening the enrollment.

        Duplicate protection:
        - If an active (non-cancelled) enrollment already exists, opens it
          instead of creating another. This handles rapid double-clicks and
          re-visits gracefully.
        - The DB UNIQUE constraint on enrollment.application_id is the final
          safety net.

        Readiness:
        - Delegates to _get_enrollment_block_reasons() (defined in edu_admission)
          to validate all required fields before calling the enrollment module.
        - The enrollment module re-validates via
          _check_application_enrollment_readiness() as a second layer.

        State:
        - Advances application state to 'enrolled' after successful creation.
        """
        self.ensure_one()

        # Guard: application must be in the handoff state
        if self.state not in ('ready_for_enrollment', 'enrolled'):
            raise UserError(
                f'Application "{self.application_no}" is not ready for '
                f'enrollment. Current state: "{self.state}". '
                'Use "Mark Ready for Enrollment" first.'
            )

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

        # Guard: must be in exactly ready_for_enrollment to create new
        if self.state != 'ready_for_enrollment':
            raise UserError(
                f'Application "{self.application_no}" is in "{self.state}" '
                'state. Cannot create a new enrollment.'
            )

        # Full readiness validation via admission module helper
        blocks = self._get_enrollment_block_reasons()
        if blocks:
            raise UserError(
                'Cannot create enrollment for "%s":\n%s' % (
                    self.application_no,
                    '\n'.join('  - %s' % b for b in blocks),
                )
            )

        # Delegate to edu.enrollment canonical creation method
        enrollment = self.env['edu.enrollment'].action_create_from_application(self)

        # Advance application state
        self.write({'state': 'enrolled'})

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
