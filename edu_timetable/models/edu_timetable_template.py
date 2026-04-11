from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EduTimetableTemplate(models.Model):
    """Weekly timetable template tied to a cohort.

    A template defines the weekly class schedule for a (academic_year ×
    batch × program_term × section) combination. The template owns a set
    of periods (row definitions: Period 1 = 08:00-08:45) and a set of
    slots (one cell per day × period).

    Only one template per (academic_year × section × program_term) may be
    in the ``active`` state at a time — enforced by a Python constraint.

    The template's ``date_start`` and ``date_end`` bound the academic
    range during which the weekly recurrence applies. Slot ``start_datetime``
    and ``end_datetime`` computed fields project the weekly rule onto the
    first occurrence within this range — enough for gantt and calendar to
    render without materializing every occurrence.
    """

    _name = 'edu.timetable.template'
    _description = 'Timetable Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, program_term_id, section_id'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        readonly=False,
        tracking=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    period_ids = fields.One2many(
        comodel_name='edu.timetable.period',
        inverse_name='template_id',
        string='Periods',
    )
    slot_ids = fields.One2many(
        comodel_name='edu.timetable.slot',
        inverse_name='template_id',
        string='Slots',
    )
    slot_count = fields.Integer(
        string='Slot Count',
        compute='_compute_slot_count',
    )
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('academic_year_id', 'batch_id', 'program_term_id', 'section_id')
    def _compute_name(self):
        for rec in self:
            parts = [
                rec.academic_year_id.display_name or '',
                rec.batch_id.display_name or '',
                rec.program_term_id.display_name or '',
                rec.section_id.display_name or '',
            ]
            rec.name = ' / '.join(p for p in parts if p) or _('New Timetable')

    @api.depends('slot_ids')
    def _compute_slot_count(self):
        for rec in self:
            rec.slot_count = len(rec.slot_ids)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end < rec.date_start:
                raise ValidationError(_('End date must be on or after start date.'))

    @api.constrains('academic_year_id', 'section_id', 'program_term_id', 'state')
    def _check_one_active_per_cohort(self):
        for rec in self:
            if rec.state != 'active':
                continue
            dup = self.search([
                ('id', '!=', rec.id),
                ('academic_year_id', '=', rec.academic_year_id.id),
                ('section_id', '=', rec.section_id.id),
                ('program_term_id', '=', rec.program_term_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if dup:
                raise ValidationError(_(
                    'Another active timetable already exists for this cohort: %s'
                ) % dup.display_name)

    def action_activate(self):
        self.write({'state': 'active'})
        return True

    def action_archive_template(self):
        self.write({'state': 'archived'})
        return True
