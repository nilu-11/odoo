from odoo import api, fields, models


class EduContinuousAssessmentRecord(models.Model):
    _inherit = 'edu.continuous.assessment.record'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        default=lambda self: self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        ),
        index=True,
        tracking=True,
        domain="[('is_teaching_staff', '=', True)]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override to set teacher_id default as hr.employee instead of res.users."""
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        for vals in vals_list:
            if not vals.get('teacher_id') and employee:
                vals.setdefault('teacher_id', employee.id)
        return super().create(vals_list)

    @api.onchange('classroom_id')
    def _onchange_classroom_id(self):
        """Override to use hr.employee for teacher auto-population."""
        if self.classroom_id:
            cl = self.classroom_id
            self.section_id = cl.section_id
            self.batch_id = cl.batch_id
            self.program_term_id = cl.program_term_id
            self.curriculum_line_id = cl.curriculum_line_id
            self.subject_id = cl.subject_id
            # Auto-populate teacher from classroom
            current_employee = self.env['hr.employee'].search(
                [('user_id', '=', self.env.uid)], limit=1
            )
            if not self.teacher_id or self.teacher_id == current_employee:
                self.teacher_id = cl.teacher_id or current_employee
            # Derive academic_year from classroom's batch (via related field)
            if cl.academic_year_id:
                self.academic_year_id = cl.academic_year_id
