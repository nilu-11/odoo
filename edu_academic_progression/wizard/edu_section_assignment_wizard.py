import logging
from collections import defaultdict
from datetime import date as dt_date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EduSectionAssignmentWizard(models.TransientModel):
    """Bulk section assignment wizard for students within a batch.

    Two-step flow
    ─────────────
    Step 1 — Configuration (wizard_state='config'):
        Select batch, program term, target sections, assignment method and
        options. Click "Generate Preview".

    Step 2 — Preview (wizard_state='preview'):
        Inspect the generated assignment lines. Each line can be adjusted
        manually before confirming. Click "Confirm Assignment" to apply.

    Scope of changes
    ────────────────
    ONLY ``edu.student.progression.history.section_id`` is modified.
    Enrollment records and the student core record are never touched.

    Downstream integration (classrooms, attendance, exams, results) derives
    its student lists from active progression history records automatically —
    no additional action is required after applying this wizard.

    Scalability
    ───────────
    Designed for 100–500 students.  Distribution logic uses Python-level
    sorting (one ORM read, no N+1 queries).  The apply step groups writes
    by target section so the DB round-trips equal the number of distinct
    sections, not the number of students.
    """

    _name = 'edu.section.assignment.wizard'
    _description = 'Bulk Section Assignment Wizard'

    # ══════════════════════════════════════════════════════
    # Step 1 — Configuration fields
    # ══════════════════════════════════════════════════════

    batch_id = fields.Many2one(
        'edu.batch', string='Batch',
        required=True, ondelete='cascade',
        domain=[('state', '=', 'active')],
        default=lambda self: self.env.context.get('default_batch_id'),
    )
    batch_program_id = fields.Many2one(
        'edu.program',
        related='batch_id.program_id',
        string='Program', readonly=True, store=False,
    )
    program_term_id = fields.Many2one(
        'edu.program.term', string='Program Term',
        required=True,
        domain="[('program_id', '=', batch_program_id)]",
        help='Progression term for which to assign sections. '
             'Auto-filled from the batch current term.',
    )

    section_ids = fields.Many2many(
        'edu.section',
        'edu_section_assignment_wiz_section_rel',
        'wizard_id', 'section_id',
        string='Target Sections',
        required=True,
        domain="[('batch_id', '=', batch_id)]",
        help='Sections to distribute students across.',
    )

    assignment_method = fields.Selection([
        ('alphabetical',    'Alphabetical (by student name)'),
        ('enrollment_date', 'Enrollment Date'),
        ('roll_number',     'Roll Number'),
        ('round_robin',     'Round Robin'),
        ('manual',          'Manual Assignment'),
    ], string='Assignment Method', required=True, default='alphabetical',
       help='Determines how students are sorted and distributed across sections.\n'
            '• Alphabetical / Enrollment Date / Roll Number: balanced distribution '
            'after sorting.\n'
            '• Round Robin: students are assigned sequentially across sections '
            '(A→B→C→A→…).\n'
            '• Manual: lines are generated without pre-assigning sections; '
            'set each student\'s section in the preview table.',
    )

    sort_order = fields.Selection([
        ('asc',  'Ascending (A→Z / Oldest→Newest / Low→High)'),
        ('desc', 'Descending (Z→A / Newest→Oldest / High→Low)'),
    ], string='Sort Order', required=True, default='asc',
       help='Direction in which students are sorted before being distributed.',
    )

    respect_capacity = fields.Boolean(
        string='Respect Section Capacity',
        default=False,
        help='When enabled, sections are filled sequentially up to their '
             'capacity before moving to the next. Sections with capacity = 0 '
             'are treated as unlimited. The wizard will error if students '
             'cannot fit into the available capacity.',
    )
    clear_existing_section = fields.Boolean(
        string='Include Already-Assigned Students',
        default=False,
        help='When enabled, students who already have a section will be '
             'included and potentially reassigned. If they have existing '
             'attendance or exam records, a Section Assignment Administrator '
             'is required to override.',
    )
    only_unassigned_students = fields.Boolean(
        string='Unassigned Students Only',
        default=True,
        help='When enabled (default), only students without a current section '
             'are included. Enabling this overrides "Include Already-Assigned '
             'Students".',
    )

    # ══════════════════════════════════════════════════════
    # Wizard state control
    # ══════════════════════════════════════════════════════

    wizard_state = fields.Selection([
        ('config',  'Configuration'),
        ('preview', 'Preview'),
    ], string='Wizard Step', default='config', required=True)

    # ══════════════════════════════════════════════════════
    # Step 2 — Preview lines
    # ══════════════════════════════════════════════════════

    line_ids = fields.One2many(
        'edu.section.assignment.wizard.line', 'wizard_id',
        string='Student Assignments',
    )

    # ── Summary (computed from lines) ─────────────────────────────────────────

    student_count = fields.Integer(
        string='Total Students',
        compute='_compute_summary', store=False,
    )
    reassignment_count = fields.Integer(
        string='Reassignments',
        compute='_compute_summary', store=False,
    )
    blocked_count = fields.Integer(
        string='Require Admin Override',
        compute='_compute_summary', store=False,
    )

    @api.depends('line_ids', 'line_ids.is_reassignment', 'line_ids.has_dependent_records')
    def _compute_summary(self):
        for wiz in self:
            lines = wiz.line_ids
            wiz.student_count = len(lines)
            reassign = lines.filtered('is_reassignment')
            wiz.reassignment_count = len(reassign)
            wiz.blocked_count = len(reassign.filtered('has_dependent_records'))

    # ══════════════════════════════════════════════════════
    # Onchange
    # ══════════════════════════════════════════════════════

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        if self.batch_id:
            self.program_term_id = self.batch_id.current_program_term_id
        else:
            self.program_term_id = False
        self.section_ids = [(5, 0, 0)]

    @api.onchange('only_unassigned_students')
    def _onchange_only_unassigned(self):
        """Enabling unassigned-only implicitly disables the reassignment flag."""
        if self.only_unassigned_students:
            self.clear_existing_section = False

    @api.onchange('clear_existing_section')
    def _onchange_clear_existing(self):
        """Enabling reassignment implicitly disables the unassigned-only flag."""
        if self.clear_existing_section:
            self.only_unassigned_students = False

    # ══════════════════════════════════════════════════════
    # Internal — Configuration validation
    # ══════════════════════════════════════════════════════

    def _validate_configuration(self):
        """Raise UserError / ValidationError if inputs cannot produce a preview."""
        self.ensure_one()

        if not self.section_ids:
            raise UserError(_('Select at least one target section before generating a preview.'))

        if not self.program_term_id:
            raise UserError(_(
                'Select a program term, or set "Current Progression" on '
                'batch "%s" first.'
            ) % self.batch_id.name)

        invalid_sections = self.section_ids.filtered(
            lambda s: s.batch_id != self.batch_id
        )
        if invalid_sections:
            raise ValidationError(_(
                'The following sections do not belong to batch "%s": %s'
            ) % (
                self.batch_id.name,
                ', '.join(invalid_sections.mapped('full_label')),
            ))

        if self.program_term_id.program_id != self.batch_id.program_id:
            raise ValidationError(_(
                'Program term "%s" does not belong to program "%s".'
            ) % (self.program_term_id.name, self.batch_id.program_id.name))

    # ══════════════════════════════════════════════════════
    # Internal — Student fetching
    # ══════════════════════════════════════════════════════

    def _get_eligible_histories(self):
        """Return active progression histories eligible for this assignment run.

        Logic:
        • Always filtered to batch + program_term + state=active.
        • Students with an existing section are included only when
          ``clear_existing_section=True`` AND ``only_unassigned_students=False``.
        """
        self.ensure_one()
        domain = [
            ('batch_id', '=', self.batch_id.id),
            ('program_term_id', '=', self.program_term_id.id),
            ('state', '=', 'active'),
        ]
        include_assigned = (
            self.clear_existing_section and not self.only_unassigned_students
        )
        if not include_assigned:
            domain.append(('section_id', '=', False))

        return self.env['edu.student.progression.history'].search(
            domain, order='id'
        )

    # ══════════════════════════════════════════════════════
    # Internal — Sorting
    # ══════════════════════════════════════════════════════

    def _sort_histories(self, histories):
        """Return a sorted Python list of progression history records.

        round_robin and manual preserve the search order (stable by id).
        """
        reverse = self.sort_order == 'desc'
        method = self.assignment_method

        if method == 'alphabetical':
            return sorted(
                histories,
                key=lambda h: (h.student_id.display_name or '').lower(),
                reverse=reverse,
            )
        if method == 'enrollment_date':
            return sorted(
                histories,
                key=lambda h: h.enrollment_id.enrollment_date or dt_date.min,
                reverse=reverse,
            )
        if method == 'roll_number':
            return sorted(
                histories,
                key=lambda h: h.student_id.roll_number or '',
                reverse=reverse,
            )
        # round_robin, manual — preserve stable id-order from the search
        return list(histories)

    # ══════════════════════════════════════════════════════
    # Internal — Distribution
    # ══════════════════════════════════════════════════════

    def _distribute_students(self, sorted_histories, sections):
        """Assign histories to sections; return list of (history, section) pairs.

        Balanced distribution example:
            63 students, 2 sections → 32 + 31
            63 students, 3 sections → 21 + 21 + 21

        Raises UserError if capacity=True and students cannot fit.
        """
        students = list(sorted_histories)
        section_list = list(sections)
        n = len(students)
        m = len(section_list)

        if not students or not section_list:
            return []

        if self.assignment_method == 'round_robin':
            # Assign sequentially: A→B→C→A→B→C→…
            return [(students[i], section_list[i % m]) for i in range(n)]

        if self.respect_capacity:
            return self._fill_by_capacity(students, section_list)

        # Balanced distribution: extra students go to the earlier sections
        base, remainder = divmod(n, m)
        assignments = []
        idx = 0
        for i, section in enumerate(section_list):
            count = base + (1 if i < remainder else 0)
            for hist in students[idx: idx + count]:
                assignments.append((hist, section))
            idx += count
        return assignments

    def _fill_by_capacity(self, students, sections):
        """Fill sections sequentially respecting their capacity limits.

        Sections with capacity=0 are treated as unlimited.
        Raises UserError if students remain after exhausting all sections.
        """
        assignments = []
        remaining = list(students)

        for section in sections:
            if not remaining:
                break
            cap = section.capacity
            current = section.current_student_count
            # capacity=0 means unlimited: take as many as needed
            available = (cap - current) if cap > 0 else len(remaining)
            if available <= 0:
                continue  # section already at capacity
            take = min(available, len(remaining))
            for hist in remaining[:take]:
                assignments.append((hist, section))
            remaining = remaining[take:]

        if remaining:
            raise UserError(_(
                '%d student(s) could not be assigned: all selected sections '
                'are at or above capacity.\n\n'
                'Options:\n'
                '  • Increase section capacity.\n'
                '  • Add more sections to the selection.\n'
                '  • Disable "Respect Section Capacity".'
            ) % len(remaining))

        return assignments

    # ══════════════════════════════════════════════════════
    # Internal — Capacity validation at apply time
    # ══════════════════════════════════════════════════════

    def _validate_capacity_on_apply(self):
        """Re-validate capacity after the user may have edited lines manually.

        Net-change approach: accounts for students moving between sections
        (leaving their old section frees a slot; entering the new section
        consumes one).
        """
        net_change: dict[int, int] = defaultdict(int)
        for line in self.line_ids:
            if line.old_section_id:
                net_change[line.old_section_id.id] -= 1
            if line.new_section_id:
                net_change[line.new_section_id.id] += 1

        errors = []
        for section in self.section_ids:
            if section.capacity > 0:
                final = section.current_student_count + net_change.get(section.id, 0)
                if final > section.capacity:
                    errors.append(_(
                        '  • %s: projected %d student(s), capacity %d '
                        '(overflow +%d)'
                    ) % (
                        section.full_label, final,
                        section.capacity, final - section.capacity,
                    ))

        if errors:
            raise UserError(
                _('Capacity exceeded — adjust assignments before confirming:\n')
                + '\n'.join(errors)
            )

    # ══════════════════════════════════════════════════════
    # Main wizard actions
    # ══════════════════════════════════════════════════════

    def action_generate_preview(self):
        """Validate configuration, compute assignments, transition to preview step."""
        self.ensure_one()
        self._validate_configuration()

        histories = self._get_eligible_histories()
        if not histories:
            raise UserError(_(
                'No eligible students found for batch "%s" / term "%s".\n\n'
                'Possible causes:\n'
                '  • No active progression records for this batch/term.\n'
                '  • "Unassigned Students Only" is on, but all students '
                'already have sections.\n'
                '  • "Include Already-Assigned Students" is off and there '
                'are no unassigned students.'
            ) % (self.batch_id.name, self.program_term_id.name))

        sorted_histories = self._sort_histories(histories)
        assignments = self._distribute_students(sorted_histories, self.section_ids)

        vals_list = []
        for seq, (hist, section) in enumerate(assignments, start=1):
            vals_list.append({
                'wizard_id': self.id,
                'student_id': hist.student_id.id,
                'enrollment_id': hist.enrollment_id.id if hist.enrollment_id else False,
                'progression_history_id': hist.id,
                'old_section_id': hist.section_id.id if hist.section_id else False,
                # Manual method: leave section empty — user fills in the table
                'new_section_id': (
                    section.id if self.assignment_method != 'manual' else False
                ),
                'sequence_no': seq,
            })

        # Atomically replace any previous lines, then write the new ones
        self.line_ids.unlink()
        self.env['edu.section.assignment.wizard.line'].create(vals_list)
        self.wizard_state = 'preview'

        # Re-open the same wizard record so the view refreshes to preview state
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_back_to_config(self):
        """Discard preview lines and return to the configuration step."""
        self.ensure_one()
        self.line_ids.unlink()
        self.wizard_state = 'config'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_apply(self):
        """Apply the section assignments.

        Writes ``section_id`` on each progression history record grouped by
        target section (batch write — one SQL UPDATE per distinct section).

        Post-conditions:
        • Classrooms automatically reflect the updated student lists.
        • New attendance sheets and exam marksheets will include the students.
        • Existing attendance/exam records are NOT modified.
        """
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_(
                'No assignments to apply. Click "Generate Preview" first.'
            ))

        # Every line must have a target section (critical for manual mode)
        unassigned = self.line_ids.filtered(lambda l: not l.new_section_id)
        if unassigned:
            raise UserError(_(
                '%d student(s) have no target section assigned.\n'
                'Assign a section to every student before confirming.'
            ) % len(unassigned))

        # Reassignment guard — admin required when dependent records exist
        is_admin = self.env.user.has_group(
            'edu_academic_progression.group_section_assignment_admin'
        )
        if not is_admin:
            blocked = self.line_ids.filtered(
                lambda l: l.is_reassignment and l.has_dependent_records
            )
            if blocked:
                preview = blocked[:5].mapped('student_id.display_name')
                label = ', '.join(preview)
                if len(blocked) > 5:
                    label += _(' … and %d more') % (len(blocked) - 5)
                raise UserError(_(
                    '%d student(s) already have attendance or exam records '
                    'linked to their current section.\n\n'
                    'A <b>Section Assignment Administrator</b> is required '
                    'to authorise this reassignment.\n\n'
                    'Affected students: %s'
                ) % (len(blocked), label))

        # Capacity re-validation (user may have edited lines since preview)
        if self.respect_capacity:
            self._validate_capacity_on_apply()

        # All target sections must belong to the wizard's batch
        invalid = self.line_ids.filtered(
            lambda l: l.new_section_id
            and l.new_section_id.batch_id != self.batch_id
        )
        if invalid:
            raise ValidationError(_(
                'Some target sections do not belong to batch "%s". '
                'Correct the affected lines before confirming.'
            ) % self.batch_id.name)

        # ── Apply: batch write grouped by target section ──────────────────────
        section_to_history_ids: dict[int, list[int]] = defaultdict(list)
        for line in self.line_ids:
            section_to_history_ids[line.new_section_id.id].append(
                line.progression_history_id.id
            )

        ProgressionHistory = self.env['edu.student.progression.history']
        for sec_id, hist_ids in section_to_history_ids.items():
            ProgressionHistory.browse(hist_ids).write({'section_id': sec_id})

        # Also update the student record's section_id so it stays in sync
        Student = self.env['edu.student']
        student_section_map: dict[int, list[int]] = defaultdict(list)
        for line in self.line_ids:
            student_section_map[line.new_section_id.id].append(line.student_id.id)
        for sec_id, student_ids in student_section_map.items():
            Student.browse(student_ids).write({'section_id': sec_id})

        # ── Audit trail on the batch ──────────────────────────────────────────
        method_label = dict(self._fields['assignment_method'].selection).get(
            self.assignment_method, self.assignment_method
        )
        section_distribution = ' &nbsp;|&nbsp; '.join(
            '%s: <b>%d</b>' % (
                s.name,
                sum(1 for l in self.line_ids if l.new_section_id == s),
            )
            for s in self.section_ids
        )
        self.batch_id.message_post(
            body=_(
                '<b>Section Assignment Applied</b><br/>'
                'Method: %s &nbsp;|&nbsp; '
                'Total students: <b>%d</b><br/>'
                'Distribution — %s'
            ) % (method_label, len(self.line_ids), section_distribution),
            subtype_xmlid='mail.mt_note',
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Section Assignment Applied'),
                'message': _(
                    '%d student(s) successfully assigned to sections in batch "%s".'
                ) % (len(self.line_ids), self.batch_id.name),
                'type': 'success',
                'sticky': False,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# Wizard Line
# ═══════════════════════════════════════════════════════════════════════════

class EduSectionAssignmentWizardLine(models.TransientModel):
    """One line per student-to-section assignment in the preview.

    Users may edit ``new_section_id`` on any line before confirming.
    The domain on ``new_section_id`` is restricted to the wizard's batch
    via the stored ``batch_id`` related field.
    """

    _name = 'edu.section.assignment.wizard.line'
    _description = 'Section Assignment Wizard Line'
    _order = 'sequence_no, student_id'

    wizard_id = fields.Many2one(
        'edu.section.assignment.wizard', string='Wizard',
        required=True, ondelete='cascade', index=True,
    )

    # ── Student context ───────────────────────────────────────────────────────

    student_id = fields.Many2one(
        'edu.student', string='Student',
        required=True, ondelete='cascade', index=True,
    )
    enrollment_id = fields.Many2one(
        'edu.enrollment', string='Enrollment',
        ondelete='set null', index=True,
    )
    progression_history_id = fields.Many2one(
        'edu.student.progression.history', string='Progression Record',
        required=True, ondelete='cascade', index=True,
    )

    # ── Section assignment ────────────────────────────────────────────────────

    old_section_id = fields.Many2one(
        'edu.section', string='Current Section',
        ondelete='set null', readonly=True,
        help='Section assigned before this wizard run (read-only).',
    )
    new_section_id = fields.Many2one(
        'edu.section', string='Assigned Section',
        ondelete='set null',
        domain="[('batch_id', '=', batch_id)]",
        help='Target section after confirming this assignment. Editable.',
    )

    # Stored related so the domain on new_section_id resolves correctly
    batch_id = fields.Many2one(
        'edu.batch',
        related='wizard_id.batch_id',
        store=True, string='Batch',
    )

    # ── Display helpers ───────────────────────────────────────────────────────

    roll_number = fields.Char(
        related='student_id.roll_number',
        string='Roll No.', store=False,
    )
    sequence_no = fields.Integer(string='Seq.')

    # ── Computed flags ────────────────────────────────────────────────────────

    is_reassignment = fields.Boolean(
        string='Reassignment?',
        compute='_compute_flags', store=False,
        help='True when the student already has a section before this wizard.',
    )
    has_dependent_records = fields.Boolean(
        string='Has Records',
        compute='_compute_flags', store=False,
        help='True when attendance or exam records exist for this progression '
             'history. Reassigning requires a Section Assignment Administrator.',
    )

    @api.depends('old_section_id', 'progression_history_id')
    def _compute_flags(self):
        """Batch-compute reassignment and dependency flags.

        Uses at most 2 additional DB queries regardless of the number of lines,
        making this efficient for 100–500 student wizards.
        """
        for line in self:
            line.is_reassignment = bool(line.old_section_id)

        history_ids = self.mapped('progression_history_id').ids
        if not history_ids:
            for line in self:
                line.has_dependent_records = False
            return

        dependent_ids: set[int] = set()

        # ── Attendance sheet lines (edu_attendance — optional) ────────────────
        att_model = self.env.get('edu.attendance.sheet.line')
        if att_model is not None:
            try:
                att_data = att_model._read_group(
                    domain=[
                        ('student_progression_history_id', 'in', history_ids)
                    ],
                    groupby=['student_progression_history_id'],
                    aggregates=['__count'],
                )
                for hist, _count in att_data:
                    dependent_ids.add(hist.id)
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    'edu_section_assignment: could not check attendance '
                    'dependency (skipping): %s', exc,
                )

        # ── Exam marksheets (edu_exam — optional) ─────────────────────────────
        exam_model = self.env.get('edu.exam.marksheet')
        if exam_model is not None:
            try:
                exam_data = exam_model._read_group(
                    domain=[
                        ('student_progression_history_id', 'in', history_ids)
                    ],
                    groupby=['student_progression_history_id'],
                    aggregates=['__count'],
                )
                for hist, _count in exam_data:
                    dependent_ids.add(hist.id)
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    'edu_section_assignment: could not check exam '
                    'dependency (skipping): %s', exc,
                )

        for line in self:
            line.has_dependent_records = (
                line.progression_history_id.id in dependent_ids
            )
