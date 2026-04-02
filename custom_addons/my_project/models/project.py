from odoo import models, fields

class MyProject(models.Model):
    _name = 'my.project'
    _description = 'Project'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Project Name', required=True)
    description = fields.Text(string='Description')
    start_date = fields.Date(string='Start Date')
    start_time = fields.Datetime(string='Start Time')
    end_date = fields.Date(string='End Date')
    end_date = fields.Datetime(string='End Time')
    active = fields.Boolean(string='Active', default=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
        ],
        string='Status',
        default='draft',

    )

    # One2many: one project → many tasks
    task_ids = fields.One2many(
        comodel_name='my.task',
        inverse_name='project_id',   # must match the Many2one field on task
        string='Tasks',
    )

    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_task_count',
    )

    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)
