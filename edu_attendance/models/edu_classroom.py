from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduClassroomAttendance(models.Model):
    """Inject attendance fields and actions into edu.classroom."""

    _inherit = 'edu.classroom'

    # ═══ Relational Fields ═══

    attendance_register_id = fields.Many2one(
        comodel_name='edu.attendance.register',
        string='Attendance Register',
        ondelete='set null',
        copy=False,
        index=True,
        readonly=True,
        help=(
            'The attendance register linked to this classroom. '
            'Created automatically when the classroom is activated.'
        ),
    )

    # ═══ Computed Fields ═══

    attendance_sheet_count = fields.Integer(
        string='Attendance Sheets',
        compute='_compute_attendance_sheet_stats',
        store=False,
    )
    latest_attendance_date = fields.Date(
        string='Latest Attendance',
        compute='_compute_attendance_sheet_stats',
        store=False,
    )

    # ═══ Computed Methods ═══

    def _compute_attendance_sheet_stats(self):
        """Batch-compute sheet count and latest date for all classrooms."""
        if not self.ids:
            for rec in self:
                rec.attendance_sheet_count = 0
                rec.latest_attendance_date = False
            return

        data = self.env['edu.attendance.sheet']._read_group(
            domain=[('classroom_id', 'in', self.ids)],
            groupby=['classroom_id'],
            aggregates=['__count', 'session_date:max'],
        )
        mapped = {cls.id: (count, max_date) for cls, count, max_date in data}
        for rec in self:
            count, max_date = mapped.get(rec.id, (0, False))
            rec.attendance_sheet_count = count
            rec.latest_attendance_date = max_date

    # ═══ Attendance Actions (from Classroom) ═══

    def action_take_attendance_today(self):
        """One-click: create / open today's attendance sheet and auto-start it.

        - Ensures attendance register exists
        - Finds or creates a sheet for today
        - Auto-starts the sheet (generating all-present lines)
        - Returns the form action
        """
        self.ensure_one()
        if self.state != 'active':
            raise UserError(
                _('Classroom "%s" must be active to take attendance.') % self.name
            )
        self._ensure_attendance_register()
        register = self.attendance_register_id
        if not register:
            raise UserError(
                _('Could not create an attendance register for classroom "%s".')
                % self.name
            )
        if register.state == 'closed':
            raise UserError(
                _('The attendance register for classroom "%s" is closed.')
                % self.name
            )

        today = fields.Date.today()
        AttSheet = self.env['edu.attendance.sheet']

        # Prefer an existing non-submitted sheet for today
        existing = AttSheet.search([
            ('register_id', '=', register.id),
            ('session_date', '=', today),
            ('state', 'in', ('draft', 'in_progress')),
        ], limit=1, order='create_date desc')

        if existing:
            sheet = existing
            if sheet.state == 'draft':
                sheet.action_start()
        else:
            sheet = AttSheet.create({
                'register_id': register.id,
                'session_date': today,
                'taken_by': self.env.user.id,
            })
            sheet.action_start()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance — %s — %s') % (self.name, today),
            'res_model': 'edu.attendance.sheet',
            'view_mode': 'form',
            'res_id': sheet.id,
            'target': 'current',
        }

    def action_create_attendance_sheet(self):
        """Open a new attendance sheet form pre-filled for this classroom."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(
                _('Classroom "%s" must be active to create an attendance sheet.')
                % self.name
            )
        self._ensure_attendance_register()
        register = self.attendance_register_id
        if not register:
            raise UserError(
                _('Could not create an attendance register for classroom "%s".')
                % self.name
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Attendance Sheet — %s') % self.name,
            'res_model': 'edu.attendance.sheet',
            'view_mode': 'form',
            'context': {
                'default_register_id': register.id,
                'default_session_date': fields.Date.today(),
                'default_taken_by': self.env.user.id,
            },
            'target': 'current',
        }

    def action_view_attendance_sheets(self):
        """Open the list of attendance sheets for this classroom."""
        self.ensure_one()
        register = self.attendance_register_id
        domain = (
            [('register_id', '=', register.id)] if register
            else [('id', '=', 0)]
        )
        ctx = {}
        if register:
            ctx['default_register_id'] = register.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance Sheets — %s') % self.name,
            'res_model': 'edu.attendance.sheet',
            'view_mode': 'list,form',
            'domain': domain,
            'context': ctx,
        }

    def action_open_attendance_matrix(self):
        """Open the attendance matrix report wizard pre-filtered to this classroom."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance Matrix — %s') % self.name,
            'res_model': 'edu.attendance.matrix.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_classroom_id': self.id,
                'default_batch_id': self.batch_id.id,
                'default_section_id': self.section_id.id,
                'default_program_term_id': self.program_term_id.id,
            },
        }
