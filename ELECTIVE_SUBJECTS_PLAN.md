# Elective Subjects Implementation Plan

## Overview

Allow students to choose elective subjects per term. The curriculum line model
already has a `subject_category` field (`compulsory` | `elective` | `optional`).
This plan uses that existing field as the gate — no new fields needed on
`edu.curriculum.line`.

The student's elected subjects are stored on `edu.student.progression.history`
(one record per student per term), which is already the authoritative anchor for
all downstream academic modules.

---

## Scope of Changes

| File | Type | Change |
|---|---|---|
| `edu_academic_progression/models/edu_student_progression_history.py` | Model | Add M2M + computed field |
| `edu_academic_progression/views/edu_student_progression_history_views.xml` | View | Add elective selection tab |
| `edu_academic_progression/security/ir.model.access.csv` | Security | Add access for new M2M if needed |
| `edu_exam/wizard/edu_exam_marksheet_generate_wizard.py` | Wizard | Filter by effective curriculum lines |
| `edu_assessment/wizard/edu_assessment_bulk_generate_wizard.py` | Wizard | Filter by effective curriculum lines |
| `edu_result/models/result_engine.py` | Engine | Scope curriculum lines per student |

---

## Phase 1 — edu_academic_progression

### 1.1 Model: `edu_student_progression_history.py`

**File:** `edu_academic_progression/models/edu_student_progression_history.py`

Add two fields inside the class, after the existing relational fields section:

```python
# ═══ Elective Subject Choices ═══

elected_curriculum_line_ids = fields.Many2many(
    comodel_name='edu.curriculum.line',
    relation='edu_progression_elected_curriculum_rel',
    column1='progression_history_id',
    column2='curriculum_line_id',
    string='Elected Subjects',
    domain="[('program_term_id', '=', program_term_id), ('subject_category', 'in', ('elective', 'optional'))]",
    help='Elective and optional subjects the student has chosen for this term. '
         'Mandatory subjects are always included automatically.',
)

effective_curriculum_line_ids = fields.Many2many(
    comodel_name='edu.curriculum.line',
    relation='edu_progression_effective_curriculum_rel',
    column1='progression_history_id',
    column2='curriculum_line_id',
    string='Effective Subjects (Mandatory + Elected)',
    compute='_compute_effective_curriculum_lines',
    store=True,
)
```

Add the compute method inside the class:

```python
@api.depends('program_term_id', 'elected_curriculum_line_ids')
def _compute_effective_curriculum_lines(self):
    for rec in self:
        if not rec.program_term_id:
            rec.effective_curriculum_line_ids = self.env['edu.curriculum.line']
            continue
        mandatory = self.env['edu.curriculum.line'].search([
            ('program_term_id', '=', rec.program_term_id.id),
            ('subject_category', '=', 'compulsory'),
        ])
        rec.effective_curriculum_line_ids = mandatory | rec.elected_curriculum_line_ids
```

**Important constraints to add:**

```python
@api.constrains('elected_curriculum_line_ids', 'program_term_id')
def _check_elected_belong_to_term(self):
    for rec in self:
        for line in rec.elected_curriculum_line_ids:
            if line.program_term_id != rec.program_term_id:
                raise ValidationError(
                    _('Subject "%s" does not belong to the selected program term.')
                    % line.subject_id.name
                )
            if line.subject_category == 'compulsory':
                raise ValidationError(
                    _('Subject "%s" is compulsory and cannot be added as an elective choice.')
                    % line.subject_id.name
                )
```

**Note on frozen fields:** The existing `write()` override protects frozen fields for
closed records. `elected_curriculum_line_ids` should also be frozen once the record
is closed. Add `'elected_curriculum_line_ids'` to the `_FROZEN_FIELDS` set (or
whichever mechanism is used — check the existing `write()` implementation).

---

### 1.2 View: `edu_student_progression_history_views.xml`

**File:** `edu_academic_progression/views/edu_student_progression_history_views.xml`

Add a new notebook page to the form view, after the existing Academic Placement
group and before the Notes/Audit sections:

```xml
<page string="Elective Subjects" name="electives">
    <div class="alert alert-info" role="alert"
         invisible="state != 'active'">
        Select the elective and optional subjects for this student's current term.
        Compulsory subjects are always included automatically.
    </div>
    <field name="elected_curriculum_line_ids"
           readonly="state != 'active'"
           domain="[('program_term_id', '=', program_term_id), ('subject_category', 'in', ('elective', 'optional'))]"
           widget="many2many_tags">
    </field>
    <separator string="Effective Subjects (Compulsory + Elected)"/>
    <field name="effective_curriculum_line_ids" readonly="1">
        <list>
            <field name="subject_id"/>
            <field name="subject_category"/>
            <field name="credit_hours"/>
            <field name="full_marks"/>
            <field name="pass_marks"/>
        </list>
    </field>
</page>
```

