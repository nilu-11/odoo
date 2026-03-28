from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_threshold_percent = fields.Float(
        string='Attendance Threshold (%)',
        config_parameter='edu_attendance.attendance_threshold_percent',
        default=75.0,
        help=(
            'Minimum attendance percentage required. '
            'Students below this threshold appear in the Defaulters report.'
        ),
    )
