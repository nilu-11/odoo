import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduAttendanceRegister(models.Model):
    """One attendance register per classroom.

    The register is the top-level container for all attendance sheets of a
    classroom.  It is created automatically when the classroom is activated.
    One classroom → one register (UNIQUE constraint on classroom_id).
    """

    _name = 'edu.attendance.register'
    _description = 'Attendance Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, section_id, subject_id'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
    )

    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )

    # ── Stored related fields from classroom ──────────────────────────────────

    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
        related='classroom_id.section_id',
        store=True,
        index=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        related='classroom_id.batch_id',
        store=True,
        index=True,
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        related='classroom_id.program_term_id',
        store=True,
        index=True,
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        related='classroom_id.subject_id',
        store=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        related='classroom_id.academic_year_id',
        store=True,
        index=True,
    )
    teacher_id = fields.Many2one(
        comodel_name='res.users',
        string='Teacher',
        related='classroom_id.teacher_id',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='classroom_id.company_id',
        store=True,
        index=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='open',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Computed ──────────────────────────────────────────────────────────────

    sheet_count = fields.Integer(
        string='Sessions',
        compute='_compute_sheet_count',
        store=False,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'classroom_unique',
            'UNIQUE(classroom_id)',
            'An attendance register already exists for this classroom.',
        ),
    ]

    # ── Computed ──────────────────────────────────────────────────────────────

    def _compute_sheet_count(self):
        data = self.env['edu.attendance.sheet']._read_group(
            domain=[('register_id', 'in', self.ids)],
            groupby=['register_id'],
            aggregates=['__count'],
        )
        mapped = {reg.id: count for reg, count in data}
        for rec in self:
            rec.sheet_count = mapped.get(rec.id, 0)

    # ── State transitions ─────────────────────────────────────────────────────

    def action_close(self):
        for rec in self:
            if rec.state != 'open':
                raise UserError(_('Register "%s" is already closed.') % rec.name)
            in_progress = self.env['edu.attendance.sheet'].search_count([
                ('register_id', '=', rec.id),
                ('state', '=', 'in_progress'),
            ])
            if in_progress:
                raise UserError(_(
                    'Cannot close register "%s" — '
                    'there are attendance sheets still in progress.'
                ) % rec.name)
        self.write({'state': 'closed'})

    def action_reopen(self):
        """Admin only: reopen a closed register."""
        for rec in self:
            if rec.state != 'closed':
                raise UserError(_('Register "%s" is not closed.') % rec.name)
        self.write({'state': 'open'})

    # ── Smart button actions ──────────────────────────────────────────────────

    def action_view_sheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance Sheets — %s') % self.name,
            'res_model': 'edu.attendance.sheet',
            'view_mode': 'list,form',
            'domain': [('register_id', '=', self.id)],
            'context': {'default_register_id': self.id},
        }

    # ── Reporting helper ──────────────────────────────────────────────────────

    def get_student_attendance_summary(self):
        """Return {student_id: {'total': n, 'present': n, 'percent': f}}."""
        self.ensure_one()
        lines = self.env['edu.attendance.sheet.line']._read_group(
            domain=[
                ('register_id', '=', self.id),
                ('sheet_state', '=', 'submitted'),
            ],
            groupby=['student_id', 'status'],
            aggregates=['__count'],
        )
        summary = {}
        for student, status, count in lines:
            sid = student.id
            if sid not in summary:
                summary[sid] = {'total': 0, 'present': 0}
            summary[sid]['total'] += count
            if status == 'present':
                summary[sid]['present'] += count
        for sid in summary:
            total = summary[sid]['total']
            summary[sid]['percent'] = (
                round(summary[sid]['present'] / total * 100, 1) if total else 0.0
            )
        return summary