Also add `elected_curriculum_line_ids` as a searchable field in the search view:

```xml
<field name="elected_curriculum_line_ids" string="Elected Subject"/>
```

---

### 1.3 Security: `ir.model.access.csv`

**File:** `edu_academic_progression/security/ir.model.access.csv`

The M2M relation table (`edu_progression_elected_curriculum_rel` and
`edu_progression_effective_curriculum_rel`) is managed automatically by Odoo.
No new model access lines are needed unless a new model is introduced.

The `effective_curriculum_line_ids` computed M2M relation table will be
auto-created. Access is inherited from the parent model's access rules.

---

## Phase 2 — edu_exam (Marksheet Generation)

### 2.1 Wizard: `edu_exam_marksheet_generate_wizard.py`

**File:** `edu_exam/wizard/edu_exam_marksheet_generate_wizard.py`

**Change location:** Inside `action_generate()`, in the per-paper loop.

Find this block:

```python
# Fetch all active students in the batch (across all sections)
histories = self.env['edu.student.progression.history'].search([
    ('batch_id', '=', paper.batch_id.id),
    ('state', '=', 'active'),
])
```

Replace with:

```python
# Fetch active students in the batch who are taking this subject.
# Students with no elected subjects set are treated as taking all subjects
# (backwards compatibility for records created before electives were introduced).
all_histories = self.env['edu.student.progression.history'].search([
    ('batch_id', '=', paper.batch_id.id),
    ('state', '=', 'active'),
])
histories = all_histories.filtered(
    lambda h: not h.effective_curriculum_line_ids
    or paper.curriculum_line_id in h.effective_curriculum_line_ids
)
```

**Backwards compatibility note:** The `not h.effective_curriculum_line_ids` guard
ensures that existing progression history records (created before this feature)
that have no elective data set will still receive marksheets for all subjects.
Once elective data is populated for a record, the filter kicks in.

No other changes needed in this file.

---

## Phase 3 — edu_assessment (Bulk Generation)

### 3.1 Wizard: `edu_assessment_bulk_generate_wizard.py`

**File:** `edu_assessment/wizard/edu_assessment_bulk_generate_wizard.py`

**Change location:** Inside `action_generate()`.

The assessment wizard currently queries progression histories by `section_id`
(classroom-scoped). Find this block:

```python
histories = self.env['edu.student.progression.history'].search([
    ('section_id', '=', self.classroom_id.section_id.id),
    ('state', '=', 'active'),
])
```

Replace with:

```python
curriculum_line = self.classroom_id.curriculum_line_id
all_histories = self.env['edu.student.progression.history'].search([
    ('section_id', '=', self.classroom_id.section_id.id),
    ('state', '=', 'active'),
])
histories = all_histories.filtered(
    lambda h: not h.effective_curriculum_line_ids
    or curriculum_line in h.effective_curriculum_line_ids
)
```

Apply the same backwards-compatibility guard as in Phase 2.

---

## Phase 4 — edu_result (Result Engine)

This is the most significant change. The result engine currently fetches all
curriculum lines for a program term and computes results for every student across
all of those lines. With electives, each student may have a different set of
effective curriculum lines.

**File:** `edu_result/models/result_engine.py`

### 4.1 Change `_get_curriculum_lines()`

Current behaviour: returns all curriculum lines for the session's program term.

```python
def _get_curriculum_lines(self):
    # currently returns ALL lines for program_term
    return self.env['edu.curriculum.line'].search([
        ('program_term_id', '=', self.session.program_term_id.id),
    ])
```

This method should remain unchanged — it still returns all lines for the term.
This is used as the superset. The per-student scoping happens in the compute loop.

### 4.2 Change `compute()`

Find the loop that iterates `histories × curriculum_lines`:

```python
for history in histories:
    for curriculum_line in curriculum_lines:
        # compute subject result
```

Wrap the inner loop with an effective-lines check:

