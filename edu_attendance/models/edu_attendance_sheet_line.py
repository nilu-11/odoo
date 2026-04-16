from odoo import fields, models, _
from odoo.exceptions import UserError


class EduAttendanceSheetLine(models.Model):
    """One student's attendance record within a session sheet."""

    _name = 'edu.attendance.sheet.line'
    _description = 'Attendance Sheet Line'
    _order = 'roll_number, student_id'
    _rec_name = 'student_id'

    # ── Parent sheet ──────────────────────────────────────────────────────────

    sheet_id = fields.Many2one(
        comodel_name='edu.attendance.sheet',
        string='Sheet',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Stored related fields for direct reporting ────────────────────────────

    register_id = fields.Many2one(
        comodel_name='edu.attendance.register',
        related='sheet_id.register_id',
        store=True,
        index=True,
        string='Register',
    )
    session_date = fields.Date(
        related='sheet_id.session_date',
        store=True,
        string='Session Date',
    )
    sheet_state = fields.Selection(
        related='sheet_id.state',
        store=True,
        string='Sheet Status',
        index=True,
    )
    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        related='sheet_id.classroom_id',
        store=True,
        index=True,
        string='Classroom',
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        related='sheet_id.subject_id',
        store=True,
        index=True,
        string='Subject',
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        related='sheet_id.section_id',
        store=True,
        index=True,
        string='Section',
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        related='sheet_id.academic_year_id',
        store=True,
        index=True,
        string='Academic Year',
    )

    # ── Student ───────────────────────────────────────────────────────────────

    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
    )
    student_progression_history_id = fields.Many2one(
        comodel_name='edu.student.progression.history',
        string='Progression Context',
        ondelete='restrict',
        index=True,
        help=(
            'Academic context at the time of this session. '
            'Ensures historical correctness after batch promotions.'
        ),
    )
    roll_number = fields.Char(
        related='student_id.roll_number',
        store=True,
        string='Roll No',
    )

    # ── Attendance ────────────────────────────────────────────────────────────

    status = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('late', 'Late'),
            ('excused', 'Excused'),
        ],
        string='Status',
        required=True,
        default='present',
        index=True,
    )
    note = fields.Char(string='Note')

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'sheet_student_unique',
            'UNIQUE(sheet_id, student_id)',
            'A student can appear only once per attendance sheet.',
        ),
    ]

    # ── ORM override ──────────────────────────────────────────────────────────

    def write(self, vals):
        """Lock all fields when the parent sheet is submitted.
        Auto-start draft sheets when a status change is made.
        """
        locked = self.filtered(lambda l: l.sheet_id.state == 'submitted')
        if locked:
            raise UserError(_(
                'Cannot edit attendance lines on a submitted sheet. '
                'Reset the sheet to draft first.'
            ))
        if 'status' in vals:
            draft_sheets = self.mapped('sheet_id').filtered(lambda s: s.state == 'draft')
            for sheet in draft_sheets:
                if not sheet.line_ids:
                    sheet.action_generate_lines()
                sheet.state = 'in_progress'
        return super().write(vals)
