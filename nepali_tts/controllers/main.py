import io
import base64
from datetime import datetime
from odoo import http
from odoo.http import request


class NepaliTtsController(http.Controller):

    @http.route('/nepali_tts/generate', type='json', auth='user', methods=['POST'])
    def generate(self, record_id, **kwargs):
        try:
            from gtts import gTTS
        except ImportError:
            return {'error': 'gTTS not installed. Run: /opt/odoo19/venv/bin/pip install gTTS'}

        record = request.env['nepali.tts'].browse(int(record_id))
        if not record.exists():
            return {'error': 'Record not found.'}
        if not record.text or not record.text.strip():
            return {'error': 'No text to convert.'}

        try:
            tts = gTTS(text=record.text, lang='ne', slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            mp3_bytes = buf.getvalue()
        except Exception as e:
            return {'error': f'Could not reach Google TTS. Check server internet. ({e})'}

        if not mp3_bytes:
            return {'error': 'Audio generation failed. Try again.'}

        # Remove old attachment
        if record.audio_attachment_id:
            record.audio_attachment_id.sudo().unlink()

        attachment = request.env['ir.attachment'].sudo().create({
            'name': f'nepali_tts_{record.id}.mp3',
            'datas': base64.b64encode(mp3_bytes).decode(),
            'mimetype': 'audio/mpeg',
            'res_model': 'nepali.tts',
            'res_id': record.id,
            'public': False,
        })

        clip_num = request.env['nepali.tts'].search_count([('state', '=', 'generated')]) + 1
        clip_name = f"Clip #{clip_num} – {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        record.sudo().write({
            'audio_attachment_id': attachment.id,
            'state': 'generated',
            'name': clip_name,
        })

        return {
            'url': f'/web/content/{attachment.id}?download=false',
            'name': clip_name,
        }