```python
for history in histories:
    # Determine which curriculum lines this student is actually taking.
    # Fall back to all lines if no elective data has been set (backwards compat).
    if history.effective_curriculum_line_ids:
        student_lines = curriculum_lines.filtered(
            lambda l: l in history.effective_curriculum_line_ids
        )
    else:
        student_lines = curriculum_lines

    for curriculum_line in student_lines:
        # compute subject result — unchanged
```

### 4.3 Change `_compute_all_student_results()`

The student-level aggregation (total marks, GPA, credit hours) currently sums
across all subject lines. With electives, a student only has subject lines for
their effective curriculum. This should work automatically because subject lines
are created per student in the loop above — there will simply be fewer lines per
student.

However, verify that GPA calculation uses the subject lines' credit hours for
weighting, not the total credit hours of the full program term. If it uses
`program_term.total_credit_hours`, this must be changed to sum only the credit
hours of the student's subject lines.

Look for code that reads `program_term_id.credit_hours` or similar and replace
with a sum over the student's actual subject lines:

```python
# Instead of:
total_credit_hours = history.program_term_id.total_credit_hours

# Use:
subject_lines_for_student = result_subject_lines.filtered(
    lambda l: l.student_progression_history_id == history
)
total_credit_hours = sum(subject_lines_for_student.mapped('credit_hours'))
```

### 4.4 Change `_build_source_cache()`

The source cache is pre-built for all (student, curriculum_line) pairs. It is
keyed by `(student_id, curriculum_line_id)`. No structural change is needed here —
the cache will simply have no entry for pairs that don't exist (student didn't
take the subject), and the compute loop will never request them.

---

## Phase 5 — Attendance (No Code Change Required)

The attendance module is already correctly scoped. `edu.attendance.register` is
one-to-one with `edu.classroom` (section × subject × term). A student who did not
elect a subject will simply not appear in that classroom's expected student list
because:

- They will have no marksheet for that subject's paper (Phase 2 above)
- The attendance sheet line creation (if it uses progression history + section)
  will need the same filter as Phase 3

**Check:** If `edu_attendance` has a "populate sheet" or "generate expected
students" wizard or method, apply the same filter pattern as Phase 2 and 3:

```python
histories = all_histories.filtered(
    lambda h: not h.effective_curriculum_line_ids
    or classroom.curriculum_line_id in h.effective_curriculum_line_ids
)
```

Search for `edu.student.progression.history` references in
`edu_attendance/models/` and `edu_attendance/wizard/` to find all call sites.

---

## Migration Notes

### Existing Data

All existing progression history records will have `elected_curriculum_line_ids`
empty and `effective_curriculum_line_ids` empty. The backwards-compatibility
guard in Phases 2, 3, and 4 (`not h.effective_curriculum_line_ids`) ensures
they are treated as taking all subjects — identical to current behaviour.

### Populating Electives for Existing Records

Once the feature is deployed, if you want to retroactively assign elective
choices to existing active students, use a one-time migration script or a
backfill wizard (similar in style to the existing progression backfill wizard).

No Odoo `pre_init_hook` or `post_init_hook` is needed since the empty M2M is
the correct backwards-compatible default.

---

## Module Update Order

```
1. edu_academic_structure   (no change — subject_category already exists)
2. edu_academic_progression (Phase 1 — new fields + view)
3. edu_exam                 (Phase 2 — wizard filter)
4. edu_assessment           (Phase 3 — wizard filter)
5. edu_result               (Phase 4 — engine scoping)
```

Update command:
```bash
odoo -d <database> -u edu_academic_progression,edu_exam,edu_assessment,edu_result
```

---

## Key Design Decisions

1. **`subject_category` already exists** on `edu.curriculum.line` with values
   `compulsory | elective | optional`. Do not add an `is_elective` boolean —
   use the existing field.

2. **`effective_curriculum_line_ids` is stored** (not just computed on-the-fly)
   so that it can be used in ORM domain filters efficiently without loading
   all records into Python.

3. **Backwards compatibility guard** (`not h.effective_curriculum_line_ids`)
   is used in all three downstream wizards and the result engine. This means
   the feature is opt-in per student — no big-bang migration required.

4. **Attendance requires manual audit** — find all call sites that query
   `edu.student.progression.history` in `edu_attendance` and apply the filter.
   There is no central list; grep for the model name.

5. **Result engine credit-hour weighting** must use per-student subject line
   credit hours, not the program term's total, otherwise GPA will be wrong
   for students taking fewer electives.

6. **Elective choices are frozen** when the progression history record is
   closed (same mechanism as other frozen fields). This preserves historical
   accuracy.
