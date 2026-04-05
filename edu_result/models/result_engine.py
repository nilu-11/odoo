"""
Result Computation Engine for edu_result.

This is a pure Python service class (not an Odoo model).  It is instantiated
by wizards and action methods to perform scheme-driven result computation.

Design principles:
  - All DB queries are batched upfront to avoid N+1 loops.
  - Computation is deterministic and stateless; the same input always
    produces the same output.
  - The engine never auto-commits; the calling wizard is responsible for
    transaction management.
  - All policy decisions are read from configuration models; nothing is
    hardcoded.
"""

from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class ResultComputeEngine:
    """
    Compute results for a single edu.result.session.

    Usage::

        engine = ResultComputeEngine(result_session)
        engine.compute()
    """

    def __init__(self, result_session):
        self.session = result_session
        self.env = result_session.env
        self.scheme = result_session.assessment_scheme_id
        self.grading_scheme = result_session.grading_scheme_id
        self.result_rule = result_session.result_rule_id
        # Sorted scheme lines (only contributing lines used in final computation)
        self.scheme_lines = self.scheme.line_ids.sorted('sequence')

    # =========================================================================
    # Main entry point
    # =========================================================================

    def compute(self):
        """Compute all results for the session.  Creates/replaces all lines."""
        _logger.info(
            'ResultComputeEngine: starting computation for session %s (%s)',
            self.session.name,
            self.session.id,
        )

        # Step 1 — candidate student list
        progression_histories = self._get_candidate_progression_histories()
        if not progression_histories:
            _logger.warning(
                'ResultComputeEngine: no progression histories found for session %s',
                self.session.name,
            )
            return

        # Step 2 — curriculum lines in scope
        curriculum_lines = self._get_curriculum_lines()
        if not curriculum_lines:
            _logger.warning(
                'ResultComputeEngine: no curriculum lines found for session %s',
                self.session.name,
            )
            return

        # Step 3 — pre-fetch all source data to avoid N+1 queries
        source_cache = self._build_source_cache(
            progression_histories, curriculum_lines
        )

        # Step 4 — wipe previous results for this session
        self._clear_previous_results()

        # Step 5 — compute subject-level results and build subject lines
        subject_line_data = []  # list of (vals_dict, components_list)
        for ph in progression_histories:
            # Determine which curriculum lines this student is actually taking.
            # Fall back to all lines if no elective data has been set (backwards compat).
            if ph.effective_curriculum_line_ids:
                effective = ph.effective_curriculum_line_ids
                student_lines = curriculum_lines.filtered(
                    lambda cl, eff=effective: cl in eff
                )
            else:
                student_lines = curriculum_lines

            for cl in student_lines:
                result = self._compute_subject_result(ph, cl, source_cache)
                if result is None:
                    continue
                vals, components = self._build_subject_line_vals(ph, cl, result)
                subject_line_data.append((vals, components))

        # Step 6 — batch-create subject lines
        self._batch_create_subject_lines(subject_line_data)

        # Step 7 — apply backlog identification
        self._identify_and_flag_backlogs()

        # Step 8 — compute student-level results
        self._compute_all_student_results(progression_histories)

        _logger.info(
            'ResultComputeEngine: computation complete for session %s — '
            '%d subject lines, %d student results',
            self.session.name,
            len(subject_line_data),
            len(progression_histories),
        )

    # =========================================================================
    # Scope resolution
    # =========================================================================

    def _get_candidate_progression_histories(self):
        """Fetch progression histories matching the session scope."""
        domain = []
        s = self.session
        if s.academic_year_id:
            domain.append(('academic_year_id', '=', s.academic_year_id.id))
        if s.program_id:
            domain.append(('program_id', '=', s.program_id.id))
        if s.batch_id:
            domain.append(('batch_id', '=', s.batch_id.id))
        if s.program_term_id:
            domain.append(('program_term_id', '=', s.program_term_id.id))
        # Include active and recently completed (for post-term computation)
        domain.append(('state', 'in', ('active', 'completed', 'promoted')))
        return self.env['edu.student.progression.history'].search(domain)

    def _get_curriculum_lines(self):
        """Fetch curriculum lines relevant to the session scope."""
        domain = []
        s = self.session
        if s.program_id:
            domain.append(('program_id', '=', s.program_id.id))
        if s.program_term_id:
            domain.append(('program_term_id', '=', s.program_term_id.id))
        return self.env['edu.curriculum.line'].search(domain)

    # =========================================================================
    # Source data pre-fetch (avoids N+1 in inner loops)
    # =========================================================================

    def _build_source_cache(self, progression_histories, curriculum_lines):
        """
        Pre-fetch all raw source data and organize into a nested dict.

        Returns:
            {scheme_line_id: {(student_id, curriculum_line_id): [mark_dicts]}}
        """
        student_ids = progression_histories.mapped('student_id').ids
        cl_ids = curriculum_lines.ids

        cache = {}
        for line in self.scheme_lines:
            cache[line.id] = self._fetch_source_for_line(
                line, student_ids, cl_ids
            )
        return cache

    def _fetch_source_for_line(self, scheme_line, student_ids, curriculum_line_ids):
        """
        Fetch source records for one scheme line in batch.

        Returns:
            {(student_id, curriculum_line_id): [{'marks': float, 'max_marks': float, ...}]}
        """
        src = scheme_line.source_type
        if src == 'exam_session':
            return self._fetch_exam_session_marks(
                scheme_line, student_ids, curriculum_line_ids
            )
        elif src == 'exam_component':
            return self._fetch_exam_component_marks(
                scheme_line, student_ids, curriculum_line_ids
            )
        elif src in ('assignment', 'class_test', 'class_performance',
                     'project', 'practical', 'viva', 'custom'):
            return self._fetch_assessment_marks(
                scheme_line, student_ids, curriculum_line_ids
            )
        elif src == 'attendance':
            return self._fetch_attendance_marks(
                scheme_line, student_ids, curriculum_line_ids
            )
        elif src == 'manual':
            return {}  # Manual marks are entered directly on result lines
        elif src == 'board_import':
            return self._fetch_board_import_marks(
                scheme_line, student_ids, curriculum_line_ids
            )
        return {}

    def _fetch_exam_session_marks(self, scheme_line, student_ids, curriculum_line_ids):
        """Fetch from edu.exam.marksheet."""
        domain = [
            ('student_id', 'in', student_ids),
            ('curriculum_line_id', 'in', curriculum_line_ids),
            ('is_latest_attempt', '=', True),
            ('exam_paper_state', 'in', ('published', 'closed')),
        ]

        # Filter by attempt type if configured
        if scheme_line.exam_attempt_type:
            domain.append(('attempt_type', '=', scheme_line.exam_attempt_type))

        # Filter by explicitly linked sessions first
        if scheme_line.exam_session_ids:
            domain.append(
                ('exam_session_id', 'in', scheme_line.exam_session_ids.ids)
            )
        else:
            # Fall back to sessions that reference this scheme line
            linked_sessions = self.env['edu.exam.session'].search([
                ('assessment_scheme_line_id', '=', scheme_line.id),
                ('state', 'in', ('published', 'closed')),
            ])
            if linked_sessions:
                domain.append(
                    ('exam_session_id', 'in', linked_sessions.ids)
                )
            else:
                # Scope by session's assessment scheme
                sessions_by_scheme = self.env['edu.exam.session'].search([
                    ('assessment_scheme_id', '=', scheme_line.scheme_id.id),
                    ('state', 'in', ('published', 'closed')),
                ])
                if not sessions_by_scheme:
                    return {}
                domain.append(
                    ('exam_session_id', 'in', sessions_by_scheme.ids)
                )

        marksheets = self.env['edu.exam.marksheet'].search(domain)
        result = defaultdict(list)
        for ms in marksheets:
            key = (ms.student_id.id, ms.curriculum_line_id.id)
            result[key].append({
                'marks': ms.final_marks or 0.0,
                'max_marks': ms.max_marks or 0.0,
                'status': ms.status,
                'marksheet_id': ms.id,
            })
        return dict(result)

    def _fetch_exam_component_marks(self, scheme_line, student_ids, curriculum_line_ids):
        """Fetch from edu.exam.marksheet.component."""
        # Find marksheets first
        ms_domain = [
            ('student_id', 'in', student_ids),
            ('curriculum_line_id', 'in', curriculum_line_ids),
            ('is_latest_attempt', '=', True),
            ('exam_paper_state', 'in', ('published', 'closed')),
        ]
        if scheme_line.exam_session_ids:
            ms_domain.append(
                ('exam_session_id', 'in', scheme_line.exam_session_ids.ids)
            )

        marksheets = self.env['edu.exam.marksheet'].search(ms_domain)
        if not marksheets:
            return {}

        comp_domain = [('marksheet_id', 'in', marksheets.ids)]
        components = self.env['edu.exam.marksheet.component'].search(comp_domain)

        # Build a lookup: marksheet_id -> (student_id, curriculum_line_id)
        ms_lookup = {
            ms.id: (ms.student_id.id, ms.curriculum_line_id.id)
            for ms in marksheets
        }

        result = defaultdict(list)
        for comp in components:
            key = ms_lookup.get(comp.marksheet_id.id)
            if key:
                result[key].append({
                    'marks': comp.final_marks or 0.0,
                    'max_marks': comp.max_marks or 0.0,
                    'status': comp.status,
                    'component_id': comp.id,
                })
        return dict(result)

    def _fetch_assessment_marks(self, scheme_line, student_ids, curriculum_line_ids):
        """Fetch from edu.continuous.assessment.record."""
        domain = [
            ('student_id', 'in', student_ids),
            ('curriculum_line_id', 'in', curriculum_line_ids),
            ('state', 'in', ('confirmed', 'locked')),
        ]

        if scheme_line.assessment_category_ids:
            domain.append(
                ('category_id', 'in', scheme_line.assessment_category_ids.ids)
            )
        elif scheme_line.source_type in (
            'assignment', 'class_test', 'class_performance',
            'project', 'practical', 'viva',
        ):
            _TYPE_MAP = {
                'assignment': 'assignment',
                'class_test': 'class_test',
                'class_performance': 'class_performance',
                'project': 'project',
                'practical': 'practical',
                'viva': 'viva',
            }
            cat_type = _TYPE_MAP.get(scheme_line.source_type)
            if cat_type:
                domain.append(('category_id.category_type', '=', cat_type))

        records = self.env['edu.continuous.assessment.record'].search(domain)
        result = defaultdict(list)
        for rec in records:
            key = (rec.student_id.id, rec.curriculum_line_id.id)
            result[key].append({
                'marks': rec.marks_obtained or 0.0,
                'max_marks': rec.max_marks or 0.0,
                'record_id': rec.id,
            })
        return dict(result)

    def _fetch_attendance_marks(self, scheme_line, student_ids, curriculum_line_ids):
        """
        Compute attendance percentage per student-subject and convert to marks.

        Attendance is stored per session line.  We group by student +
        curriculum_line (via classroom) and compute present/total ratio.
        """
        # Fetch all submitted attendance lines for these students
        attn_lines = self.env['edu.attendance.sheet.line'].search([
            ('student_id', 'in', student_ids),
            ('sheet_state', '=', 'submitted'),
        ])

        # Group: (student_id, curriculum_line_id) → {present, total}
        totals = defaultdict(lambda: {'present': 0, 'total': 0})
        for line in attn_lines:
            cl_id = line.classroom_id.curriculum_line_id.id \
                if line.classroom_id and line.classroom_id.curriculum_line_id \
                else None
            if cl_id not in curriculum_line_ids:
                continue
            key = (line.student_id.id, cl_id)
            totals[key]['total'] += 1
            if line.status == 'present':
                totals[key]['present'] += 1

        max_marks = scheme_line.max_marks or 10.0
        result = {}
        for key, counts in totals.items():
            if counts['total'] > 0:
                attendance_pct = (counts['present'] / counts['total']) * 100.0
                marks = (attendance_pct / 100.0) * max_marks
                result[key] = [{
                    'marks': round(marks, 4),
                    'max_marks': max_marks,
                    'attendance_percent': attendance_pct,
                }]
        return result

    def _fetch_board_import_marks(self, scheme_line, student_ids, curriculum_line_ids):
        """
        Board marks are fetched from published exam sessions that are flagged
        as board exams.  Uses the same exam marksheet path.
        """
        domain = [
            ('student_id', 'in', student_ids),
            ('curriculum_line_id', 'in', curriculum_line_ids),
            ('is_latest_attempt', '=', True),
            ('exam_session_id.is_board_exam', '=', True),
            ('exam_paper_state', 'in', ('published', 'closed')),
        ]
        if scheme_line.exam_session_ids:
            domain.append(
                ('exam_session_id', 'in', scheme_line.exam_session_ids.ids)
            )
        marksheets = self.env['edu.exam.marksheet'].search(domain)
        result = defaultdict(list)
        for ms in marksheets:
            key = (ms.student_id.id, ms.curriculum_line_id.id)
            result[key].append({
                'marks': ms.final_marks or 0.0,
                'max_marks': ms.max_marks or 0.0,
                'status': ms.status,
                'marksheet_id': ms.id,
            })
        return dict(result)

    # =========================================================================
    # Aggregation helpers
    # =========================================================================

    def _aggregate_marks(self, mark_dicts, method, best_of=0, drop_lowest=0):
        """
        Reduce a list of mark dicts to (obtained, max_marks).

        mark_dicts: [{'marks': float, 'max_marks': float, ...}]
        Returns: (obtained: float, max_total: float)
        """
        if not mark_dicts:
            return 0.0, 0.0

        # Apply drop_lowest before aggregating
        if drop_lowest and len(mark_dicts) > drop_lowest:
            mark_dicts = sorted(mark_dicts, key=lambda x: x['marks'])[drop_lowest:]

        if method == 'total':
            return (
                sum(m['marks'] for m in mark_dicts),
                sum(m['max_marks'] for m in mark_dicts),
            )

        elif method == 'average':
            n = len(mark_dicts)
            max_m = mark_dicts[0]['max_marks'] if mark_dicts else 0.0
            return sum(m['marks'] for m in mark_dicts) / n, max_m

        elif method == 'best':
            n = best_of if best_of else 1
            top_n = sorted(mark_dicts, key=lambda x: x['marks'], reverse=True)[:n]
            return (
                sum(m['marks'] for m in top_n),
                sum(m['max_marks'] for m in top_n),
            )

        elif method == 'latest':
            last = mark_dicts[-1]
            return last['marks'], last['max_marks']

        elif method == 'weighted_average':
            # Treat same as average here (source-level weighting is not supported
            # at this level; scheme-level weightage handles the weighting)
            n = len(mark_dicts)
            max_m = mark_dicts[0]['max_marks'] if mark_dicts else 0.0
            return sum(m['marks'] for m in mark_dicts) / n, max_m

        elif method == 'manual':
            first = mark_dicts[0]
            return first['marks'], first['max_marks']

        # Default: total
        return (
            sum(m['marks'] for m in mark_dicts),
            sum(m['max_marks'] for m in mark_dicts),
        )

    def _normalize(self, obtained, raw_max, target_max):
        """Scale obtained from raw_max to target_max."""
        if not raw_max:
            return 0.0
        return round((obtained / raw_max) * target_max, 6)

    def _weighted_contribution(self, normalized_obtained, target_max, weightage_pct):
        """
        Compute weighted percentage contribution.

        weighted = (normalized / target_max) * weightage_pct
        """
        if not target_max:
            return 0.0
        return round((normalized_obtained / target_max) * weightage_pct, 6)

    # =========================================================================
    # Subject-level computation
    # =========================================================================

    def _compute_subject_result(self, progression_history, curriculum_line, source_cache):
        """
        Compute the result for one student × curriculum_line.

        Returns a result dict or None if no data is available.
        """
        ph = progression_history
        cl = curriculum_line
        student_id = ph.student_id.id
        cl_id = cl.id
        key = (student_id, cl_id)

        components = []
        total_weighted = 0.0
        has_mandatory_fail = False

        # Track special statuses from exam sources
        is_absent = False
        is_withheld = False
        is_malpractice = False

        has_any_data = False

        for line in self.scheme_lines:
            if not line.contributes_to_final:
                continue

            raw_records = source_cache.get(line.id, {}).get(key, [])

            # Detect special exam statuses
            for rec in raw_records:
                status = rec.get('status', '')
                if status == 'absent':
                    is_absent = True
                elif status == 'withheld':
                    is_withheld = True
                elif status == 'malpractice':
                    is_malpractice = True
                if status not in ('absent', 'withheld', 'malpractice'):
                    has_any_data = True

            if raw_records:
                has_any_data = True

            # Drop lowest if configured
            usable = list(raw_records)
            if line.drop_lowest and len(usable) > line.drop_lowest:
                usable = sorted(usable, key=lambda x: x.get('marks', 0))[line.drop_lowest:]

            obtained, raw_max = self._aggregate_marks(
                usable,
                line.aggregation_method,
                best_of=line.best_of_count or 0,
                drop_lowest=0,  # already dropped above
            )

            # Normalize to scheme line scale
            target_max = line.max_marks or 100.0
            normalized = self._normalize(obtained, raw_max, target_max)

            # Weighted contribution towards final percentage
            weighted = self._weighted_contribution(
                normalized, target_max, line.weightage_percent or 0.0
            )

            # Component-level pass check
            line_pass = True
            if line.requires_separate_pass and line.pass_marks:
                line_pass = normalized >= line.pass_marks

            if line.is_mandatory and not line_pass and raw_records:
                has_mandatory_fail = True

            total_weighted += weighted

            components.append({
                'scheme_line_id': line.id,
                'scheme_line_name': line.name,
                'raw_obtained': obtained,
                'raw_max': raw_max,
                'normalized_obtained': normalized,
                'normalized_max': target_max,
                'weighted_contribution': weighted,
                'weightage_percent': line.weightage_percent or 0.0,
                'is_pass': line_pass,
                'is_mandatory': line.is_mandatory,
                'records_count': len(raw_records),
            })

        if not has_any_data and not is_absent and not is_withheld and not is_malpractice:
            # No data at all — skip this student/subject combination
            return None

        # Determine final status
        percentage = round(total_weighted, 4)
        min_pct = (
            self.result_rule.minimum_overall_percent
            if self.result_rule else 40.0
        )

        if is_malpractice:
            final_status = 'malpractice'
            is_pass = False
        elif is_withheld:
            final_status = 'withheld'
            is_pass = False
        elif is_absent:
            final_status = 'absent'
            is_pass = False
        elif has_mandatory_fail and (
            self.result_rule and self.result_rule.fail_on_any_mandatory_component
        ):
            final_status = 'fail'
            is_pass = False
        elif percentage < min_pct:
            final_status = 'fail'
            is_pass = False
        else:
            final_status = 'pass'
            is_pass = True

        # Grade conversion
        grade_letter, grade_point, remark, is_grade_fail = self._apply_grading(percentage)
        if is_grade_fail and final_status == 'pass':
            final_status = 'fail'
            is_pass = False

        return {
            'percentage': percentage,
            'weighted_total': total_weighted,
            'component_total': sum(c['normalized_obtained'] for c in components),
            'grade_letter': grade_letter,
            'grade_point': grade_point,
            'is_pass': is_pass,
            'is_failed': final_status == 'fail',
            'is_absent': is_absent,
            'is_withheld': is_withheld,
            'is_malpractice': is_malpractice,
            'original_result_status': final_status,
            'current_result_status': final_status,
            'remarks': remark or '',
            'components': components,
        }

    # =========================================================================
    # Grading
    # =========================================================================

    def _apply_grading(self, percentage):
        """
        Look up grade for a percentage using the result session's grading scheme.

        Returns: (grade_letter, grade_point, remark, is_fail)
        """
        if not self.grading_scheme:
            return '', 0.0, '', False
        return self.grading_scheme.get_grade(percentage)

    # =========================================================================
    # DB write helpers
    # =========================================================================

    def _clear_previous_results(self):
        """Wipe all existing subject lines and student results for this session."""
        session_id = self.session.id
        SubjectLine = self.env['edu.result.subject.line']
        StudentResult = self.env['edu.result.student']
        ComponentLine = self.env['edu.result.subject.component']

        existing_subject_lines = SubjectLine.search(
            [('result_session_id', '=', session_id)]
        )
        if existing_subject_lines:
            ComponentLine.search(
                [('result_subject_line_id', 'in', existing_subject_lines.ids)]
            ).unlink()
            existing_subject_lines.unlink()

        StudentResult.search(
            [('result_session_id', '=', session_id)]
        ).unlink()

    def _build_subject_line_vals(self, ph, curriculum_line, result):
        """Build the vals dict for edu.result.subject.line creation."""
        vals = {
            'result_session_id': self.session.id,
            'student_id': ph.student_id.id,
            'enrollment_id': ph.enrollment_id.id if ph.enrollment_id else False,
            'student_progression_history_id': ph.id,
            'batch_id': ph.batch_id.id if ph.batch_id else False,
            'section_id': ph.section_id.id if ph.section_id else False,
            'program_term_id': ph.program_term_id.id if ph.program_term_id else False,
            'subject_id': curriculum_line.subject_id.id,
            'curriculum_line_id': curriculum_line.id,
            'component_total': result['component_total'],
            'weighted_total': result['weighted_total'],
            'percentage': result['percentage'],
            'grade_letter': result['grade_letter'],
            'grade_point': result['grade_point'],
            'is_pass': result['is_pass'],
            'is_failed': result['is_failed'],
            'is_absent': result['is_absent'],
            'is_withheld': result['is_withheld'],
            'is_malpractice': result['is_malpractice'],
            'is_exempt': False,
            'original_result_status': result['original_result_status'],
            'current_result_status': result['current_result_status'],
            'backlog_flag': False,
            'is_backlog_subject': False,
            'is_back_exam_eligible': False,
            'attempt_count': 1,
            'effective_attempt_no': 1,
            'has_back_exam': False,
            'back_exam_cleared': False,
            'recomputed_after_back': False,
            'superseded_by_result_subject_line_id': False,
            'remarks': result['remarks'],
        }
        return vals, result['components']

    def _batch_create_subject_lines(self, subject_line_data):
        """Batch-create subject lines and their components."""
        SubjectLine = self.env['edu.result.subject.line']
        ComponentLine = self.env['edu.result.subject.component']

        if not subject_line_data:
            return

        # Create subject lines in bulk
        vals_list = [vd[0] for vd in subject_line_data]
        created_lines = SubjectLine.create(vals_list)

        # Build component vals
        comp_vals_all = []
        for line_rec, (_, components) in zip(created_lines, subject_line_data):
            for comp in components:
                comp_vals_all.append({
                    'result_subject_line_id': line_rec.id,
                    'scheme_line_id': comp['scheme_line_id'],
                    'name': comp['scheme_line_name'],
                    'raw_obtained': comp['raw_obtained'],
                    'raw_max': comp['raw_max'],
                    'normalized_obtained': comp['normalized_obtained'],
                    'normalized_max': comp['normalized_max'],
                    'weighted_contribution': comp['weighted_contribution'],
                    'weightage_percent': comp['weightage_percent'],
                    'is_pass': comp['is_pass'],
                    'is_mandatory': comp['is_mandatory'],
                    'records_count': comp['records_count'],
                })

        if comp_vals_all:
            ComponentLine.create(comp_vals_all)

    # =========================================================================
    # Backlog identification
    # =========================================================================

    def _identify_and_flag_backlogs(self):
        """
        Flag failed subjects as backlogs and mark back exam eligibility.

        Back exam eligibility is determined by the back exam policy on the
        assessment scheme (or the result rule's back_exam_policy reference).
        """
        rule = self.result_rule
        policy = self.scheme.back_exam_policy_id

        # Fetch eligible statuses from policy
        eligible_statuses = ['fail']
        if policy:
            eligible_statuses = policy.get_eligible_statuses()

        failed_lines = self.env['edu.result.subject.line'].search([
            ('result_session_id', '=', self.session.id),
            ('is_failed', '=', True),
        ])
        absent_lines = self.env['edu.result.subject.line'].search([
            ('result_session_id', '=', self.session.id),
            ('is_absent', '=', True),
        ]) if 'absent' in eligible_statuses else self.env['edu.result.subject.line']

        backlog_lines = failed_lines | absent_lines

        backlog_write = {'is_backlog_subject': True, 'backlog_flag': True}
        if rule and rule.allow_backlog:
            backlog_write['is_back_exam_eligible'] = True

        if backlog_lines:
            backlog_lines.write(backlog_write)

    # =========================================================================
    # Student-level aggregation
    # =========================================================================

    def _compute_all_student_results(self, progression_histories):
        """Create edu.result.student for each progression history."""
        StudentResult = self.env['edu.result.student']
        SubjectLine = self.env['edu.result.subject.line']

        # Batch-fetch all subject lines for the session
        all_subject_lines = SubjectLine.search(
            [('result_session_id', '=', self.session.id)]
        )
        # Index by progression_history_id
        by_ph = defaultdict(lambda: self.env['edu.result.subject.line'])
        for sl in all_subject_lines:
            by_ph[sl.student_progression_history_id.id] |= sl

        student_result_vals = []
        for ph in progression_histories:
            subject_lines = by_ph.get(ph.id, self.env['edu.result.subject.line'])
            if not subject_lines:
                continue
            vals = self._build_student_result_vals(ph, subject_lines)
            student_result_vals.append(vals)

        if student_result_vals:
            StudentResult.create(student_result_vals)

    def _build_student_result_vals(self, ph, subject_lines):
        """Compute and build vals dict for one student's result."""
        rule = self.result_rule

        # Filter to active (non-superseded) subject lines only
        active_lines = subject_lines.filtered(
            lambda sl: not sl.superseded_by_result_subject_line_id
        )

        if not active_lines:
            active_lines = subject_lines

        # Average percentage across subjects
        pct_values = [sl.percentage for sl in active_lines]
        avg_percentage = sum(pct_values) / len(pct_values) if pct_values else 0.0

        # GPA: credit-weighted
        total_credits = 0.0
        total_grade_points = 0.0
        for sl in active_lines:
            credit = (
                sl.curriculum_line_id.credit_hours
                if sl.curriculum_line_id and sl.curriculum_line_id.credit_hours
                else 1.0
            )
            total_credits += credit
            total_grade_points += (sl.grade_point or 0.0) * credit
        gpa = round(total_grade_points / total_credits, 4) if total_credits else 0.0

        # Backlog count
        backlog_lines = active_lines.filtered('is_backlog_subject')
        backlog_count = len(backlog_lines)
        cleared = len(active_lines.filtered('back_exam_cleared'))
        remaining = max(0, backlog_count - cleared)

        # Determine overall result status
        has_fail = any(sl.is_failed for sl in active_lines)
        has_malpractice = any(sl.is_malpractice for sl in active_lines)
        has_withheld = any(sl.is_withheld for sl in active_lines)
        max_backlogs = (rule.max_backlog_subjects if rule else 0) or 0

        if has_malpractice:
            result_status = 'malpractice'
        elif has_withheld:
            result_status = 'withheld'
        elif has_fail:
            if rule and rule.allow_backlog and backlog_count <= max_backlogs:
                result_status = 'promoted_with_backlog'
            else:
                result_status = 'fail'
        else:
            result_status = 'pass'

        # Grade for student level
        grade_letter, _, _, _ = self._apply_grading(avg_percentage)

        # Distinction (≥ 80% average, no fail, no backlog — configurable if needed)
        distinction = (
            avg_percentage >= 80.0
            and not has_fail
            and not has_malpractice
            and not has_withheld
        )

        return {
            'result_session_id': self.session.id,
            'student_id': ph.student_id.id,
            'enrollment_id': ph.enrollment_id.id if ph.enrollment_id else False,
            'student_progression_history_id': ph.id,
            'batch_id': ph.batch_id.id if ph.batch_id else False,
            'section_id': ph.section_id.id if ph.section_id else False,
            'program_term_id': ph.program_term_id.id if ph.program_term_id else False,
            'total_marks': sum(
                (sl.curriculum_line_id.full_marks or 100.0)
                for sl in active_lines
            ),
            'obtained_marks': round(
                sum(sl.weighted_total for sl in active_lines), 4
            ),
            'percentage': round(avg_percentage, 4),
            'gpa': gpa,
            'grade_letter': grade_letter,
            'result_status': result_status,
            'backlog_count': backlog_count,
            'cleared_backlog_count': cleared,
            'remaining_backlog_count': remaining,
            'has_active_backlog': remaining > 0,
            'distinction_flag': distinction,
            'remarks': '',
            'published_on': False,
        }

    # =========================================================================
    # Back exam recomputation
    # =========================================================================

    def recompute_after_back_exam(self, back_exam_session, back_exam_policy):
        """
        Recompute results for students who took a back exam.

        This method:
        1. Finds subject lines eligible for back exam in this session.
        2. Checks if back exam marks exist in back_exam_session.
        3. Applies carry-forward rules from back_exam_policy.
        4. Creates new subject lines (marks old ones as superseded).
        5. Recomputes student-level results for affected students.
        """
        policy = back_exam_policy
        eligible_statuses = policy.get_eligible_statuses()

        # Find eligible subject lines that haven't been cleared yet
        eligible_lines = self.env['edu.result.subject.line'].search([
            ('result_session_id', '=', self.session.id),
            ('is_back_exam_eligible', '=', True),
            ('back_exam_cleared', '=', False),
            ('superseded_by_result_subject_line_id', '=', False),
        ])

        affected_ph_ids = set()
        SubjectLine = self.env['edu.result.subject.line']
        ComponentLine = self.env['edu.result.subject.component']

        # Batch-fetch back exam marksheets
        back_marksheets = self.env['edu.exam.marksheet'].search([
            ('exam_session_id', '=', back_exam_session.id),
            ('state', 'in', ('published', 'closed'))
            if hasattr(self.env['edu.exam.marksheet'], 'state')
            else ('exam_paper_state', 'in', ('published', 'closed')),
            ('is_latest_attempt', '=', True),
        ])
        # Index by (student_id, curriculum_line_id)
        back_ms_index = {
            (ms.student_id.id, ms.curriculum_line_id.id): ms
            for ms in back_marksheets
        }

        new_subject_line_data = []
        lines_to_supersede = []

        for orig_line in eligible_lines:
            key = (orig_line.student_id.id, orig_line.curriculum_line_id.id)
            back_ms = back_ms_index.get(key)
            if not back_ms:
                continue  # Student did not take back exam for this subject

            # Check attempt limit
            if orig_line.attempt_count >= policy.max_attempts:
                continue

            # Recompute subject result
            new_result = self._recompute_with_back_marks(
                orig_line, back_ms, policy
            )
            if new_result is None:
                continue

            # Build new subject line vals (copy original, override changed fields)
            new_vals = {
                'result_session_id': self.session.id,
                'student_id': orig_line.student_id.id,
                'enrollment_id': orig_line.enrollment_id.id if orig_line.enrollment_id else False,
                'student_progression_history_id': orig_line.student_progression_history_id.id,
                'batch_id': orig_line.batch_id.id if orig_line.batch_id else False,
                'section_id': orig_line.section_id.id if orig_line.section_id else False,
                'program_term_id': orig_line.program_term_id.id if orig_line.program_term_id else False,
                'subject_id': orig_line.subject_id.id,
                'curriculum_line_id': orig_line.curriculum_line_id.id,
                'component_total': new_result['component_total'],
                'weighted_total': new_result['weighted_total'],
                'percentage': new_result['percentage'],
                'grade_letter': new_result['grade_letter'],
                'grade_point': new_result['grade_point'],
                'is_pass': new_result['is_pass'],
                'is_failed': not new_result['is_pass'],
                'is_absent': False,
                'is_withheld': False,
                'is_malpractice': False,
                'is_exempt': False,
                'original_result_status': orig_line.original_result_status,
                'current_result_status': 'pass' if new_result['is_pass'] else 'fail',
                'backlog_flag': not new_result['is_pass'],
                'is_backlog_subject': not new_result['is_pass'],
                'is_back_exam_eligible': not new_result['is_pass'],
                'attempt_count': orig_line.attempt_count + 1,
                'effective_attempt_no': orig_line.attempt_count + 1,
                'has_back_exam': True,
                'back_exam_cleared': new_result['is_pass'],
                'recomputed_after_back': True,
                'superseded_by_result_subject_line_id': False,
                'remarks': f'Back exam attempt {orig_line.attempt_count + 1}. {new_result["remarks"]}',
            }
            new_subject_line_data.append((new_vals, new_result['components'], orig_line))
            affected_ph_ids.add(orig_line.student_progression_history_id.id)

        # Create new lines
        for new_vals, components, orig_line in new_subject_line_data:
            new_line = SubjectLine.create(new_vals)

            # Create component breakdown for new line
            comp_vals_list = []
            for comp in components:
                comp_vals_list.append({
                    'result_subject_line_id': new_line.id,
                    'scheme_line_id': comp['scheme_line_id'],
                    'name': comp['scheme_line_name'],
                    'raw_obtained': comp['raw_obtained'],
                    'raw_max': comp['raw_max'],
                    'normalized_obtained': comp['normalized_obtained'],
                    'normalized_max': comp['normalized_max'],
                    'weighted_contribution': comp['weighted_contribution'],
                    'weightage_percent': comp['weightage_percent'],
                    'is_pass': comp['is_pass'],
                    'is_mandatory': comp['is_mandatory'],
                    'records_count': comp['records_count'],
                })
            if comp_vals_list:
                ComponentLine.create(comp_vals_list)

            # Supersede old line
            orig_line.write({
                'superseded_by_result_subject_line_id': new_line.id,
                'has_back_exam': True,
                'back_exam_cleared': new_line.back_exam_cleared,
            })

        # Recompute student-level results for affected students
        if affected_ph_ids:
            affected_phs = self.env['edu.student.progression.history'].browse(
                list(affected_ph_ids)
            )
            self._recompute_student_results_for(affected_phs)

    def _recompute_with_back_marks(self, original_line, back_marksheet, policy):
        """
        Recompute a single subject using back exam marks and carry-forward rules.

        For the scheme lines where the back exam replaces original marks, we use
        back_marksheet.  For other lines, we carry forward from original components
        according to the policy's carry_forward_* settings.
        """
        back_obtained = back_marksheet.final_marks or 0.0
        back_max = back_marksheet.max_marks or 100.0

        # Determine which exam sessions the back exam covers
        back_session_id = back_marksheet.exam_session_id.id

        components = []
        total_weighted = 0.0
        has_mandatory_fail = False
        has_any_data = False

        for line in self.scheme_lines:
            if not line.contributes_to_final:
                continue

            use_back_marks = False

            # Check if this scheme line is sourced from an exam session
            # and the back exam session matches or is linked
            if line.source_type in ('exam_session', 'exam_component', 'board_import'):
                if line.exam_session_ids and back_session_id in line.exam_session_ids.ids:
                    use_back_marks = True
                elif back_marksheet.exam_session_id.assessment_scheme_line_id.id == line.id:
                    use_back_marks = True

            # Carry-forward logic
            if not use_back_marks:
                carry = self._should_carry_forward(line, policy)
                if carry:
                    # Use the original component value
                    orig_comp = original_line.component_ids.filtered(
                        lambda c: c.scheme_line_id.id == line.id
                    )
                    if orig_comp:
                        c = orig_comp[0]
                        normalized = c.normalized_obtained
                        raw_max = c.normalized_max
                        weighted = c.weighted_contribution
                        line_pass = c.is_pass
                        has_any_data = True
                    else:
                        normalized, raw_max, weighted, line_pass = 0.0, line.max_marks or 100.0, 0.0, True
                else:
                    normalized, raw_max, weighted, line_pass = 0.0, line.max_marks or 100.0, 0.0, True
            else:
                # Use back exam marks
                target_max = line.max_marks or 100.0
                normalized = self._normalize(back_obtained, back_max, target_max)
                weighted = self._weighted_contribution(
                    normalized, target_max, line.weightage_percent or 0.0
                )
                line_pass = True
                if line.requires_separate_pass and line.pass_marks:
                    line_pass = normalized >= line.pass_marks
                if line.is_mandatory and not line_pass:
                    has_mandatory_fail = True
                has_any_data = True
                raw_max = target_max

            total_weighted += weighted

            components.append({
                'scheme_line_id': line.id,
                'scheme_line_name': line.name,
                'raw_obtained': normalized,
                'raw_max': raw_max,
                'normalized_obtained': normalized,
                'normalized_max': raw_max,
                'weighted_contribution': weighted,
                'weightage_percent': line.weightage_percent or 0.0,
                'is_pass': line_pass,
                'is_mandatory': line.is_mandatory,
                'records_count': 1,
            })

        if not has_any_data:
            return None

        percentage = round(total_weighted, 4)

        # Apply percentage cap from policy
        if policy.cap_max_percentage_after_back and policy.cap_max_percentage_after_back > 0:
            percentage = min(percentage, policy.cap_max_percentage_after_back)

        min_pct = (
            self.result_rule.minimum_overall_percent
            if self.result_rule else 40.0
        )

        is_pass = (
            not has_mandatory_fail
            and percentage >= min_pct
        )

        grade_letter, grade_point, remark, is_grade_fail = self._apply_grading(percentage)
        if is_grade_fail:
            is_pass = False

        # Apply grade cap from policy
        # (simplified — full cap logic would require grading scheme traversal)
        if policy.cap_max_grade_after_back and grade_letter:
            pass  # Future enhancement: cap grade_letter to configured cap

        return {
            'percentage': percentage,
            'weighted_total': total_weighted,
            'component_total': sum(c['normalized_obtained'] for c in components),
            'grade_letter': grade_letter,
            'grade_point': grade_point,
            'is_pass': is_pass,
            'remarks': remark or '',
            'components': components,
        }

    def _should_carry_forward(self, scheme_line, policy):
        """Determine if this scheme line's marks should be carried forward."""
        src = scheme_line.source_type
        if src in ('exam_session', 'exam_component') and not scheme_line.is_external:
            return policy.carry_forward_internal_marks
        if src in ('practical', 'viva'):
            return policy.carry_forward_practical_marks
        if src == 'assignment':
            return policy.carry_forward_assignment_marks
        if src == 'attendance':
            return policy.carry_forward_attendance_marks
        if src == 'class_performance':
            return policy.carry_forward_class_performance
        # Class tests, projects — treat as internal by default
        return policy.carry_forward_internal_marks

    def _recompute_student_results_for(self, progression_histories):
        """Recompute student-level results for specific progression histories."""
        StudentResult = self.env['edu.result.student']
        SubjectLine = self.env['edu.result.subject.line']

        ph_ids = progression_histories.ids

        # Fetch all non-superseded subject lines for these students in this session
        active_lines = SubjectLine.search([
            ('result_session_id', '=', self.session.id),
            ('student_progression_history_id', 'in', ph_ids),
            ('superseded_by_result_subject_line_id', '=', False),
        ])

        by_ph = defaultdict(lambda: self.env['edu.result.subject.line'])
        for sl in active_lines:
            by_ph[sl.student_progression_history_id.id] |= sl

        for ph in progression_histories:
            subject_lines = by_ph.get(ph.id, self.env['edu.result.subject.line'])
            if not subject_lines:
                continue

            new_vals = self._build_student_result_vals(ph, subject_lines)
            student_result = StudentResult.search([
                ('result_session_id', '=', self.session.id),
                ('student_progression_history_id', '=', ph.id),
            ], limit=1)

            if student_result:
                student_result.write({
                    k: v for k, v in new_vals.items()
                    if k not in ('result_session_id', 'student_id',
                                 'enrollment_id', 'student_progression_history_id',
                                 'batch_id', 'section_id', 'program_term_id')
                })
            else:
                StudentResult.create(new_vals)
