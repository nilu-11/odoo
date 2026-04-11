from odoo import models, fields


class NepaliTts(models.Model):
    _name = 'nepali.tts'
    _description = 'Nepali Text to Speech'
    _order = 'create_date desc'

    name = fields.Char(string='Label', readonly=True, default='New')
    text = fields.Text(string='Nepali Text', required=True)
    audio_attachment_id = fields.Many2one(
        'ir.attachment', string='Audio', ondelete='set null', readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('generated', 'Generated')],
        default='draft', readonly=True)
