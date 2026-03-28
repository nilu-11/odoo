from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduResultRecomputeBacklogWizard(models.TransientModel):
    """
    Wizard for recomputing results after a back exam session is published.

    Identifies eligible subject lines (failed/absent/etc.), finds their
    back exam marks, applies the back exam policy, and creates new result
    lines while preserving the original attempt history.
    """

    _name = 'edu.result.recompute.backlog.wizard'
    _description = 'Recompute Result After Back Exam'

    # ── Source result session ─────────────────────────────────────────────────
    result_session_id = fields.Many2one(
        'edu.result.session', string='Original Result Session',
        required=True,
        default=lambda self: (
            self.env.context.get('default_result_session_id')
            or self.env.context.get('active_id')
        ),
        domain=[('state', 'in', ('verified', 'published', 'closed'))],
    )

    # ── Back exam session ─────────────────────────────────────────────────────
    back_exam_session_id = fields.Many2one(
        'edu.exam.session', string='Back Exam Session',
        required=True,
        domain=[
            ('attempt_type', 'in', ('back', 'makeup', 'improvement', 'special')),
            ('state', 'in', ('published', 'closed')),
        ],
        help='Select the back exam session whose published marks will be used.',
    )

    # ── Policy ────────────────────────────────────────────────────────────────
    back_exam_policy_id = fields.Many2one(
        'edu.back.exam.policy', string='Back Exam Policy',
        required=True,
        help='Governs carry-forward rules and result replacement logic.',
    )

    # ── Preview info ──────────────────────────────────────────────────────────
    eligible_subject_line_count = fields.Integer(
        string='Eligible Subject Lines',
        compute='_compute_eligible_count',
    )
    affected_student_count = fields.Integer(
        string='Affected Students',
        compute='_compute_eligible_count',
    )

    @api.depends('result_session_id', 'back_exam_session_id')
    def _compute_eligible_count(self):
        for rec in self:
            if not rec.result_session_id:
                rec.eligible_subject_line_count = 0
                rec.affected_student_count = 0
                continue

            eligible = self.env['edu.result.subject.line'].search([
                ('result_session_id', '=', rec.result_session_id.id),
                ('is_back_exam_eligible', '=', True),
                ('back_exam_cleared', '=', False),
                ('superseded_by_result_subject_line_id', '=', False),
            ])
            rec.eligible_subject_line_count = len(eligible)
            rec.affected_student_count = len(
                eligible.mapped('student_progression_history_id')
            )

    @api.onchange('result_session_id')
    def _onchange_result_session(self):
        if self.result_session_id and self.result_session_id.assessment_scheme_id:
            policy = self.result_session_id.assessment_scheme_id.back_exam_policy_id
            if policy:
                self.back_exam_policy_id = policy

    def action_recompute(self):
        """Execute back exam recomputation."""
        self.ensure_one()
        session = self.result_session_id
        back_exam = self.back_exam_session_id
        policy = self.back_exam_policy_id

        if not session:
            raise UserError('No original result session selected.')
        if not back_exam:
            raise UserError('No back exam session selected.')
        if not policy:
            raise UserError('A back exam policy is required.')

        if back_exam.state not in ('published', 'closed'):
            raise ValidationError(
                f'Back exam session "{back_exam.name}" must be published before recomputing.'
            )

        if session.state == 'closed':
            raise UserError(
                'Cannot recompute results for a closed session.'
            )

        from ..models.result_engine import ResultComputeEngine
        engine = ResultComputeEngine(session)
        engine.recompute_after_back_exam(back_exam, policy)

        session.message_post(
            body=(
                f'Back exam recomputation completed using session '
                f'"{back_exam.name}" and policy "{policy.name}".'
            )
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Subject Results',
            'res_model': 'edu.result.subject.line',
            'view_mode': 'list,form',
            'domain': [
                ('result_session_id', '=', session.id),
                ('recomputed_after_back', '=', True),
            ],
        }
