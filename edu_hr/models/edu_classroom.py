from odoo import fields, models


class EduClassroom(models.Model):
    _inherit = 'edu.classroom'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        index=True,
        domain="[('is_teaching_staff', '=', True)]",
    )

    def action_view_teacher_profile(self):
        """Open the teacher's staff profile form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teacher Profile',
            'res_model': 'hr.employee',
            'view_mode': 'form',
            'res_id': self.teacher_id.id,
        }
