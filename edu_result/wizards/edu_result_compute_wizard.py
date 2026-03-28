from odoo import api, fields, models
from odoo.exceptions import UserError


class EduResultComputeWizard(models.TransientModel):
    """
    Wizard for triggering result computation on a result session.

    Allows the user to preview scope, confirm grading/rule settings,
    and then execute the computation engine.
    """

    _name = 'edu.result.compute.wizard'
    _description = 'Compute Result Wizard'

    result_session_id = fields.Many2one(
        'edu.result.session', string='Result Session',
        required=True,
        default=lambda self: (
            self.env.context.get('default_result_session_id')
            or self.env.context.get('active_id')
        ),
    )

    # ── Scheme info (readonly display) ────────────────────────────────────────
    assessment_scheme_id = fields.Many2one(
        'edu.assessment.scheme', string='Assessment Scheme',
        related='result_session_id.assessment_scheme_id',
        readonly=True,
    )
    grading_scheme_id = fields.Many2one(
        'edu.grading.scheme', string='Grading Scheme',
        related='result_session_id.grading_scheme_id',
        readonly=True,
    )
    result_rule_id = fields.Many2one(
        'edu.result.rule', string='Result Rule',
        related='result_session_id.result_rule_id',
        readonly=True,
    )

    # ── Scope display ──────────────────────────────────────────────────────────
    academic_year_id = fields.Many2one(
        'edu.academic.year', related='result_session_id.academic_year_id',
        readonly=True,
    )
    program_id = fields.Many2one(
        'edu.program', related='result_session_id.program_id',
        readonly=True,
    )
    batch_id = fields.Many2one(
        'edu.batch', related='result_session_id.batch_id',
        readonly=True,
    )
    program_term_id = fields.Many2one(
        'edu.program.term', related='result_session_id.program_term_id',
        readonly=True,
    )

    # ── Options ────────────────────────────────────────────────────────────────
    recompute_if_exists = fields.Boolean(
        string='Recompute (Wipe Existing Results)',
        default=True,
        help='If checked, all existing results for this session will be '
             'deleted and recomputed from scratch.',
    )

    # ── Estimated scope (informational) ───────────────────────────────────────
    estimated_student_count = fields.Integer(
        string='Estimated Students',
        compute='_compute_estimated_scope',
    )
    estimated_curriculum_line_count = fields.Integer(
        string='Estimated Subjects',
        compute='_compute_estimated_scope',
    )

    @api.depends(
        'result_session_id.academic_year_id',
        'result_session_id.program_id',
        'result_session_id.batch_id',
        'result_session_id.program_term_id',
    )
    def _compute_estimated_scope(self):
        for rec in self:
            session = rec.result_session_id
            if not session:
                rec.estimated_student_count = 0
                rec.estimated_curriculum_line_count = 0
                continue

            ph_domain = []
            if session.academic_year_id:
                ph_domain.append(('academic_year_id', '=', session.academic_year_id.id))
            if session.program_id:
                ph_domain.append(('program_id', '=', session.program_id.id))
            if session.batch_id:
                ph_domain.append(('batch_id', '=', session.batch_id.id))
            if session.program_term_id:
                ph_domain.append(('program_term_id', '=', session.program_term_id.id))
            ph_domain.append(('state', 'in', ('active', 'completed', 'promoted')))
            rec.estimated_student_count = self.env[
                'edu.student.progression.history'
            ].search_count(ph_domain)

            cl_domain = []
            if session.program_id:
                cl_domain.append(('program_id', '=', session.program_id.id))
            if session.program_term_id:
                cl_domain.append(('program_term_id', '=', session.program_term_id.id))
            rec.estimated_curriculum_line_count = self.env[
                'edu.curriculum.line'
            ].search_count(cl_domain)

    def action_compute(self):
        """Execute the result computation engine."""
        self.ensure_one()
        session = self.result_session_id
        if not session:
            raise UserError('No result session selected.')
        if not session.assessment_scheme_id:
            raise UserError(
                'The result session must have an assessment scheme before computing.'
            )
        if not self.recompute_if_exists and session.student_result_ids:
            raise UserError(
                'Results already exist for this session. '
                'Enable "Recompute" to overwrite them.'
            )

        # Validate required config
        if not session.result_rule_id:
            raise UserError(
                'A result rule is required. Please configure one on the session.'
            )

        session.action_compute()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Student Results',
            'res_model': 'edu.result.student',
            'view_mode': 'list,form',
            'domain': [('result_session_id', '=', session.id)],
        }
