from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduResultSession(models.Model):
    """
    Top-level result computation event.

    Ties together an assessment scheme, grading scheme, and result rule for a
    specific academic scope (year + program + batch + term).  Computation flows
    through the ResultComputeEngine service and produces edu.result.subject.line
    and edu.result.student records.

    State machine:  draft → processing → verified → published → closed
    """

    _name = 'edu.result.session'
    _description = 'Result Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Result Session', required=True, copy=False,
        default='New', tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('processing', 'Processing'),
            ('verified', 'Verified'),
            ('published', 'Published'),
            ('closed', 'Closed'),
        ],
        string='Status', default='draft', required=True,
        tracking=True, index=True,
    )
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        index=True,
    )

    # ── Scheme / rule links ───────────────────────────────────────────────────
    assessment_scheme_id = fields.Many2one(
        'edu.assessment.scheme', string='Assessment Scheme',
        required=True, ondelete='restrict', tracking=True,
        states={'draft': [('readonly', False)]},
    )
    grading_scheme_id = fields.Many2one(
        'edu.grading.scheme', string='Grading Scheme',
        ondelete='restrict', tracking=True,
    )
    result_rule_id = fields.Many2one(
        'edu.result.rule', string='Result Rule',
        ondelete='restrict', tracking=True,
    )

    # ── Scope ─────────────────────────────────────────────────────────────────
    academic_year_id = fields.Many2one(
        'edu.academic.year', string='Academic Year',
        required=True, ondelete='restrict', index=True,
    )
    program_id = fields.Many2one(
        'edu.program', string='Program',
        ondelete='restrict', index=True,
    )
    batch_id = fields.Many2one(
        'edu.batch', string='Batch',
        ondelete='restrict', index=True,
        domain="[('program_id', '=', program_id)]",
    )
    program_term_id = fields.Many2one(
        'edu.program.term', string='Program Term',
        ondelete='restrict', index=True,
        domain="[('program_id', '=', program_id)]",
    )

    # ── Results ───────────────────────────────────────────────────────────────
    subject_line_ids = fields.One2many(
        'edu.result.subject.line', 'result_session_id',
        string='Subject Results',
    )
    student_result_ids = fields.One2many(
        'edu.result.student', 'result_session_id',
        string='Student Results',
    )

    # ── Computed stats ────────────────────────────────────────────────────────
    subject_line_count = fields.Integer(
        string='Subject Lines', compute='_compute_counts', store=True,
    )
    student_result_count = fields.Integer(
        string='Students', compute='_compute_counts', store=True,
    )
    pass_count = fields.Integer(
        string='Passed', compute='_compute_counts', store=True,
    )
    fail_count = fields.Integer(
        string='Failed', compute='_compute_counts', store=True,
    )
    backlog_count = fields.Integer(
        string='With Backlog', compute='_compute_counts', store=True,
    )

    published_on = fields.Datetime(string='Published On', readonly=True)
    verified_by = fields.Many2one(
        'res.users', string='Verified By', readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = seq.next_by_code('edu.result.session') or 'New'
        return super().create(vals_list)

    @api.depends(
        'subject_line_ids',
        'student_result_ids',
        'student_result_ids.result_status',
    )
    def _compute_counts(self):
        for rec in self:
            rec.subject_line_count = len(rec.subject_line_ids)
            student_results = rec.student_result_ids
            rec.student_result_count = len(student_results)
            rec.pass_count = len(
                student_results.filtered(
                    lambda r: r.result_status in ('pass', 'promoted')
                )
            )
            rec.fail_count = len(
                student_results.filtered(
                    lambda r: r.result_status in ('fail', 'repeat')
                )
            )
            rec.backlog_count = len(
                student_results.filtered(lambda r: r.has_active_backlog)
            )

    # ── State transitions ──────────────────────────────────────────────────────

    def _check_editable(self):
        for rec in self:
            if rec.state in ('published', 'closed'):
                raise UserError(
                    f'Result session "{rec.name}" is {rec.state} and cannot be modified.'
                )

    def action_start_processing(self):
        """Trigger computation via the wizard or direct call."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft sessions can be set to processing.')
            rec.state = 'processing'
            rec.message_post(body='Result computation started.')

    def action_verify(self):
        for rec in self:
            if rec.state != 'processing':
                raise UserError('Session must be in Processing state to verify.')
            if not rec.student_result_ids:
                raise UserError(
                    'No student results found. Run computation before verifying.'
                )
            rec.state = 'verified'
            rec.verified_by = self.env.uid
            rec.message_post(body=f'Result verified by {self.env.user.name}.')

    def action_publish(self):
        for rec in self:
            if rec.state != 'verified':
                raise UserError('Session must be Verified before publishing.')
            rec.state = 'published'
            rec.published_on = fields.Datetime.now()
            rec.student_result_ids.write({'published_on': rec.published_on})
            rec.message_post(body='Result published.')

    def action_close(self):
        for rec in self:
            if rec.state != 'published':
                raise UserError('Only published sessions can be closed.')
            rec.state = 'closed'
            rec.message_post(body='Result session closed and locked.')

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == 'closed':
                raise UserError(
                    'Closed sessions cannot be reset. Contact an administrator.'
                )
            rec.state = 'draft'
            rec.message_post(body='Reset to Draft.')

    # ── Computation ───────────────────────────────────────────────────────────

    def action_compute(self):
        """Compute all results for this session using the ResultComputeEngine."""
        self.ensure_one()
        if self.state not in ('draft', 'processing'):
            raise UserError('Computation is only allowed in Draft or Processing state.')
        if not self.assessment_scheme_id:
            raise UserError('An assessment scheme must be set before computing.')
        self.action_start_processing()
        from .result_engine import ResultComputeEngine
        engine = ResultComputeEngine(self)
        engine.compute()
        self.message_post(body='Result computation completed successfully.')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Computation Complete',
                'message': f'Results computed for {self.student_result_count} students.',
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Smart button actions ───────────────────────────────────────────────────

    def action_view_subject_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subject Results',
            'res_model': 'edu.result.subject.line',
            'view_mode': 'list,form',
            'domain': [('result_session_id', '=', self.id)],
            'context': {'default_result_session_id': self.id},
        }

    def action_view_student_results(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Student Results',
            'res_model': 'edu.result.student',
            'view_mode': 'list,form',
            'domain': [('result_session_id', '=', self.id)],
            'context': {'default_result_session_id': self.id},
        }

    def action_open_compute_wizard(self):
        """Open the compute wizard with this session pre-filled."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Compute Results',
            'res_model': 'edu.result.compute.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_result_session_id': self.id},
        }

    def action_open_recompute_backlog_wizard(self):
        """Open the back exam recompute wizard with this session pre-filled."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Recompute After Back Exam',
            'res_model': 'edu.result.recompute.backlog.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_result_session_id': self.id},
        }
