import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduClassroom(models.Model):
    """Extend edu.classroom with exam paper count and smart button."""

    _inherit = 'edu.classroom'

    exam_paper_count = fields.Integer(
        string='Exam Papers',
        compute='_compute_exam_paper_count',
        store=False,
    )
    marks_entry_count = fields.Integer(
        string='Marks Entry',
        compute='_compute_marks_entry_count',
        store=False,
    )

    def _paper_domain(self, extra=None):
        """Base domain to match exam papers for this classroom.

        Papers are batch-level — classroom_id is optional and often unset.
        Match by batch_id + curriculum_line_id instead.
        """
        domain = [
            ('batch_id', '=', self.batch_id.id),
            ('curriculum_line_id', '=', self.curriculum_line_id.id),
        ]
        if extra:
            domain += extra
        return domain

    def _compute_exam_paper_count(self):
        for rec in self:
            rec.exam_paper_count = self.env['edu.exam.paper'].search_count(
                rec._paper_domain()
            )

    def _compute_marks_entry_count(self):
        for rec in self:
            rec.marks_entry_count = self.env['edu.exam.paper'].search_count(
                rec._paper_domain([('state', '=', 'marks_entry')])
            )

    def action_view_exam_papers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Papers — %s') % self.name,
            'res_model': 'edu.exam.paper',
            'view_mode': 'list,form',
            'domain': self._paper_domain(),
            'context': {
                'default_batch_id': self.batch_id.id,
                'default_section_id': self.section_id.id,
                'default_curriculum_line_id': self.curriculum_line_id.id,
                'default_program_term_id': self.program_term_id.id,
                'default_teacher_id': self.teacher_id.id,
            },
        }

    def action_marks_entry(self):
        """Open marks entry for this classroom's subject/batch exam paper.

        Papers are batch-level so we match on batch_id + curriculum_line_id.
        Marksheets are filtered to this classroom's section so each teacher
        only sees their own students.
        """
        self.ensure_one()
        papers = self.env['edu.exam.paper'].search(
            self._paper_domain([('state', '=', 'marks_entry')])
        )
        if not papers:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Marks Entry Open'),
                    'message': _(
                        'No exam paper for "%s" is currently open for marks entry.'
                    ) % self.name,
                    'type': 'warning',
                    'sticky': False,
                },
            }
        # Open the marksheet entry list filtered to this section
        paper_ids = papers.ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marks Entry — %s') % self.name,
            'res_model': 'edu.exam.marksheet',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('edu_exam.view_edu_exam_marksheet_entry_list').id, 'list'),
                (False, 'form'),
            ],
            'domain': [
                ('exam_paper_id', 'in', paper_ids),
                ('section_id', '=', self.section_id.id),
                ('is_latest_attempt', '=', True),
            ],
            'context': {
                'default_section_id': self.section_id.id,
                'marks_entry_mode': True,
            },
        }
