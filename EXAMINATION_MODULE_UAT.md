# Examination Module UAT

## 1. Document Purpose

This document provides a structured User Acceptance Testing (UAT) guide for the `edu_exam` flow and its integration with:

- `edu_academic_structure`
- `edu_academic_progression`
- `edu_attendance`
- `edu_assessment`
- `edu_result`

The goal is to verify that examination setup, paper generation, marksheet generation, marks entry, publication, result computation, and back-exam handling behave correctly for real academic operations.

## 2. UAT Scope

The following business flows are covered:

- Exam session creation and lifecycle
- Exam paper generation from classrooms
- Exam paper generation from curriculum lines
- Marksheet generation for eligible students
- Elective subject filtering
- Attendance snapshot behavior during marksheet generation
- Marks entry and validation rules
- Paper and session publication flow
- Result computation based on published exams
- Back exam generation and latest-attempt behavior

The following are out of scope unless separately requested:

- Performance/load testing
- Report print layout validation
- Security role matrix testing in depth
- Automated test scripting

## 3. Modules and Functional Dependencies

### 3.1 Primary module

- `edu_exam`

### 3.2 Dependent modules used during testing

- `edu_academic_structure`
- `edu_academic_progression`
- `edu_attendance`
- `edu_assessment`
- `edu_result`

## 4. Test Roles

Use the following business roles during UAT where possible:

- Education Admin
- Exam Officer
- Exam Publish Manager
- Teacher

Minimum requirement:

- One admin-capable user
- One exam officer or equivalent
- One exam publish manager or equivalent

## 5. Test Environment Preconditions

Before starting UAT, ensure the following are available in the test database:

- A valid academic year
- A valid program
- At least one program term
- One batch linked to the program
- At least two sections under the same batch
- At least four students
- Active progression histories for all test students
- Curriculum lines for compulsory subjects
- At least one elective or optional curriculum line
- Classrooms created for the section-subject combinations
- Attendance registers and attendance data for relevant classrooms
- Assessment scheme configured
- Result rule configured
- Grading scheme configured

## 6. Recommended Master Test Data

Use a compact but realistic setup:

- Academic Year: `2026`
- Program: `BSc CSIT`
- Program Term: `Semester 1`
- Batch: `BSc CSIT 2026 - Sem 1`
- Sections: `A`, `B`
- Compulsory Subjects:
  - English
  - Mathematics
  - Programming Fundamentals
- Elective Subject:
  - Statistics
- Students:
  - Student 1 in Section A with elective selected
  - Student 2 in Section A with elective selected
  - Student 3 in Section B without elected subjects set
  - Student 4 in Section B without elected subjects set

This setup is important because the current logic treats students without elected subjects as taking all subjects for backward compatibility.

## 7. Entry Criteria

UAT can begin only if:

- All dependent modules are installed
- Core academic master data is available
- Progression histories are active
- Users can access the Examinations menu
- No blocking technical errors appear during basic navigation

## 8. Exit Criteria

UAT may be considered complete when:

- All critical and high-priority test cases pass
- No blocker remains open
- Result computation is validated against published exam data
- Back exam generation is validated for at least one failed student
- Stakeholders approve the functional behavior

## 9. UAT Execution Notes

- Execute test cases in the sequence defined below.
- Record actual results for every case.
- Capture screenshots for any failure or unexpected result.
- Do not reuse partially corrupted data after a failed critical flow. Reset or create fresh records where needed.

## 10. Test Case Format

Each test case includes:

- Test Case ID
- Objective
- Preconditions
- Steps
- Expected Result
- Status
- Remarks

Recommended status values:

- Not Started
- Pass
- Fail
- Blocked

## 11. Detailed UAT Test Cases

### TC-EXAM-001: Verify exam menu and access

**Objective**

Verify that the Examinations module is accessible and major menus are visible.

**Preconditions**

- User has exam access rights.

**Steps**

1. Login to Odoo.
2. Open the `Examinations` menu.
3. Verify submenus for:
   - Exam Sessions
   - Exam Papers
   - Marksheets
   - Back Exams
   - Configuration

**Expected Result**

- Examinations menu opens without error.
- All expected menus are visible according to the user role.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-002: Create a regular exam session

**Objective**

Verify that a regular exam session can be created successfully.

**Preconditions**

