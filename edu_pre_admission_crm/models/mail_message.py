import re
from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    call_feedback = fields.Char(
        string='Feedback',
        compute='_compute_call_feedback',
    )

    def _compute_call_feedback(self):
        feedback_re = re.compile(
            r'Feedback:</b>\s*<br\s*/?>\s*(.*?)\s*</p>',
            re.DOTALL | re.IGNORECASE,
        )
        strip_tags_re = re.compile(r'<[^>]+>')
        for msg in self:
            body = msg.body or ''
            match = feedback_re.search(body)
            if match:
                msg.call_feedback = strip_tags_re.sub('', match.group(1)).strip()
            else:
                msg.call_feedback = strip_tags_re.sub('', body).strip()
