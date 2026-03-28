import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduAssessmentBulkLockWizard(models.TransientModel):
    """Wizard — confirm or lock multiple continuous assessment records in bulk.

    Accessible from the list view action menu.  Supports two operations:
    - Confirm: moves draft → confirmed
    - Lock:    moves draft/confirmed → locked (restricted to officer/admin)
    """

    _name = 'edu.assessment.bulk.lock.wizard'
    _description = 'Bulk Confirm / Lock Assessment Records Wizard'

    record_ids = fields.Many2many(
        comodel_name='edu.continuous.assessment.record',
        relation='assessment_bulk_lock_wiz_record_rel',
        column1='wizard_id',
        column2='record_id',
        string='Assessment Records',
    )
    action = fields.Selection(
        selection=[
            ('confirm', 'Confirm Selected Records'),
            ('lock', 'Lock Selected Records'),
        ],
        string='Action',
        required=True,
        default='confirm',
    )
    result_message = fields.Char(
        string='Result',
        readonly=True,
    )

    # ── Summary stats (readonly display) ──────────────────────────────────────

    draft_count = fields.Integer(
        string='Draft',
        compute='_compute_summary',
    )
    confirmed_count = fields.Integer(
        string='Confirmed',
        compute='_compute_summary',
    )
    locked_count = fields.Integer(
        string='Already Locked',
        compute='_compute_summary',
    )

    @api.depends('record_ids')
    def _compute_summary(self):
        for rec in self:
            rec.draft_count = len(rec.record_ids.filtered(lambda r: r.state == 'draft'))
            rec.confirmed_count = len(rec.record_ids.filtered(lambda r: r.state == 'confirmed'))
            rec.locked_count = len(rec.record_ids.filtered(lambda r: r.state == 'locked'))

    # ── Default: pre-load active_ids from context ─────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if (
            'record_ids' in fields_list
            and self.env.context.get('active_model') == 'edu.continuous.assessment.record'
        ):
            res['record_ids'] = [(6, 0, self.env.context.get('active_ids', []))]
        return res

    # ── Apply action ──────────────────────────────────────────────────────────

    def action_apply(self):
        """Apply confirm or lock to the selected records."""
        self.ensure_one()
        if not self.record_ids:
            raise UserError(_('No assessment records selected.'))

        if self.action == 'confirm':
            to_process = self.record_ids.filtered(lambda r: r.state == 'draft')
            if not to_process:
                raise UserError(_('None of the selected records are in Draft state.'))
            to_process.write({'state': 'confirmed'})
            msg = _('Confirmed %d record(s).') % len(to_process)

        elif self.action == 'lock':
            # Lock requires officer or higher
            is_officer = (
                self.env.user.has_group('edu_assessment.group_assessment_officer')
                or self.env.user.has_group('edu_assessment.group_assessment_admin')
                or self.env.user.has_group('edu_academic_structure.group_education_admin')
            )
            if not is_officer:
                raise UserError(
                    _('Only Assessment Officers or Admins can lock assessment records in bulk.')
                )
            to_process = self.record_ids.filtered(lambda r: r.state in ('draft', 'confirmed'))
            if not to_process:
                raise UserError(
                    _('None of the selected records are in Draft or Confirmed state.')
                )
            to_process.write({'state': 'locked'})
            msg = _('Locked %d record(s).') % len(to_process)

        else:
            raise UserError(_('Unknown action: %s') % self.action)

        self.result_message = msg

        # Return same wizard to show result
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