- Academic year, batch, program, and program term exist.

**Steps**

1. Go to `Examinations -> Exam Sessions`.
2. Create a new exam session.
3. Enter:
   - Session Name
   - Exam Type
   - Attempt Type = `Regular`
   - Academic Year
   - Program
   - Batch
   - Program Term
   - Start Date
   - End Date
4. Save the record.

**Expected Result**

- Session is saved successfully.
- Session code is generated automatically if left blank.
- State remains `Draft`.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-003: Validate exam session date rules

**Objective**

Verify that invalid session dates are rejected.

**Preconditions**

- Exam session creation page is open.

**Steps**

1. Create a new exam session.
2. Enter a `Date End` earlier than `Date Start`.
3. Save the record.

**Expected Result**

- System blocks save.
- Validation message indicates that end date cannot be earlier than start date.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-004: Generate exam papers from active classrooms

**Objective**

Verify that papers are generated from active classrooms and deduplicated by curriculum line and batch.

**Preconditions**

- Exam session exists in `Draft` or `Planned`.
- Active classrooms exist for the session batch and program term.

**Steps**

1. Open the exam session.
2. Click `Generate Papers`.
3. Select scope `From Active Classrooms`.
4. Click `Load Preview`.
5. Review preview lines.
6. Click `Generate`.

**Expected Result**

- One paper is created per `exam session + curriculum line + batch`.
- Duplicate papers are not created for the same subject across multiple sections.
- Teacher is populated from the first matching classroom where available.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-005: Re-run classroom-based paper generation for idempotency

**Objective**

Verify that re-running paper generation does not create duplicates.

**Preconditions**

- TC-EXAM-004 has passed.

**Steps**

1. Open the same exam session again.
2. Click `Generate Papers`.
3. Select scope `From Active Classrooms`.
4. Click `Load Preview`.
5. Observe preview status.
6. Click `Generate`.

**Expected Result**

- Existing papers are identified as already existing.
- No duplicate paper records are created.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-006: Generate exam papers from curriculum lines

**Objective**

Verify that papers can also be generated directly from curriculum lines.

**Preconditions**

- Exam session has a program term.
- Curriculum lines exist for that program term.

**Steps**

1. Create a fresh exam session or use one without generated papers.
2. Click `Generate Papers`.
3. Select scope `From Curriculum Lines`.
4. Click `Load Preview`.
5. Click `Generate`.

**Expected Result**

- Papers are created from curriculum lines even when classroom linkage is absent.
- Batch and curriculum line are correctly set on created papers.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-007: Verify paper generation excludes duplicates by SQL/business rule

**Objective**

Verify uniqueness of exam papers for the same session, curriculum line, and batch.

**Preconditions**

- At least one exam paper already exists.

**Steps**

1. Try to manually create another paper with the same:
   - Exam Session
   - Curriculum Line
   - Batch
2. Save the record.

**Expected Result**

- System blocks duplicate creation.
- User sees a uniqueness validation error.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-008: Generate marksheets for all papers in a session

**Objective**

Verify that marksheets are generated for eligible students.

**Preconditions**

- Exam session has generated papers.
- Students have active progression histories.

**Steps**

1. Open `Generate Marksheets`.
2. Select the exam session.
3. Leave paper filter empty.
4. Set:
   - Attempt Type = `Regular`
   - Attempt No = `1`
   - Snapshot Attendance = enabled
5. Run generation.

**Expected Result**

- Marksheets are created for eligible students across all session papers.
- Result message shows created and skipped counts.
- Students are linked to the correct batch, section, program term, and curriculum line snapshot.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-009: Verify elective filtering during marksheet generation

**Objective**

Verify that elective subject papers generate marksheets only for eligible students.

**Preconditions**

- At least one elective curriculum line exists.
- Some students have elected it.
- Some students have no elected subjects set.

**Steps**

1. Open the marksheet list for the elective paper.
2. Review generated marksheets student by student.

**Expected Result**

- Students who explicitly elected the subject receive marksheets.
- Students with no elected subjects set also receive marksheets due to backward-compatible logic.
- Students with explicit elective choices excluding that subject do not receive marksheets.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-010: Re-run marksheet generation for idempotency

**Objective**

Verify that duplicate marksheets are not created for the same paper and attempt combination.

**Preconditions**

