import base64
import io
import logging
from collections import defaultdict

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

_logger = logging.getLogger(__name__)

STATUS_SYMBOLS = {
    'present': 'P',
    'absent': 'A',
    'late': 'L',
    'excused': 'E',
}

STATUS_LABELS = {
    'present': 'Present',
    'absent': 'Absent',
    'late': 'Late',
    'excused': 'Excused',
}

STATUS_COLORS = {
    'present': '#d4edda',
    'absent': '#f8d7da',
    'late': '#fff3cd',
    'excused': '#d1ecf1',
}


class EduAttendanceMatrixReportWizard(models.TransientModel):
    """Attendance matrix report: rows = students, columns = dates, cells = status.

    Supports both HTML preview (rendered inline) and XLSX download.
    """

    _name = 'edu.attendance.matrix.report.wizard'
    _description = 'Attendance Matrix Report'

    # ═══ Filter Fields ═══

    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
    )
    student_ids = fields.Many2many(
        comodel_name='edu.student',
        string='Students',
    )
    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=fields.Date.today,
    )
    status_display = fields.Selection(
        selection=[
            ('symbol', 'Symbol (P / A / L / E)'),
            ('full_text', 'Full Text'),
        ],
        string='Status Display',
        default='symbol',
        required=True,
    )

    # ═══ State & Output ═══

    state = fields.Selection(
        selection=[
            ('config', 'Configure'),
            ('result', 'Result'),
        ],
        string='State',
        default='config',
    )
    html_content = fields.Html(
        string='Report Preview',
        sanitize=False,
        readonly=True,
    )
    xlsx_file = fields.Binary(
        string='Excel File',
        readonly=True,
    )
    xlsx_filename = fields.Char(string='Filename')

    # ═══ Onchanges ═══

    @api.onchange('classroom_id')
    def _onchange_classroom_id(self):
        if self.classroom_id:
            self.batch_id = self.classroom_id.batch_id
            self.section_id = self.classroom_id.section_id
            self.program_term_id = self.classroom_id.program_term_id

    # ═══ Actions ═══

    def action_generate(self):
        """Generate both HTML preview and XLSX file from attendance data."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('Date From must be before or equal to Date To.'))

        data = self._fetch_matrix_data()
        self.html_content = self._render_html_matrix(data)
        self._generate_xlsx(data)
        self.state = 'result'
        return self._reopen_wizard()

    def action_back(self):
        """Return to the configuration state."""
        self.ensure_one()
        self.write({
            'state': 'config',
            'html_content': False,
            'xlsx_file': False,
            'xlsx_filename': False,
        })
        return self._reopen_wizard()

    def action_download_xlsx(self):
        """Download the pre-generated XLSX file."""
        self.ensure_one()
        if not self.xlsx_file:
            data = self._fetch_matrix_data()
            self._generate_xlsx(data)
        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content?model=%s&id=%d'
                '&field=xlsx_file&filename_field=xlsx_filename&download=true'
            ) % (self._name, self.id),
            'target': 'self',
        }

    def _reopen_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    # ═══ Data Fetching ═══

    def _fetch_matrix_data(self):
        """Return {'students': [...], 'dates': [...], 'matrix': {sid: {date: status}}}."""
        self.ensure_one()
        domain = [
            ('sheet_state', '=', 'submitted'),
            ('session_date', '>=', self.date_from),
            ('session_date', '<=', self.date_to),
        ]

        if self.classroom_id:
            domain.append(('classroom_id', '=', self.classroom_id.id))
        else:
            # Build a register-level pre-filter for batch / section / term
            reg_domain = []
            if self.batch_id:
                reg_domain.append(('batch_id', '=', self.batch_id.id))
            if self.section_id:
                reg_domain.append(('section_id', '=', self.section_id.id))
            if self.program_term_id:
                reg_domain.append(('program_term_id', '=', self.program_term_id.id))
            if reg_domain:
                registers = self.env['edu.attendance.register'].search(reg_domain)
                if registers:
                    domain.append(('register_id', 'in', registers.ids))
                else:
                    # No matching registers → return empty
                    return {'students': [], 'dates': [], 'matrix': defaultdict(dict)}

        if self.student_ids:
            domain.append(('student_id', 'in', self.student_ids.ids))

        lines = self.env['edu.attendance.sheet.line'].search(domain)

        # Build matrix in a single pass — O(n) over lines
        students = {}
        dates = set()
        matrix = defaultdict(dict)

        for line in lines:
            sid = line.student_id.id
            if sid not in students:
                students[sid] = {
                    'id': sid,
                    'name': line.student_id.name,
                    'roll_number': line.roll_number or '',
                }
            dates.add(line.session_date)
            matrix[sid][line.session_date] = line.status

        sorted_dates = sorted(dates)
        sorted_students = sorted(
            students.values(),
            key=lambda s: (s['roll_number'], s['name']),
        )

        return {
            'students': sorted_students,
            'dates': sorted_dates,
            'matrix': matrix,
        }

    # ═══ HTML Rendering ═══

    def _render_html_matrix(self, data):
        students = data['students']
        dates = data['dates']
        matrix = data['matrix']
        use_symbols = self.status_display == 'symbol'
        status_map = STATUS_SYMBOLS if use_symbols else STATUS_LABELS

        if not students or not dates:
            return Markup(
                '<div class="alert alert-info">'
                'No submitted attendance data found for the selected criteria.'
                '</div>'
            )

        parts = []
        parts.append('<div style="overflow-x:auto;">')
        parts.append(
            '<table class="table table-bordered table-sm text-center"'
            ' style="font-size:0.85em;white-space:nowrap;">'
        )

        # ── Header row ────────────────────────────────────────────────────
        parts.append('<thead class="table-dark"><tr>')
        parts.append(
            '<th class="text-start"'
            ' style="position:sticky;left:0;z-index:1;background:#343a40;">'
            'Student</th>'
        )
        parts.append('<th>Roll No</th>')
        for d in dates:
            parts.append('<th>%s</th>' % escape(d.strftime('%d/%m')))
        for hdr in ('P', 'A', 'L', 'E', '%'):
            parts.append('<th>%s</th>' % hdr)
        parts.append('</tr></thead>')

        # ── Body rows ─────────────────────────────────────────────────────
        parts.append('<tbody>')
        for stu in students:
            sid = stu['id']
            parts.append('<tr>')
            parts.append(
                '<td class="text-start" style="position:sticky;left:0;'
                'background:#fff;font-weight:500;">%s</td>' % escape(stu['name'])
            )
            parts.append('<td>%s</td>' % escape(stu['roll_number']))

            pcnt = acnt = lcnt = ecnt = 0
            for d in dates:
                status = matrix[sid].get(d)
                if status:
                    pcnt += status == 'present'
                    acnt += status == 'absent'
                    lcnt += status == 'late'
                    ecnt += status == 'excused'
                    label = status_map.get(status, '-')
                    color = STATUS_COLORS.get(status, '#ffffff')
                    parts.append(
                        '<td style="background-color:%s;">%s</td>' % (color, escape(label))
                    )
                else:
                    parts.append('<td style="color:#ccc;">-</td>')

            total = pcnt + acnt + lcnt + ecnt
            effective = pcnt + lcnt
            pct = round(effective / total * 100, 1) if total else 0.0
            pct_color = '#28a745' if pct >= 75 else '#dc3545'

            parts.append('<td class="fw-bold">%d</td>' % pcnt)
            parts.append(
                '<td class="fw-bold" style="color:#dc3545;">%d</td>' % acnt
            )
            parts.append(
                '<td class="fw-bold" style="color:#ffc107;">%d</td>' % lcnt
            )
            parts.append(
                '<td class="fw-bold" style="color:#17a2b8;">%d</td>' % ecnt
            )
            parts.append(
                '<td class="fw-bold" style="color:%s;">%.1f%%</td>'
                % (pct_color, pct)
            )
            parts.append('</tr>')

        parts.append('</tbody></table></div>')
        return Markup(''.join(parts))

    # ═══ XLSX Generation ═══

    def _generate_xlsx(self, data):
        if xlsxwriter is None:
            raise UserError(
                _('The xlsxwriter library is not installed. '
                  'Cannot generate the Excel file.')
            )

        students = data['students']
        dates = data['dates']
        matrix = data['matrix']
        use_symbols = self.status_display == 'symbol'
        status_map = STATUS_SYMBOLS if use_symbols else STATUS_LABELS

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Attendance Matrix')

        # ── Formats ───────────────────────────────────────────────────────
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14,
            'align': 'center', 'valign': 'vcenter',
        })
        info_fmt = workbook.add_format({'italic': True})
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#343a40', 'font_color': '#ffffff',
            'align': 'center', 'valign': 'vcenter', 'border': 1,
        })
        student_fmt = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter', 'border': 1,
        })
        center_fmt = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1,
        })
        present_fmt = workbook.add_format({
            'align': 'center', 'bg_color': '#d4edda', 'border': 1,
        })
        absent_fmt = workbook.add_format({
            'align': 'center', 'bg_color': '#f8d7da',
            'font_color': '#721c24', 'border': 1,
        })
        late_fmt = workbook.add_format({
            'align': 'center', 'bg_color': '#fff3cd',
            'font_color': '#856404', 'border': 1,
        })
        excused_fmt = workbook.add_format({
            'align': 'center', 'bg_color': '#d1ecf1',
            'font_color': '#0c5460', 'border': 1,
        })
        empty_fmt = workbook.add_format({
            'align': 'center', 'font_color': '#cccccc', 'border': 1,
        })
        summary_fmt = workbook.add_format({
            'bold': True, 'align': 'center', 'border': 1,
        })
        pct_fmt = workbook.add_format({
            'bold': True, 'align': 'center', 'border': 1,
            'num_format': '0.0%',
        })
        status_formats = {
            'present': present_fmt,
            'absent': absent_fmt,
            'late': late_fmt,
            'excused': excused_fmt,
        }

        # ── Title rows ────────────────────────────────────────────────────
        row = 0
        title = 'Attendance Matrix Report'
        if self.classroom_id:
            title += ' — %s' % self.classroom_id.name
        ws.merge_range(row, 0, row, min(5, 1 + len(dates)), title, title_fmt)
        row += 1
        ws.write(row, 0, 'Period: %s to %s' % (self.date_from, self.date_to), info_fmt)
        if self.batch_id:
            ws.write(row, 3, 'Batch: %s' % self.batch_id.name, info_fmt)
        if self.section_id:
            ws.write(row, 5, 'Section: %s' % self.section_id.name, info_fmt)
        row += 2

        # ── Column headers ────────────────────────────────────────────────
        col = 0
        ws.write(row, col, 'Student', header_fmt)
        ws.set_column(col, col, 28)
        col += 1
        ws.write(row, col, 'Roll No', header_fmt)
        ws.set_column(col, col, 10)
        col += 1
        for d in dates:
            ws.write(row, col, d.strftime('%d/%m'), header_fmt)
            ws.set_column(col, col, 7)
            col += 1
        summary_col = col
        for hdr in ('P', 'A', 'L', 'E'):
            ws.write(row, col, hdr, header_fmt)
            ws.set_column(col, col, 5)
            col += 1
        ws.write(row, col, '%', header_fmt)
        ws.set_column(col, col, 7)
        row += 1

        # ── Data rows ─────────────────────────────────────────────────────
        for stu in students:
            sid = stu['id']
            col = 0
            ws.write(row, col, stu['name'], student_fmt)
            col += 1
            ws.write(row, col, stu['roll_number'], center_fmt)
            col += 1

            pcnt = acnt = lcnt = ecnt = 0
            for d in dates:
                status = matrix[sid].get(d)
                if status:
                    pcnt += status == 'present'
                    acnt += status == 'absent'
                    lcnt += status == 'late'
                    ecnt += status == 'excused'
                    label = status_map.get(status, '-')
                    fmt = status_formats.get(status, center_fmt)
                    ws.write(row, col, label, fmt)
                else:
                    ws.write(row, col, '-', empty_fmt)
                col += 1

            total = pcnt + acnt + lcnt + ecnt
            effective = pcnt + lcnt
            pct = effective / total if total else 0.0

            ws.write(row, col, pcnt, summary_fmt)
            col += 1
            ws.write(row, col, acnt, summary_fmt)
            col += 1
            ws.write(row, col, lcnt, summary_fmt)
            col += 1
            ws.write(row, col, ecnt, summary_fmt)
            col += 1
            ws.write(row, col, pct, pct_fmt)
            row += 1

        workbook.close()
        output.seek(0)

        date_str = '%s_to_%s' % (
            self.date_from.strftime('%Y%m%d'),
            self.date_to.strftime('%Y%m%d'),
        )
        if self.classroom_id:
            fname = 'attendance_matrix_%s_%s.xlsx' % (
                (self.classroom_id.code or 'classroom').replace('/', '-'),
                date_str,
            )
        else:
            fname = 'attendance_matrix_%s.xlsx' % date_str

        self.xlsx_file = base64.b64encode(output.read())
        self.xlsx_filename = fname
