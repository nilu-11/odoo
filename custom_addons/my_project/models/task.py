from odoo import models, fields

class MyTask(models.Model):
    _name = 'my.task'
    _description = 'Task'

    name = fields.Char(string='Task Name', required=True)
    description = fields.Text(string='Description')
    deadline = fields.Date(string='Deadline')
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Priority', default='medium')
    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='State', default='todo')

    # Many2one: many tasks → one project
    project_id = fields.Many2one(
        comodel_name='my.project',
        string='Project',
        required=True,
        ondelete='cascade',  
    )