- TC-EXAM-008 has passed.

**Steps**

1. Run `Generate Marksheets` again with the same:
   - Exam Session
   - Attempt Type
   - Attempt No
2. Complete generation.

**Expected Result**

- Existing marksheets are skipped.
- No duplicate marksheets are created.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-011: Verify attendance snapshot during marksheet generation

**Objective**

Verify that attendance data is snapshotted into marksheets.

**Preconditions**

- Attendance register exists for the student’s section and subject classroom.
- Attendance data has been submitted.

**Steps**

1. Generate marksheets with `Snapshot Attendance` enabled.
2. Open a generated marksheet.
3. Check `Attendance %` and `Attendance Eligible`.

**Expected Result**

- Attendance percentage is populated when attendance summary exists.
- If student attendance data is missing from the relevant register summary, attendance eligible becomes false or remains not fully eligible based on the fetched data.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-012: Generate marksheets with paper filter

**Objective**

Verify marksheet generation for selected papers only.

**Preconditions**

- Session contains multiple papers.

**Steps**

1. Open `Generate Marksheets`.
2. Select the exam session.
3. Select only one or two papers in the paper filter.
4. Run generation.

**Expected Result**

- Marksheets are created only for the selected papers.
- Other papers remain unaffected.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-013: Verify paper lifecycle transitions

**Objective**

Verify valid state changes for an exam paper.

**Preconditions**

- At least one exam paper exists.

**Steps**

1. Open a paper in `Draft`.
2. Click `Schedule`.
3. Click `Start`.
4. Click `Open Marks Entry`.
5. Click `Submit`.
6. Click `Publish`.
7. Click `Close`.

**Expected Result**

- State changes occur in the correct sequence:
  - Draft
  - Scheduled
  - In Progress
  - Marks Entry
  - Submitted
  - Published
  - Closed

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-014: Verify session lifecycle transitions

**Objective**

Verify valid state changes for an exam session.

**Preconditions**

- Exam session exists.

**Steps**

1. Open session in `Draft`.
2. Click `Plan`.
3. Click `Start`.
4. Click `Open Marks Entry`.
5. Click `Publish`.
6. Click `Close`.

**Expected Result**

- Session follows the correct lifecycle:
  - Draft
  - Planned
  - Ongoing
  - Marks Entry
  - Published
  - Closed

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-015: Verify marks entry calculations

**Objective**

Verify final marks and pass/fail computation.

**Preconditions**

- Marksheets exist for a paper in marks-entry state.

**Steps**

1. Open a marksheet.
2. Enter raw marks below pass marks.
3. Save and note final marks and pass flag.
4. Update raw marks above pass marks.
5. Save and note final marks and pass flag.
6. Add grace marks.
7. Save again.

**Expected Result**

- Final marks equal `raw marks + grace marks` for present students.
- Pass flag becomes true only when final marks are greater than or equal to pass marks.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-016: Verify absent student behavior

**Objective**

Verify marksheet logic for absent students.

**Preconditions**

- Marksheet exists.

**Steps**

1. Open a marksheet.
2. Set status to `Absent`.
3. Save the record.

**Expected Result**

- Final marks become `0`.
- Pass flag becomes false.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-017: Validate marks constraints

**Objective**

Verify that invalid marks are blocked.

**Preconditions**

- Marksheet exists in editable state.

**Steps**

1. Enter negative raw marks and save.
2. Enter raw marks greater than max marks and save.
3. Enter negative grace marks and save.

**Expected Result**

- System rejects all invalid values with validation errors.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-018: Verify edit restrictions after publication

**Objective**

Verify that marksheets cannot be edited after paper publication for non-admin users.

**Preconditions**

- Paper is in `Published` state.
- Use a non-admin exam user if possible.

**Steps**

1. Open a marksheet under a published paper.
2. Try to change raw marks.
3. Save.

**Expected Result**

- System blocks the edit.
- User receives a message that marksheet cannot be edited because paper is published or closed.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-019: Compute results from published exam data

**Objective**

Verify that result computation picks up only published or closed latest-attempt exam marksheets.

**Preconditions**

- Result session is configured for the same batch/program term.
- Assessment scheme, grading scheme, and result rule are set.
- At least one paper is published.

**Steps**

