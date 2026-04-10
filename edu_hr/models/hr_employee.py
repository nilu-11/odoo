from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ═══ Staff Classification ═══

    is_teaching_staff = fields.Boolean(
        string='Is Teaching Staff',
        default=False,
        tracking=True,
        help='Enable for teachers and instructors who are assigned to classrooms.',
    )
    staff_type = fields.Selection(
        selection=[
            ('teacher', 'Teacher'),
            ('lab_assistant', 'Lab Assistant'),
            ('librarian', 'Librarian'),
            ('admin_staff', 'Administrative Staff'),
            ('support_staff', 'Support Staff'),
            ('other', 'Other'),
        ],
        string='Staff Type',
        tracking=True,
    )
    employee_code = fields.Char(
        string='Employee Code',
        copy=False,
        tracking=True,
        help='Institution-specific staff identifier. Auto-generated for teaching staff.',
    )

    # ═══ Academic Profile ═══

    edu_department_id = fields.Many2one(
        comodel_name='edu.department',
        string='Academic Department',
        ondelete='set null',
        tracking=True,
        help='The academic department this staff member belongs to.',
    )
    qualification_ids = fields.One2many(
        comodel_name='edu.staff.qualification',
        inverse_name='employee_id',
        string='Qualifications',
    )
    subject_expertise_ids = fields.Many2many(
        comodel_name='edu.subject',
        relation='hr_employee_edu_subject_rel',
        column1='employee_id',
        column2='subject_id',
        string='Subject Expertise',
        help='Subjects this staff member is qualified to teach.',
    )

    # ═══ Workload (Computed) ═══

    classroom_ids = fields.One2many(
        comodel_name='edu.classroom',
        inverse_name='teacher_id',
        string='Classrooms',
    )
    classroom_count = fields.Integer(
        string='Classrooms',
        compute='_compute_classroom_count',
        store=True,
    )
    exam_paper_count = fields.Integer(
        string='Exam Papers',
        compute='_compute_exam_paper_count',
    )
    assessment_record_count = fields.Integer(
        string='Assessments',
        compute='_compute_assessment_record_count',
    )
    attendance_register_count = fields.Integer(
        string='Attendance Registers',
        compute='_compute_attendance_register_count',
    )

    # ═══ Computed Methods ═══

    @api.depends('classroom_ids')
    def _compute_classroom_count(self):
        for rec in self:
            rec.classroom_count = len(rec.classroom_ids)

    def _compute_exam_paper_count(self):
        for rec in self:
            if rec.id:
                rec.exam_paper_count = self.env['edu.exam.paper'].search_count(
                    [('teacher_id', '=', rec.id)]
                )
            else:
                rec.exam_paper_count = 0

    def _compute_assessment_record_count(self):
        for rec in self:
            if rec.id:
                rec.assessment_record_count = self.env[
                    'edu.continuous.assessment.record'
                ].search_count([('teacher_id', '=', rec.id)])
            else:
                rec.assessment_record_count = 0

    def _compute_attendance_register_count(self):
        for rec in self:
            if rec.id:
                rec.attendance_register_count = self.env[
                    'edu.attendance.register'
                ].search_count([('teacher_id', '=', rec.id)])
            else:
                rec.attendance_register_count = 0

    # ═══ Smart Button Actions ═══

    def action_view_classrooms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Classrooms — %s' % self.name,
            'res_model': 'edu.classroom',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
            'context': {'default_teacher_id': self.id},
        }

    def action_view_exam_papers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exam Papers — %s' % self.name,
            'res_model': 'edu.exam.paper',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
        }

    def action_view_assessment_records(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assessments — %s' % self.name,
            'res_model': 'edu.continuous.assessment.record',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
        }

    def action_view_attendance_registers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attendance Registers — %s' % self.name,
            'res_model': 'edu.attendance.register',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.id)],
        }

    # ═══ Auto-generate Employee Code ═══

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_teaching_staff') and not vals.get('employee_code'):
                vals['employee_code'] = self.env['ir.sequence'].next_by_code(
                    'edu.employee.code'
                ) or ''
        return super().create(vals_list)
