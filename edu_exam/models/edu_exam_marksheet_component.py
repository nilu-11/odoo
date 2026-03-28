import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class EduExamMarksheetComponent(models.Model):
    """Marksheet Component — marks for one paper component on one student's
    marksheet.  Created automatically (or manually) when a paper has
    components defined.
    """

    _name = 'edu.exam.marksheet.component'
    _description = 'Exam Marksheet Component'
    _order = 'marksheet_id, paper_component_id'
    _rec_name = 'component_name'

    marksheet_id = fields.Many2one(
        comodel_name='edu.exam.marksheet',
        string='Marksheet',
        required=True,
        ondelete='cascade',
        index=True,
    )
    paper_component_id = fields.Many2one(
        comodel_name='edu.exam.paper.component',
        string='Paper Component',
        required=True,
        ondelete='restrict',
    )

    # ── Stored related fields (for reporting without JOINs) ───────────────────

    component_name = fields.Char(
        string='Component',
        related='paper_component_id.name',
        store=True,
    )
    component_type = fields.Selection(
        related='paper_component_id.component_type',
        string='Type',
        store=True,
    )
    max_marks = fields.Float(
        string='Max Marks',
        related='paper_component_id.max_marks',
        store=True,
    )
    pass_marks_component = fields.Float(
        string='Pass Marks',
        related='paper_component_id.pass_marks',
        store=True,
    )

    # ── Marks entry ───────────────────────────────────────────────────────────

    status = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('exempt', 'Exempt'),
            ('withheld', 'Withheld'),
        ],
        string='Status',
        default='present',
    )
    marks_obtained = fields.Float(
        string='Marks Obtained',
        default=0.0,
    )
    grace_marks = fields.Float(
        string='Grace Marks',
        default=0.0,
    )
    final_marks = fields.Float(
        string='Final Marks',
        compute='_compute_final',
        store=True,
    )
    is_pass = fields.Boolean(
        string='Pass',
        compute='_compute_is_pass',
        store=True,
    )
    remarks = fields.Char(
        string='Remarks',
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'unique_marksheet_component',
            'UNIQUE(marksheet_id, paper_component_id)',
            'Each component can only appear once per marksheet.',
        ),
        (
            'check_marks_obtained_non_negative',
            'CHECK(marks_obtained >= 0)',
            'Marks obtained cannot be negative.',
        ),
    ]

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('marks_obtained', 'grace_marks', 'status')
    def _compute_final(self):
        for rec in self:
            if rec.status == 'present':
                rec.final_marks = (rec.marks_obtained or 0.0) + (rec.grace_marks or 0.0)
            else:
                rec.final_marks = 0.0

    @api.depends('final_marks', 'pass_marks_component', 'status')
    def _compute_is_pass(self):
        for rec in self:
            rec.is_pass = (
                rec.status == 'present'
                and (rec.final_marks or 0.0) >= (rec.pass_marks_component or 0.0)
            )

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('marks_obtained', 'max_marks')
    def _check_marks_le_max(self):
        for rec in self:
            if rec.max_marks and (rec.marks_obtained or 0.0) > rec.max_marks:
                raise ValidationError(
                    _(
                        'Marks obtained (%.2f) exceed the component max marks (%.2f) for "%s".'
                    ) % (rec.marks_obtained, rec.max_marks, rec.component_name or '')
                )
