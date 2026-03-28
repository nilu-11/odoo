"""
Model extensions: adds result-related smart buttons to existing EMIS models.
"""
from odoo import api, fields, models


class EduStudent(models.Model):
    _inherit = 'edu.student'

    result_student_ids = fields.One2many(
        'edu.result.student', 'student_id',
        string='Results',
    )
    result_count = fields.Integer(
        string='Results', compute='_compute_result_count',
    )

    @api.depends('result_student_ids')
    def _compute_result_count(self):
        for rec in self:
            rec.result_count = len(rec.result_student_ids)

    def action_view_results(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Results',
            'res_model': 'edu.result.student',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
        }


class EduBatch(models.Model):
    _inherit = 'edu.batch'

    result_session_ids = fields.One2many(
        'edu.result.session', 'batch_id',
        string='Result Sessions',
    )
    result_session_count = fields.Integer(
        string='Result Sessions', compute='_compute_result_session_count',
    )

    @api.depends('result_session_ids')
    def _compute_result_session_count(self):
        for rec in self:
            rec.result_session_count = len(rec.result_session_ids)

    def action_view_result_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Result Sessions',
            'res_model': 'edu.result.session',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
        }


class EduExamSession(models.Model):
    """Add a smart button from exam session → result sessions."""
    _inherit = 'edu.exam.session'

    result_session_count = fields.Integer(
        string='Result Sessions',
        compute='_compute_result_session_count',
    )

    def _compute_result_session_count(self):
        ResultSession = self.env['edu.result.session']
        for rec in self:
            # Find result sessions that share the same scheme
            count = ResultSession.search_count([
                ('assessment_scheme_id', '=', rec.assessment_scheme_id.id),
                ('academic_year_id', '=', rec.academic_year_id.id),
            ]) if rec.assessment_scheme_id and rec.academic_year_id else 0
            rec.result_session_count = count

    def action_view_result_sessions(self):
        self.ensure_one()
        domain = []
        if self.assessment_scheme_id:
            domain.append(('assessment_scheme_id', '=', self.assessment_scheme_id.id))
        if self.academic_year_id:
            domain.append(('academic_year_id', '=', self.academic_year_id.id))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Result Sessions',
            'res_model': 'edu.result.session',
            'view_mode': 'list,form',
            'domain': domain,
        }