1. Go to the result session.
2. Open the compute wizard.
3. Confirm scope and configuration.
4. Run compute.
5. Open generated student results and subject result lines.

**Expected Result**

- Results are generated successfully.
- Subject lines are created for eligible subjects only.
- Only published or closed papers contribute to result computation.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-020: Verify unpublished papers are excluded from result computation

**Objective**

Verify that papers not yet published do not affect results.

**Preconditions**

- At least one paper is still in `Draft`, `Scheduled`, `In Progress`, `Marks Entry`, or `Submitted`.
- Result session is ready for compute.

**Steps**

1. Keep one paper unpublished.
2. Run result computation.
3. Review subject result lines for that subject.

**Expected Result**

- Unpublished paper marks are not included in computed results.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-021: Create back exam session for failed students

**Objective**

Verify that a back exam session can be created and populated with papers and marksheets.

**Preconditions**

- At least one student has failed a subject in the regular exam.

**Steps**

1. Open the back exam generation wizard.
2. Select:
   - Mode = `Create New Session`
   - Attempt Type = `Back`
   - Academic Year
   - Dates
   - Based On Exam Session
   - Based On Result Session if applicable
3. Add candidate lines for failed student-subject combinations.
4. Mark `Include`.
5. Run generation.

**Expected Result**

- New back exam session is created.
- Required papers are created only if not already available.
- New marksheets are created for selected candidates.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-022: Verify back exam latest-attempt behavior

**Objective**

Verify latest-attempt handling between old and new marksheets.

**Preconditions**

- Back exam marksheet has been generated for a student with a previous failed marksheet.

**Steps**

1. Open the original regular marksheet.
2. Open the new back exam marksheet.
3. Compare attempt-related fields.

**Expected Result**

- Original marksheet has `Latest Attempt = False`.
- New back exam marksheet has `Latest Attempt = True`.
- New marksheet references the previous marksheet.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-023: Compute results after back exam publication

**Objective**

Verify that result computation uses the latest published back attempt.

**Preconditions**

- Back exam paper is published.
- Back exam marks have been entered.

**Steps**

1. Publish the back exam paper.
2. Recompute the corresponding result session or a dedicated result session.
3. Review the student’s subject result.

**Expected Result**

- Result computation uses the latest published attempt.
- Student outcome reflects the back exam marks instead of the superseded failed attempt where applicable.

**Status**: __________

**Remarks**: ________________________________________

---

### TC-EXAM-024: Verify cancellation and reset behavior

**Objective**

Verify cancel and reset operations for session and paper where supported.

**Preconditions**

- Use non-critical test records.

**Steps**

1. Cancel a non-closed exam session.
2. Reset it to draft if permitted.
3. Use a paper in `Scheduled` or `Submitted` state.
4. Reset the paper to draft as admin.

**Expected Result**

- Session can be cancelled unless already closed.
- Cancelled session can be reset to draft.
- Paper reset is allowed only for supported states and admin-level users.

**Status**: __________

**Remarks**: ________________________________________

---

## 12. Negative Testing Summary

The following negative checks must be performed during UAT:

- End date earlier than start date on exam session
- Duplicate paper for same session, curriculum line, and batch
- Duplicate marksheet for same paper, student, attempt type, and attempt number
- Negative raw marks
- Raw marks above max marks
- Negative grace marks
- Edit attempt on locked marksheet
- Edit attempt on marksheet under published paper
- Invalid lifecycle transition sequence

## 13. Known Functional Areas Requiring Extra Attention

These areas should be observed carefully during testing:

- Batch-wide paper generation with multiple sections teaching the same subject
- Elective filtering based on progression history effective curriculum lines
- Students without elected subjects being treated as taking all subjects
- Attendance snapshot behavior across section-specific classrooms
- Latest-attempt selection in result computation
- Back exam linkage to previous marksheets

## 14. Defect Log Template

Use the following structure for each defect:

- Defect ID
- Test Case ID
- Summary
- Detailed Steps
- Expected Result
- Actual Result
- Severity
- Screenshot/Reference
- Status
- Owner

## 15. Sign-Off

### Business Sign-Off

- Name:
- Role:
- Signature:
- Date:

### QA/UAT Sign-Off

- Name:
- Role:
- Signature:
- Date:

### Technical Sign-Off

- Name:
- Role:
- Signature:
- Date:

