import re
from odoo import api, fields, models

from odoo.tools import html2plaintext

class MailMessage(models.Model):
    _inherit = 'mail.message'

    feedback_text = fields.Char(string='Feedback', compute='_compute_feedback_text')

    @api.depends('body')
    def _compute_feedback_text(self):
        for message in self:
            feedback = False
            body = message.body or ''
            if body:
                plain = html2plaintext(body)
                match = re.search(r'Feedback:\s*(.*)', plain, re.IGNORECASE)
                if match:
                    feedback = match.group(1).strip()
                    if feedback:
                        feedback = feedback.splitlines()[0].strip()
            message.feedback_text = feedback or False
