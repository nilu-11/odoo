# EMIS — Education Management Information System
# Comprehensive Testing Plan

**System:** Odoo 19 Custom EMIS Modules
**Prepared for:** QA / Testing Team
**Modules Covered:** 11 custom modules (Phases 1–11)
**Document Version:** 1.0

---

## HOW TO USE THIS DOCUMENT

- Each test case has a unique **ID**, a **Priority** (P1 = Critical, P2 = High, P3 = Medium, P4 = Low), and a **Status** column for testers to fill in (Pass / Fail / Blocked / Skip).
- Run test cases in **module order** — earlier modules are dependencies of later ones.
- **Prerequisites** listed at the start of each section must be completed before that section begins.
- For any **Fail**, record: expected result, actual result, screenshots, and steps to reproduce.
- **Integration tests** in Section 13 must run after all individual module tests pass.

---

## TEST ENVIRONMENT SETUP

### Required User Accounts
Create the following users before testing:

| User | Role | Groups to Assign |
|---|---|---|
| `admin_user` | System Admin | Education Admin |
| `result_admin` | Result Admin | Result Admin |
| `result_officer` | Result Officer | Result Officer |
| `result_viewer` | Result Viewer | Result Viewer |
| `exam_officer` | Exam Officer | Exam Officer |
| `exam_teacher` | Teacher | Exam Teacher |
| `assessment_teacher` | Teacher | Assessment Teacher |
| `attendance_teacher` | Teacher | Attendance Teacher |
| `fee_officer` | Finance | Fee Manager |

### Master Data to Create First
Complete the following in order before running any functional tests:

1. Company settings — name, currency
2. Academic Year (at least 2: one "Open", one "Closed")
3. Department
4. Program (at least 2)
5. Program Terms (auto-generate via action)
6. Subjects (at least 6)
7. Curriculum Lines (map subjects to program terms)
8. Batch (at least 1)
9. Sections (at least 2 per batch)

---

## MODULE 1 — edu_academic_structure

### 1.1 Academic Year

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-001 | Create Academic Year | Navigate to Configuration → Academic Years → Create. Enter name, start date, end date. Save. | Record created. | P1 | |
| M1-002 | Open/Close Academic Year | Set Academic Year to "Open" then "Closed". | State transitions correctly. Closed year cannot be edited. | P1 | |
| M1-003 | Duplicate Year Code | Create two Academic Years with the same code. | System blocks with "unique constraint" error. | P2 | |
| M1-004 | Date validation | Set end_date before start_date. | Validation error raised. | P2 | |

### 1.2 Department

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-005 | Create Department | Create a department with name and code. | Record created successfully. | P1 | |
| M1-006 | Duplicate Department Code | Create two departments with same code. | Unique constraint error. | P2 | |

### 1.3 Program

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-007 | Create Program | Create program with name, code, department, program_type, total_terms=8. | Record saved. | P1 | |
| M1-008 | Auto-generate Program Terms | Click "Generate Program Terms" on a program with total_terms=8. | 8 program term records created (Term 1 to Term 8) linked to program. | P1 | |
| M1-009 | Duplicate Program Code | Create two programs with same code in same company. | Unique constraint error. | P2 | |
| M1-010 | Invalid total_terms | Set total_terms=0. | Validation error: "must be > 0". | P2 | |
| M1-011 | Delete program with batches | Try to delete a program that has an active batch. | System blocks deletion. | P1 | |
| M1-012 | Archive Program | Archive an active program. | Program hidden from default views. Program terms remain. | P3 | |

### 1.4 Subject

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-013 | Create Subject | Create subject with name, code, credit_hours, full_marks, pass_marks. | Record saved. | P1 | |
| M1-014 | Pass marks > Full marks | Set pass_marks > full_marks. | Validation error. | P1 | |
| M1-015 | Negative full_marks | Set full_marks = -1. | Validation error. | P2 | |

### 1.5 Curriculum Lines

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-016 | Add subject to term | On a Program Term, add a subject via curriculum lines. | Curriculum line created with credit_hours/marks auto-populated from subject. | P1 | |
| M1-017 | Duplicate subject in term | Add same subject twice to the same program term. | Unique constraint error. | P1 | |
| M1-018 | Auto-populate from subject | Select a subject on a curriculum line. | credit_hours, full_marks, pass_marks auto-fill from subject defaults. | P2 | |
| M1-019 | Override marks on curriculum line | Manually change full_marks on a curriculum line. | Override is saved; original subject unchanged. | P2 | |

### 1.6 Batch

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-020 | Create Batch | Create batch linked to program and academic year. | Batch created in "draft" state with auto-generated name and code. | P1 | |
| M1-021 | Activate Batch | Click "Activate" on draft batch. | State changes to "active". Program_id, academic_year_id become read-only. | P1 | |
| M1-022 | Close Batch | Click "Close" on active batch. | State changes to "closed". Fields locked. | P1 | |
| M1-023 | Modify locked fields | Try to edit program_id on an "active" batch. | System blocks edit. | P1 | |
| M1-024 | Activate batch in closed year | Try to activate a batch whose academic year is "closed". | Error: Academic year must be open. | P2 | |
| M1-025 | Duplicate batch (no intake) | Create two batches for same program + year without intake_name. | Second creation blocked by unique constraint. | P2 | |
| M1-026 | Duplicate batch (same intake) | Create two batches for same program + year + same intake_name. | Unique constraint error. | P2 | |
| M1-027 | Different intake names | Create two batches for same program + year with intake_name "Spring" and "Fall". | Both created successfully. | P2 | |

### 1.7 Section

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M1-028 | Create Section | Add section "A" to an active batch. | Section created. | P1 | |
| M1-029 | Duplicate section in batch | Create two sections with same name in same batch. | Unique constraint error. | P1 | |
| M1-030 | Section in closed batch | Try to create section in a closed batch. | Error or field lock prevents it. | P2 | |

---

## MODULE 2 — edu_pre_admission_crm

### Prerequisites: Academic Year (Open), Program, Batch

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M2-001 | Create Applicant Profile | Navigate to Pre-Admission → Applicants. Create profile with name, DOB, contact info. | Profile created. | P1 | |
| M2-002 | Add Guardian | On applicant profile, add a guardian with relationship type. | Guardian linked. | P1 | |
| M2-003 | Add Academic History | Add prior academic record (school name, year, percentage). | Record saved. | P2 | |
| M2-004 | Create CRM Lead for applicant | Link a CRM lead to the applicant profile for a target program. | Lead created and linked. | P1 | |
| M2-005 | CRM → Admission conversion | From a qualified lead, trigger "Convert to Admission Application". | Admission application created with applicant data pre-filled. | P1 | |
| M2-006 | Duplicate applicant | Create two profiles with same identification number. | System should warn or block duplicate. | P2 | |
| M2-007 | Incomplete profile conversion | Try to convert a lead where applicant has missing required fields. | System blocks with missing data message. | P2 | |

---

## MODULE 3 — edu_admission

### Prerequisites: Program, Batch, Scholarship Schemes configured

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M3-001 | Create Admission Register | Create an admission register for a program and academic year with open/close dates. | Register created. | P1 | |
| M3-002 | Open Admission Register | Activate the register. | State = open. Applications can now be submitted. | P1 | |
| M3-003 | Submit Admission Application | Create application linked to register + applicant profile. | Application in "submitted" state. | P1 | |
| M3-004 | Review Application | Set state to "under review". | Status updates. Reviewer recorded. | P1 | |
| M3-005 | Approve Application | Approve the application. | Status = approved. Offer letter can be generated. | P1 | |
| M3-006 | Reject Application | Reject the application with a reason. | Status = rejected. | P1 | |
| M3-007 | Generate Offer Letter | On approved application, generate offer letter. | Offer letter created. Status = offer_sent. | P1 | |
| M3-008 | Accept Offer | Applicant accepts offer. | Status = offer_accepted. Ready for enrollment. | P1 | |
| M3-009 | Scholarship assignment | Assign one or more scholarships to an application. | Scholarship discount calculated. Cap enforced correctly. | P1 | |
| M3-010 | Scholarship stacking | Assign two scholarships from the same stacking group. | Stacking rules enforced. Only highest/combined as configured. | P1 | |
| M3-011 | Scholarship cap | Assign scholarship that would exceed cap percentage. | Discount capped at configured maximum. | P1 | |
| M3-012 | Application after register closed | Try to create application after register close date. | System blocks application. | P2 | |
| M3-013 | Duplicate application | Same applicant applies twice to same register. | Second application blocked. | P2 | |
| M3-014 | Ready for enrollment flag | Application with accepted offer shows "Ready for Enrollment". | Flag set correctly. | P1 | |

---

## MODULE 4 — edu_enrollment

### Prerequisites: Application in "offer_accepted" state, Fee Structure configured

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M4-001 | Create Enrollment from Application | Click "Create Enrollment" on a ready application. | Enrollment record created in "draft" state with all academic/financial data copied. | P1 | |
| M4-002 | Academic data snapshot | On created enrollment, verify program, batch, year match application. | Snapshot data matches source application exactly. | P1 | |
| M4-003 | Financial data snapshot | Verify base_total_fee, scholarship amounts, net_fee_after_scholarship are frozen copies. | Financial data matches offer calculations. | P1 | |
| M4-004 | Cannot create duplicate enrollment | Try to create enrollment for same application twice. | Unique constraint error: one enrollment per application. | P1 | |
| M4-005 | Confirm Enrollment | Click "Confirm". All required fields present, fee_confirmed=True. | State = confirmed. Academic/financial fields locked. | P1 | |
| M4-006 | Confirm without fee confirmation | Try to confirm enrollment where fee_confirmed=False. | Blocked: "Fee not confirmed". | P1 | |
| M4-007 | Checklist completion | Complete all checklist items. Verify checklist_complete = True. | Flag updated. | P2 | |
| M4-008 | Activate Enrollment | With checklist complete, click "Activate". | State = active. Student record created/linked. | P1 | |
| M4-009 | Activate without complete checklist | Try to activate with pending checklist items. | Blocked: checklist items listed. | P1 | |
| M4-010 | Edit frozen field after confirm | Try to change program_id on confirmed enrollment. | System blocks: field locked. | P1 | |
| M4-011 | Cancel Enrollment | Admin cancels an active enrollment. | State = cancelled. Reason recorded. | P2 | |
| M4-012 | Reset to draft | Reset cancelled enrollment. | State = draft. Fields editable again. | P2 | |
| M4-013 | Complete Enrollment | Mark active enrollment as completed. | State = completed. | P2 | |
| M4-014 | enrollment_block_reason | On incomplete draft enrollment, read enrollment_block_reason. | Lists all missing items (fee not confirmed, checklist pending, etc.). | P2 | |

---

## MODULE 5 — edu_fees

### Prerequisites: Enrollment in "active" state, Fee Structure, Payment Schedule Templates

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M5-001 | Generate Fee Plan from Enrollment | Trigger fee plan generation on active enrollment. | Fee plan created in "draft" state with lines matching fee structure. | P1 | |
| M5-002 | One plan per enrollment | Try to generate a second fee plan for the same enrollment. | Blocked: unique constraint (one plan per enrollment). | P1 | |
| M5-003 | Fee plan totals | Verify total_original = sum of line original_amounts; total_final = sum of final_amounts. | Computed totals match. | P1 | |
| M5-004 | Scholarship distribution | With scholarship on enrollment, verify discount spread proportionally across eligible lines. | Proportional distribution correct. Non-eligible lines show 0 discount. | P1 | |
| M5-005 | Scholarship cap per line | Discount on any single line cannot exceed that line's original_amount. | Cap enforced per line. | P1 | |
| M5-006 | Confirm Fee Plan | Click "Confirm" on draft plan. | State = confirmed. | P1 | |
| M5-007 | Confirm empty fee plan | Try to confirm plan with no lines. | Blocked: "No fee lines found". | P1 | |
| M5-008 | Activate Fee Plan | Click "Activate" on confirmed plan. | State = active. | P1 | |
| M5-009 | Generate Dues | On active fee plan line with schedule template, generate dues. | Due records created matching schedule (split amounts, due dates). | P1 | |
| M5-010 | Due total = Line final amount | Sum of all dues for a line = line final_amount. | Totals match. | P1 | |
| M5-011 | Record Payment | Create payment record with amount, payment method, date. | Payment in "draft" state. | P1 | |
| M5-012 | Post Payment | Click "Post" on draft payment. | State = posted. | P1 | |
| M5-013 | Auto-allocate payment | Click "Auto-allocate" on posted payment. | Oldest outstanding dues allocated first. Allocated_amount updated. | P1 | |
| M5-014 | Manual allocation | Manually link payment to specific dues with specific amounts. | Allocations saved. Due status updated. | P1 | |
| M5-015 | Over-allocate payment | Try to allocate more than payment amount. | Validation error. | P1 | |
| M5-016 | Due status update | After full payment allocation, due status = paid. | Status = paid. | P1 | |
| M5-017 | Partial payment | Allocate payment covering only part of a due. | Due status = partial. Remaining balance shown. | P1 | |
| M5-018 | Cancel posted payment | Cancel a posted payment. | Allocations released. Due statuses reverted. | P1 | |
| M5-019 | Zero amount payment | Try to create payment with amount = 0. | Blocked: "amount must be > 0". | P2 | |
| M5-020 | Enrollment block check | Check that enrollment activation is blocked if required fees not confirmed. | enrollment_block_reason lists fee issue. | P2 | |
| M5-021 | Close Fee Plan | Click "Close" on active plan. | State = closed. | P2 | |

---

## MODULE 5b — edu_fees_accounting

### Prerequisites: Odoo Accounting module installed, fee dues exist

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M5b-001 | Generate Invoice from Due | On a due record, click "Generate Invoice". | Odoo invoice created and linked. | P1 | |
| M5b-002 | Invoice line amounts | Invoice lines match due amounts and fee heads. | Line items correct. | P1 | |
| M5b-003 | Record accounting payment | Register payment in Odoo accounting against invoice. | Payment reflected on invoice. Due status updated. | P1 | |
| M5b-004 | Credit note generation | Issue credit note for cancelled/overpaid amount. | Credit note created and linked. | P1 | |
| M5b-005 | Reconciliation | Reconcile payment with invoice in accounting. | Accounting entries balanced. | P1 | |
| M5b-006 | Deposit ledger | Record advance deposit. Verify it appears in student ledger. | Deposit recorded. Balance updated. | P2 | |
| M5b-007 | Refund processing | Process refund for deposit. | Refund entry created. Balance adjusted. | P2 | |
| M5b-008 | Double invoice guard | Try to generate invoice for a due that already has one. | Blocked or existing invoice shown. | P1 | |

---

## MODULE 6 — edu_academic_progression

### Prerequisites: Enrollment in "active" state, Batch with sections, Program Terms

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M6-001 | Create Progression History | System creates progression history record when student is enrolled and activated. | Record exists with state = active, correct batch/term/section. | P1 | |
| M6-002 | One active progression per student | Try to create a second active progression for same student. | Unique constraint: only one active record per student. | P1 | |
| M6-003 | Frozen fields after closure | Set progression to "completed". Try to edit batch_id. | Blocked: field is frozen. | P1 | |
| M6-004 | Batch Promotion Wizard | Run batch promotion wizard for a batch. Select next program term. | All active progression records for batch: state → promoted, end_date set, new progression record created with next term. | P1 | |
| M6-005 | Promotion chain | After promotion, promoted_from_id on new record links to old. promoted_to_id on old record links to new. | Chain correct. | P1 | |
| M6-006 | Promote individual student | Manually promote one student via action. | Only that student's record promoted. | P2 | |
| M6-007 | Repeat student | Set a progression to "repeated" state. | State = repeated. Student remains on same term. | P2 | |
| M6-008 | Cancel progression | Admin cancels active progression. | State = cancelled. | P2 | |
| M6-009 | Cannot delete closed progression | Try to delete a closed (completed/promoted) progression record. | Blocked. | P1 | |
| M6-010 | display_name format | Read display_name of an active progression. | Format: "[active] student_no \| batch \| progression_label". | P3 | |
| M6-011 | get_academic_context() | Call get_academic_context() on active progression. | Returns dict with all required fields: student_id, batch_id, program_term_id, section_id, etc. | P2 | |
| M6-012 | Section assignment | Assign section to progression record. | section_id must belong to the same batch (validation). | P2 | |

---

## MODULE 7 — edu_classroom

### Prerequisites: Active batch with sections, Curriculum Lines, Teachers configured

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M7-001 | Create Classroom | Create classroom for batch + section + program_term + curriculum_line + teacher. | Classroom created in "draft". Name and code auto-generated. | P1 | |
| M7-002 | Name auto-generation | Verify classroom name = batch.code + section.name + subject.code + term.label. | Name matches formula. | P2 | |
| M7-003 | Activate Classroom | Click "Activate" on draft classroom. | State = active. core fields locked. Attendance register auto-created. | P1 | |
| M7-004 | Locked fields after activation | Try to change section_id on active classroom. | Blocked: field locked. | P1 | |
| M7-005 | Close Classroom | Click "Close" on active classroom with no in-progress attendance. | State = closed. | P1 | |
| M7-006 | Close with in-progress attendance | Try to close classroom that has in-progress attendance sheets. | Blocked: "in-progress attendance sheets exist". | P1 | |
| M7-007 | Student count smart button | On active classroom, view student count. | Count matches active progressions for that batch+section+term. | P2 | |
| M7-008 | Bulk classroom generation | Use "Generate Classrooms" wizard for a section and program term. | One classroom created per curriculum line. Idempotent (running twice creates no duplicates). | P1 | |
| M7-009 | Duplicate classroom | Try to create two classrooms with same batch+section+curriculum_line+term. | Unique constraint error. | P1 | |
| M7-010 | Attendance register auto-created | After classroom activation, check attendance_register_id is set. | Register exists. | P1 | |
| M7-011 | Section domain | When creating classroom, section_ids only shows sections of the selected batch. | Domain filter works correctly. | P2 | |

---

## MODULE 8 — edu_attendance

### Prerequisites: Active classrooms, Active progression histories

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M8-001 | View Attendance Register | Navigate to classroom → attendance register. | Register linked to classroom. | P1 | |
| M8-002 | Create Attendance Sheet | Create attendance sheet for a classroom on a date. Set time_from/time_to. | Sheet created in "draft". | P1 | |
| M8-003 | Start Session | Click "Start" on draft attendance sheet. | State = in_progress. Lines auto-generated for all active students in section. | P1 | |
| M8-004 | Auto-generated lines | Verify one line per active progression history for the classroom's section/batch/term. | Line count matches active student count. | P1 | |
| M8-005 | Mark attendance | Mark students present/absent/late on lines. | Status values saved. | P1 | |
| M8-006 | Submit Attendance | Click "Submit" with at least one line marked. | State = submitted. Date/time fields locked. | P1 | |
| M8-007 | Submit empty sheet | Try to submit sheet with no lines. | Blocked: "No attendance lines". | P1 | |
| M8-008 | Edit submitted sheet | Try to change session_date on submitted sheet. | Blocked: field locked. | P1 | |
| M8-009 | Admin reset to draft | Admin resets submitted sheet to draft. | State = draft. Lines remain. | P2 | |
| M8-010 | Attendance threshold alert | Check if student below configured threshold (e.g. 75%) triggers alert. | Warning/flag shown on student/classroom view. | P2 | |
| M8-011 | Teacher scope | Login as exam_teacher. Verify teacher only sees their classroom's attendance registers. | Record rule restricts view to own classrooms. | P1 | |
| M8-012 | Officer scope | Login as result_officer. Verify officer sees all attendance records. | No domain restriction. | P1 | |
| M8-013 | Attendance count on classroom | Classroom form shows attendance count smart button. | Count = number of submitted sheets. | P2 | |
| M8-014 | Duplicate sheet on same date | Create two sheets for same classroom on same date. | System should warn or block duplicate. | P2 | |

---

## MODULE 9 — edu_exam

### Prerequisites: Active classrooms, Curriculum lines, Assessment Scheme configured, Published marksheets for result tests

#### 9.1 Assessment Scheme (for Exam module)

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M9-001 | Create Assessment Scheme | Create scheme with name, code, result_period_type. Add scheme lines. | Scheme created. | P1 | |
| M9-002 | Add Scheme Lines | Add lines: First Term Exam (20%), Second Term Exam (20%), Final Exam (30%), Assignment Average (10%), Attendance (10%), Class Performance (10%). | 6 lines created. Total weightage = 100%. | P1 | |
| M9-003 | Total weightage display | Verify total_weightage field on scheme form. | Shows sum = 100.0 (green). Shows non-100 in red. | P2 | |
| M9-004 | Scheme line max_marks=0 | Try to create scheme line with max_marks=0. | Validation error: "must be positive". | P2 | |
| M9-005 | Pass marks > max marks on line | Set pass_marks > max_marks on scheme line. | Validation error. | P2 | |
| M9-006 | Link scheme to exam session | On exam session, select assessment_scheme_id and assessment_scheme_line_id. | Session linked to specific scheme line (e.g. "First Term Exam"). | P1 | |

#### 9.2 Exam Session

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M9-007 | Create Exam Session | Create session with name, exam_type=internal, attempt_type=regular, dates, academic_year, batch. | Session created in "draft". | P1 | |
| M9-008 | Plan Session | Click "Plan". | State = planned. | P1 | |
| M9-009 | Start Session | Click "Start". | State = ongoing. | P1 | |
| M9-010 | Open Marks Entry | Click "Open Marks Entry". | State = marks_entry. | P1 | |
| M9-011 | Publish Session | (As exam_publish_manager) Click "Publish". | State = published. | P1 | |
| M9-012 | Close Session | Click "Close". | State = closed. | P1 | |
| M9-013 | Cancel Session | Cancel from any non-closed state. | State = cancelled. | P1 | |
| M9-014 | Reset to draft | Reset cancelled session. | State = draft. | P2 | |
| M9-015 | Teacher cannot publish | Login as exam_teacher. Try to publish session. | Blocked: insufficient group. | P1 | |
| M9-016 | Date validation | Set date_end before date_start. | Validation error. | P2 | |
| M9-017 | Unique session code | Create two sessions with same code. | Unique constraint error. | P2 | |

#### 9.3 Exam Papers

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M9-018 | Generate Papers from Session | On exam session, use "Generate Papers" wizard. Select classrooms. | One paper created per classroom (subject × section). | P1 | |
| M9-019 | Manual paper creation | Create paper manually: link to session, curriculum_line, section, set max_marks. | Paper created in "draft". | P1 | |
| M9-020 | Duplicate paper in session | Create two papers for same session + curriculum_line + section. | Unique constraint error. | P1 | |
| M9-021 | Schedule Paper | Click "Schedule" on paper. Set exam_date. | State = scheduled. | P1 | |
| M9-022 | Open Marks Entry on paper | Click "Open Marks Entry". | State = marks_entry. Marksheets can be created. | P1 | |
| M9-023 | Publish Paper | (As publish manager) publish paper. | State = published. | P1 | |
| M9-024 | Paper state flow | Draft → Scheduled → In Progress → Marks Entry → Submitted → Published → Closed. | Each transition works. | P1 | |
| M9-025 | Add paper components | Add component to paper (e.g. theory, practical). Set max_marks, pass_marks for each. | Components saved. Sum of component max_marks should not exceed paper max_marks. | P2 | |

#### 9.4 Marksheets

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M9-026 | Generate Marksheets | On a paper in marks_entry state, generate marksheets. | One marksheet per student in the section/batch. | P1 | |
| M9-027 | Snapshot fields | Verify marksheet stores batch_id, section_id, program_term_id, curriculum_line_id, academic_year_id, enrollment_id, student_progression_history_id as standalone (not related) fields. | All snapshot fields populated. | P1 | |
| M9-028 | Enter marks | Set status=present, enter raw_marks. | final_marks computed. is_pass computed. | P1 | |
| M9-029 | Mark absent | Set status=absent. | raw_marks = 0. is_pass = False. | P1 | |
| M9-030 | Mark withheld | Set status=withheld. | Marksheet recorded as withheld. | P2 | |
| M9-031 | Mark malpractice | Set status=malpractice. | Status recorded. | P2 | |
| M9-032 | Marks > max_marks | Enter raw_marks > max_marks. | Validation error. | P1 | |
| M9-033 | Grace marks | Enter grace_marks. Verify final_marks = raw_marks + grace_marks. | Computation correct. | P2 | |
| M9-034 | Pass calculation | Enter marks equal to pass_marks. is_pass = True. Enter one less. is_pass = False. | Pass flag correct. | P1 | |
| M9-035 | Attempt tracking | is_latest_attempt=True on most recent marksheet. Previous ones = False. | Flag maintained correctly. | P1 | |
| M9-036 | Lock marksheet | Set is_locked=True. Try to edit marks. | Edit blocked for non-admin. | P1 | |
| M9-037 | Component-wise marks | On paper with components, enter marks per component. | Component marks aggregated to marksheet total. | P2 | |
| M9-038 | Back exam session creation | Create exam session with attempt_type=back_exam. Link based_on_result_session_id and back_exam_policy_id. | Back exam session created. | P1 | |
| M9-039 | Back exam marksheet | Generate marksheet for back exam session. Verify attempt_no incremented, is_back_attempt=True. | Attempt tracking correct. | P1 | |

#### 9.5 Reports

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M9-040 | Exam Routine Report | Print exam routine from a published session. | PDF generated with paper schedule details. | P2 | |
| M9-041 | Marksheet Report | Print marksheet report for a paper. | PDF shows student names and marks. | P2 | |

---

## MODULE 10 — edu_assessment

### Prerequisites: Active classrooms, Active progression histories, Assessment categories configured

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M10-001 | Create Assessment Category | Create category: name="Assignment", category_type=assignment. | Category saved. | P1 | |
| M10-002 | Default categories | Verify default seed categories exist after install (assignment, class_test, etc.). | Default categories present. | P2 | |
| M10-003 | Create Assessment Record | Create continuous assessment: student, classroom, category, date, max_marks, marks_obtained. | Record in "draft". | P1 | |
| M10-004 | Snapshot fields | Verify enrollment_id, student_progression_history_id, batch_id, etc. are stored (not computed from relation). | All snapshots populated. | P1 | |
| M10-005 | Percentage computation | Verify percentage = (marks_obtained / max_marks) * 100. | Computation correct. | P1 | |
| M10-006 | Marks > Max marks | Enter marks_obtained > max_marks. | Validation error. | P1 | |
| M10-007 | Confirm Assessment | Click "Confirm". | State = confirmed. | P1 | |
| M10-008 | Lock Assessment | Click "Lock". | State = locked. Core fields locked. | P1 | |
| M10-009 | Edit locked assessment | Try to edit marks_obtained on locked record (as teacher). | Blocked for teacher. | P1 | |
| M10-010 | Admin edit locked | As assessment_admin, edit marks on locked record. | Admin can edit. | P2 | |
| M10-011 | Reset draft | Admin resets locked to draft. | State = draft. | P2 | |
| M10-012 | Bulk Generate Wizard | Use bulk generate wizard: select classroom, category, date, max_marks. | One draft assessment record created per student in classroom. | P1 | |
| M10-013 | Bulk Confirm Wizard | Select multiple draft records. Use bulk confirm wizard. | All selected records move to confirmed. | P1 | |
| M10-014 | Bulk Lock Wizard | Select multiple confirmed records. Use bulk lock wizard. | All move to locked. | P1 | |
| M10-015 | Teacher scope | Login as assessment_teacher. Verify teacher only sees assessments for their classrooms. | Record rule restricts view. | P1 | |
| M10-016 | Smart button on classroom | On classroom form, verify assessment smart button shows count. Click to navigate. | Count correct. Navigation works. | P2 | |
| M10-017 | Smart button on student | On student form, verify assessment smart button. | Count and navigation correct. | P2 | |
| M10-018 | Assessment PDF report | Print assessment report for a confirmed record. | PDF generated. | P2 | |

---

## MODULE 11 — edu_result

### Prerequisites: All above modules functional, Published exam marksheets, Confirmed/locked assessment records, Submitted attendance sheets

### 11.1 Configuration

#### Back Exam Policy

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-001 | Create Back Exam Policy | Create policy: name, code, max_attempts=2, carry_forward_internal_marks=True, result_replacement_method=latest_attempt. | Policy saved. | P1 | |
| M11-002 | Activate Policy | Click "Activate". | State = active. | P1 | |
| M11-003 | Max attempts = 0 | Set max_attempts=0. | Validation error: "must be at least 1". | P2 | |
| M11-004 | Cap percentage > 100 | Set cap_max_percentage_after_back = 150. | Validation error. | P2 | |
| M11-005 | Unique code | Create two policies with same code. | Unique constraint error. | P2 | |
| M11-006 | get_eligible_statuses | Check policy with fail=True, absent=True, withheld=False. Call get_eligible_statuses(). | Returns ['fail', 'absent']. | P2 | |

#### Grading Scheme

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-007 | Create Grading Scheme | Create grading scheme with code, result_system=percentage. | Scheme created. | P1 | |
| M11-008 | Add Grade Bands | Add bands: 90-100=A+/4.0, 80-89=A/3.7, 70-79=B+/3.3, 60-69=B/3.0, 50-59=C/2.0, 40-49=D/1.0, 0-39=F/0.0 (is_fail=True). | 7 bands created. | P1 | |
| M11-009 | Overlapping bands | Add band 85-95. | Validation error: "overlaps with band 90-100". | P1 | |
| M11-010 | Min > Max on band | Set min_percent=80, max_percent=70. | Validation error. | P1 | |
| M11-011 | Band out of range | Set max_percent=110. | Validation error: "must be between 0 and 100". | P2 | |
| M11-012 | get_grade() | Call grading_scheme.get_grade(85.0). | Returns ('A', 3.7, remark, False). | P1 | |
| M11-013 | get_grade() fail band | Call grading_scheme.get_grade(35.0). | Returns ('F', 0.0, remark, True). | P1 | |
| M11-014 | get_grade() exact boundary | Call get_grade(90.0). | Returns 'A+' (inclusive min). Call get_grade(89.0). Returns 'A'. | P1 | |
| M11-015 | Duplicate scheme code | Create two grading schemes with same code. | Unique constraint error. | P2 | |

#### Assessment Scheme

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-016 | Create Annual Weighted Scheme | Create scheme: result_period_type=annual, result_system=both. Back_exam_policy set. | Scheme saved. | P1 | |
| M11-017 | Add scheme lines (full annual) | Add: First Term Exam 20%, Second Term Exam 20%, Final Exam 30%, Assignment Avg 10%, Class Performance 10%, Attendance 10%. Set source_type and aggregation for each. | 6 lines. Total weightage = 100. | P1 | |
| M11-018 | Total weightage = 100 (green) | Verify total_weightage display on scheme form. | Shows 100.0 in green indicator. | P2 | |
| M11-019 | Total weightage ≠ 100 (red) | Temporarily remove one line. | Shows non-100 in red indicator. | P2 | |
| M11-020 | Link exam sessions to lines | On "First Term Exam" line, link the specific first-term exam session via exam_session_ids. | Many2many link saved. | P1 | |
| M11-021 | Link assessment categories | On "Assignment Average" line, link assignment categories via assessment_category_ids. | Categories linked. | P1 | |
| M11-022 | Scheme with no scope | Create scheme with no program_id/academic_year/term (generic). | Scheme created as reusable across programs. | P2 | |
| M11-023 | Scheme scope filtering | Create scheme scoped to specific program. | When used on result session for that program, it applies correctly. | P2 | |
| M11-024 | Activate Scheme | Click "Activate". | State = active. | P1 | |
| M11-025 | action_view_scheme_lines | Click "Lines" smart button on scheme form. | Opens scheme line list filtered to this scheme. | P2 | |

#### Result Rule

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-026 | Create Result Rule | Create rule: minimum_overall_percent=40, fail_on_any_mandatory_component=True, allow_backlog=True, max_backlog_subjects=3, attendance_shortage_action=warn. | Rule saved. | P1 | |
| M11-027 | Activate Rule | Click "Activate". | State = active. | P1 | |
| M11-028 | Min percent > 100 | Set minimum_overall_percent=105. | Validation error. | P2 | |
| M11-029 | Negative max backlog | Set max_backlog_subjects=-1. | Validation error. | P2 | |

### 11.2 Result Session

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-030 | Create Result Session | Create session: link assessment_scheme, grading_scheme, result_rule. Set academic_year, program, batch, program_term. | Session created. Name auto-generated (RS-2024-0001). | P1 | |
| M11-031 | Sequence auto-generation | Create multiple sessions. Verify names auto-increment. | Sequences correct. | P2 | |
| M11-032 | Scheme locked after draft | After moving to processing, try to change assessment_scheme_id. | Blocked: field readonly outside draft. | P1 | |

### 11.3 Result Computation Engine

#### Setup for computation tests:
Before running these, ensure:
- At least 3 students have active progression histories for the test batch + term
- Exam sessions are published with marksheets entered for all students × subjects
- Continuous assessment records are confirmed/locked for all students × subjects
- Attendance sheets are submitted

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-033 | Open Compute Wizard | On draft result session, click "Compute Results". | Wizard opens showing estimated student count and subject count. | P1 | |
| M11-034 | Estimated scope preview | Wizard shows estimated_student_count and estimated_curriculum_line_count. | Counts match active progressions and curriculum lines in scope. | P2 | |
| M11-035 | Run computation | In compute wizard, click "Compute Now". | Result processing starts. Redirects to student results. | P1 | |
| M11-036 | Session moves to processing | After computation triggered, result session state = processing. | State = processing. | P1 | |
| M11-037 | Subject lines created | After computation, edu.result.subject.line records exist for each student × subject. | Line count = students × subjects. | P1 | |
| M11-038 | Component breakdown | Each subject line has component_ids records (one per scheme line). | Components show raw_obtained, normalized, weighted_contribution. | P1 | |
| M11-039 | Weighted total calculation | For a known student with known marks: verify percentage = sum of weighted contributions. | Manual calculation matches computed value. | P1 | |
| M11-040 | Grade assignment | Subject with percentage=85 → grade should be "A" per grading scheme. | Grade letter and grade point assigned correctly. | P1 | |
| M11-041 | Student result created | edu.result.student records created for each student. | One record per student. | P1 | |
| M11-042 | Student result GPA | Verify GPA = credit-weighted average of grade points across subjects. | GPA calculation correct. | P1 | |
| M11-043 | Student average percentage | Student percentage = average of subject percentages. | Calculation correct. | P1 | |
| M11-044 | Pass result status | Student passing all subjects above minimum_overall_percent → result_status = pass. | Status = pass. | P1 | |
| M11-045 | Fail result status | Student failing 4 subjects with max_backlog_subjects=3 → result_status = fail. | Status = fail. | P1 | |
| M11-046 | Promoted with backlog | Student failing exactly 2 subjects (≤ max_backlog_subjects=3) → result_status = promoted_with_backlog. | Status = promoted_with_backlog. | P1 | |
| M11-047 | Mandatory component fail | Student passes overall percentage but fails a mandatory component with requires_separate_pass=True. | is_pass=False on that subject line. | P1 | |
| M11-048 | Absent handling | Student with status=absent on marksheet → subject line: is_absent=True, is_pass=False. | Handled correctly. | P1 | |
| M11-049 | Withheld handling | Student with status=withheld → subject line: is_withheld=True. | Handled correctly. | P2 | |
| M11-050 | Malpractice handling | Student with status=malpractice → subject line: is_malpractice=True. student result_status = malpractice. | Handled correctly. | P2 | |
| M11-051 | Backlog flagging | Failed subjects have is_backlog_subject=True, backlog_flag=True, is_back_exam_eligible=True (if rule allows). | Flags set correctly. | P1 | |
| M11-052 | Distinction flag | Student with average_percentage ≥ 80% and no fail → distinction_flag=True. | Flag set. | P2 | |
| M11-053 | Snapshot fields on result lines | Verify batch_id, section_id, program_term_id, student_progression_history_id are stored (not relational). | All snapshots populated. | P1 | |
| M11-054 | Recompute wipes old results | Run computation twice. Second run replaces (not doubles) results. | Record count stays the same after second run. | P1 | |
| M11-055 | No data for student-subject | Student has no marksheet for a subject. | Result engine skips that combination (no subject line created) or marks as absent. | P2 | |

#### Aggregation method tests

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-056 | Aggregation: total | Scheme line aggregation=total. Student has 3 assessment records for same subject. | Total = sum of all three marks. | P1 | |
| M11-057 | Aggregation: average | Scheme line aggregation=average. Student has 3 records: 70, 80, 90. | Average = 80. | P1 | |
| M11-058 | Aggregation: best | Scheme line aggregation=best, best_of_count=2. Scores: 60, 80, 90. | Best 2 = 80+90 = 170 out of double max. | P1 | |
| M11-059 | Aggregation: latest | Scheme line aggregation=latest. Two records with dates. | Takes the last record's marks. | P1 | |
| M11-060 | Drop lowest | drop_lowest=1. Scores: 40, 70, 80. | Drops 40, uses 70+80. | P2 | |
| M11-061 | Attendance source | Scheme line source_type=attendance. 8/10 sessions attended. Max_marks=10. | attendance_percent=80%, marks=8.0 out of 10. | P1 | |
| M11-062 | No attendance data | Scheme line source_type=attendance. No submitted sheets for student-subject. | Attendance marks = 0 (or skipped). | P2 | |

### 11.4 Result Session State Machine

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-063 | Verify session | After computation, click "Verify". | State = verified. verified_by = current user. | P1 | |
| M11-064 | Verify without results | Try to verify session with no student results. | Blocked: "No student results found". | P1 | |
| M11-065 | Publish session | (As result_publish_manager) Click "Publish". | State = published. published_on timestamp set. All student results get published_on. | P1 | |
| M11-066 | Officer cannot publish | Login as result_officer. Try to publish. | Blocked: insufficient group. | P1 | |
| M11-067 | Close session | Click "Close" on published session. | State = closed. | P1 | |
| M11-068 | Reset to draft | Reset from processing/verified state. | State = draft. | P2 | |
| M11-069 | Cannot reset closed session | Try to reset a closed session. | Blocked: "Closed sessions cannot be reset." | P1 | |
| M11-070 | Edit published result line | Try to modify percentage on a published subject line. | Blocked for protected fields. | P1 | |
| M11-071 | Remarks on published line | Edit remarks on a published subject line. | Allowed: remarks is in the allowed set. | P2 | |

### 11.5 Back Exam Recomputation

#### Setup: Result session must be in "verified" or "published" state with some failed subjects. Back exam session must be published with marksheets.

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-072 | Open Recompute Wizard | On a result session with backlogs, click "Recompute After Back Exam". | Wizard opens. eligible_subject_line_count and affected_student_count shown. | P1 | |
| M11-073 | Select back exam session | In wizard, select the published back exam session. | Session selectable (attempt_type=back, state=published). | P1 | |
| M11-074 | Policy auto-populated | If scheme has a back_exam_policy, it auto-populates in wizard. | Policy pre-filled. | P2 | |
| M11-075 | Run recomputation | Click "Recompute Now". | New subject lines created for students who took back exam. | P1 | |
| M11-076 | Original line superseded | Original failed subject line has superseded_by_result_subject_line_id set. | Chain preserved. History intact. | P1 | |
| M11-077 | New line has recomputed_after_back=True | New subject line: recomputed_after_back=True, has_back_exam=True, attempt_count=2. | Flags correct. | P1 | |
| M11-078 | Carry-forward internal marks | Policy has carry_forward_internal_marks=True. Internal exam marks not replaced. | Original internal component retained in new line's components. | P1 | |
| M11-079 | Only failed component replaced | With result_replacement_method=replace_failed_component_only: only the back-exam source replaces; other components carried forward. | Partial replacement correct. | P1 | |
| M11-080 | Latest attempt replacement | With result_replacement_method=latest_attempt: back exam marks fully replace subject score. | Latest marks used. | P1 | |
| M11-081 | Highest attempt | With result_replacement_method=highest_attempt: best of original or back exam used. | Highest score wins. | P1 | |
| M11-082 | Back exam cleared flag | If student passes after back exam: back_exam_cleared=True. | Flag set. | P1 | |
| M11-083 | Student result updated | After recomputation, student-level result recalculated. Cleared backlogs reduce remaining_backlog_count. | remaining_backlog_count decreases by number cleared. | P1 | |
| M11-084 | Promotion status update | Student who was "fail" now has all backlogs cleared → result_status = promoted_with_backlog or pass. | Status updated correctly. | P1 | |
| M11-085 | Percentage cap | Policy has cap_max_percentage_after_back=60. Student would score 75% after back exam. | Final percentage capped at 60%. | P1 | |
| M11-086 | Max attempts respected | Student already used 2 attempts (max_attempts=2). Try to run recompute for 3rd time. | Attempt skipped for that student. | P1 | |
| M11-087 | Student without back exam marks | Student eligible for back exam but didn't sit back exam. | No new line created for that student. Original remains. | P2 | |
| M11-088 | Unpublished back exam session | Try to recompute using a back exam session in "marks_entry" state. | Validation error: "session must be published". | P1 | |

### 11.6 Reports

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-089 | Result Sheet PDF | On a published student result, print "Result Sheet". | PDF shows: student info, per-subject marks, grade, status, overall summary, signature blocks. | P1 | |
| M11-090 | Subject Tabulation PDF | On a published result session, print "Subject Tabulation Sheet". | PDF shows per-subject tables with all students' marks. | P1 | |
| M11-091 | Student Result Summary PDF | Print "Student Result Summary" on result session. | PDF shows all students with percentage, GPA, grade, status, backlog count. | P1 | |
| M11-092 | Backlog Report PDF | Print "Backlog Report" on result session. | PDF lists only backlog subjects with eligibility and cleared status. | P1 | |
| M11-093 | Back Exam Eligibility PDF | Print "Back Exam Eligibility Report". | PDF lists students eligible for back exam (not yet cleared). | P1 | |
| M11-094 | Empty reports | Print reports on session with no results. | "No data" message shown. No crash. | P2 | |

### 11.7 Security / Access Control

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-095 | Viewer sees only published sessions | Login as result_viewer. Navigate to Result Sessions. | Only sessions in published/closed state visible. | P1 | |
| M11-096 | Viewer cannot edit | Result viewer tries to edit a session. | Fields readonly / save blocked. | P1 | |
| M11-097 | Officer sees all sessions | Login as result_officer. | All sessions visible regardless of state. | P1 | |
| M11-098 | Officer cannot delete session | Result officer tries to delete a session. | Blocked: no delete permission. | P1 | |
| M11-099 | Publish manager can publish | Login as result_publish_manager. Click "Publish". | Succeeds. | P1 | |
| M11-100 | Admin can delete | Login as result_admin. Delete a draft session. | Deletion succeeds. | P2 | |
| M11-101 | Admin can reset closed | Via Python/admin interface, check reset_to_draft is blocked for closed. | Even admin cannot reset closed session (code-level guard). | P1 | |
| M11-102 | Configuration access | Viewer tries to access Assessment Schemes menu. | Menu not visible (admin-only menu). | P2 | |

### 11.8 Smart Buttons

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M11-103 | Student form → Results | Navigate to a student record. Click "Results" smart button. | Opens student result records filtered to this student. | P2 | |
| M11-104 | Batch form → Result Sessions | On batch form, click "Result Sessions" smart button. | Opens result sessions filtered to this batch. | P2 | |
| M11-105 | Exam session → Result sessions | On exam session, click "Result Sessions" smart button. | Opens related result sessions (same scheme + year). | P2 | |
| M11-106 | Result session → Subject Lines | On result session, click "Subject Lines" smart button. | Opens subject lines filtered to session. | P2 | |
| M11-107 | Result session → Students | On result session, click "Students" smart button. | Opens student results filtered to session. | P2 | |
| M11-108 | Counts on result session | Pass count + Fail count = total result count? | Counts correct and consistent. | P2 | |

---

## MODULE 12 — Menu & Navigation

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| M12-001 | Education root menu visible | Login as any education user. | "Education" menu visible in top navigation. | P1 | |
| M12-002 | Results submenu (viewer) | Login as result_viewer. | "Results" → "Student Results" visible. "Configuration" not visible. | P1 | |
| M12-003 | Results submenu (admin) | Login as result_admin. | All menus visible including Configuration submenu. | P1 | |
| M12-004 | Backlog Report menu | Navigate to Results → Reports → Backlog Report. | Opens subject lines filtered to backlog. | P2 | |
| M12-005 | Pass/Fail Summary menu | Navigate to Results → Reports → Pass/Fail Summary. | Opens student results grouped by status and batch. | P2 | |
| M12-006 | Configuration menus | Navigate to Results → Configuration → each submenu. | All configuration views open correctly. | P2 | |

---

## SECTION 13 — FULL END-TO-END INTEGRATION TESTS

These tests verify the complete student lifecycle across all modules.

### 13.1 Complete Student Journey: Admission → Result

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| E2E-001 | Full admission pipeline | Create applicant → CRM lead → Admission application → Review → Approve → Offer letter → Accept. | Application state = offer_accepted. | P1 | |
| E2E-002 | Enrollment and fee plan | Create enrollment from accepted application → Confirm → Activate → Auto-generate fee plan. | Enrollment active. Fee plan created with correct amounts. | P1 | |
| E2E-003 | Payment and due clearing | Record payment → Post → Auto-allocate → All dues paid. | All dues = paid. No outstanding balance. | P1 | |
| E2E-004 | Progression record created | After enrollment activation, verify progression history record exists with correct batch/term/section. | Record active with correct snapshot fields. | P1 | |
| E2E-005 | Classroom attendance tracking | Teacher creates classroom attendance sheet → Marks students → Submits. | Attendance submitted. Lines include the enrolled students. | P1 | |
| E2E-006 | Assessment records | Teacher creates assignment assessment for students in classroom. Confirms and locks. | Assessment records locked with correct student snapshots. | P1 | |
| E2E-007 | Exam creation and marks entry | Create exam session → Generate papers → Open marks entry → Enter marks for all students → Publish. | All marksheets published. | P1 | |
| E2E-008 | Result computation with annual weighted scheme | Create result session with annual weighted scheme (exam + assignment + attendance). Link scheme lines to exam sessions and assessment categories. Run computation. | Subject lines created for each student × subject. Weighted percentages computed from all sources. | P1 | |
| E2E-009 | Result publication | Verify session → Publish → Students can view their result (as viewer). | Result published. Viewer sees published results. | P1 | |
| E2E-010 | Batch promotion after result | Run batch promotion wizard. All passed students promoted to next term. | New progression records created. Old ones = promoted. Batch current_program_term updated. | P1 | |

### 13.2 Back Exam Lifecycle

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| E2E-011 | Identify failed students | After result computation, check is_back_exam_eligible flags. | Failed students correctly identified. | P1 | |
| E2E-012 | Create back exam session | Create new exam session with attempt_type=back_exam, linked to result session. Generate papers and marksheets for failed students only. | Back exam session created. Marksheets for failing students. | P1 | |
| E2E-013 | Enter back exam marks | Enter marks for failed students in back exam. Publish back exam session. | Back exam published. | P1 | |
| E2E-014 | Recompute results | Run recompute backlog wizard on original result session. Select back exam session and policy. | New subject lines created. Carry-forward rules applied. | P1 | |
| E2E-015 | Verify outcome | Students who scored ≥ pass marks in back exam: back_exam_cleared=True, result_status updated. | Cleared backlog reflected on student result. | P1 | |
| E2E-016 | Historical integrity | Original (superseded) subject lines still exist with superseded_by link. | History preserved. No data deleted. | P1 | |

### 13.3 Snapshot Integrity After Promotion

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| E2E-017 | Exam marksheet snapshot after promotion | Promote a batch. Then view an old marksheet. | Marksheet still shows original batch, section, program_term (not current promoted state). | P1 | |
| E2E-018 | Assessment record snapshot after promotion | View old assessment records after batch promotion. | Records still show original progression context. | P1 | |
| E2E-019 | Result line snapshot after promotion | View old result subject lines after batch promotion. | Lines still reference original batch and term. | P1 | |
| E2E-020 | Fee plan snapshot | View fee plan after enrollment modifications (if allowed). | Fee amounts remain as captured at enrollment time. | P1 | |

### 13.4 Concurrent and Edge Cases

| ID | Test Case | Steps | Expected Result | Priority | Status |
|---|---|---|---|---|---|
| E2E-021 | Student with no exam marks in result scope | Run result computation for a student who has no published marksheets. | Student either skipped in results or subject line shows absent/0. No crash. | P2 | |
| E2E-022 | Result session with no students in scope | Run result computation where no progression histories exist. | Warning logged. No result lines created. Session moves to processing (empty). No crash. | P2 | |
| E2E-023 | Result session with no curriculum lines | Compute results where program_term has no curriculum lines. | Empty result session. No crash. | P2 | |
| E2E-024 | Multiple result sessions for same batch/term | Create two result sessions for the same batch and term. Run both. | Both sessions compute independently. No data overlap. | P2 | |
| E2E-025 | Recompute back exam twice | Run recompute wizard twice for same back exam session. | Second run: students already at max attempts are skipped. No duplicate lines. | P2 | |
| E2E-026 | Delete student after result computed | Admin deletes student record after result session is published. | ondelete='restrict' on result records prevents deletion or raises clear error. | P2 | |

---

## SECTION 14 — NEGATIVE TESTING (Boundary & Error Conditions)

| ID | Test Case | Expected Result | Priority | Status |
|---|---|---|---|---|
| N-001 | Install module without dependencies | Try to install edu_result without edu_exam installed. | Installation blocked: dependency error. | P1 | |
| N-002 | All required fields missing | Submit any form with no required fields. | Field-level validation errors displayed clearly. | P1 | |
| N-003 | SQL injection in search | Type `'; DROP TABLE --` in any search field. | No SQL error. Input treated as literal string. | P1 | |
| N-004 | XSS in text fields | Enter `<script>alert('xss')</script>` in a remarks field. | Output escaped. No script execution. | P1 | |
| N-005 | Concurrent edit conflict | Two users edit same record simultaneously. | ORM optimistic locking raises error on second save. | P2 | |
| N-006 | Very large marks | Enter raw_marks = 999999. max_marks = 100. | Validation error: marks > max_marks. | P2 | |
| N-007 | Negative marks | Enter raw_marks = -50. | Validation error or zero enforced. | P2 | |
| N-008 | Float precision | Enter marks = 33.333333333. | Stored and displayed with configured precision (no crash). | P3 | |
| N-009 | Empty result session recompute | Click "Compute" on session with no scheme lines. | Graceful handling: no crash, appropriate message. | P2 | |
| N-010 | Result rule with 0% minimum | Set minimum_overall_percent=0. Compute results. | All students pass (no fail threshold). | P3 | |
| N-011 | Scheme weightage = 0 on a line | Add line with weightage_percent=0. | Line contributes 0 to final (not an error, just 0 contribution). | P3 | |
| N-012 | Back exam with no eligible students | Run recompute wizard where no students are back_exam_eligible. | Wizard shows eligible_subject_line_count=0. No new lines created. | P2 | |

---

## SECTION 15 — PERFORMANCE TESTS

| ID | Test Case | Threshold | Priority | Status |
|---|---|---|---|---|
| P-001 | Result computation: 100 students × 8 subjects | Run result computation for 100 students with 8 subjects each (800 subject lines). | Completes in < 30 seconds. No timeout. | P1 | |
| P-002 | Result computation: 500 students | Same as above but 500 students × 8 subjects (4000 subject lines). | Completes in < 120 seconds. | P2 | |
| P-003 | List view loading | Open Student Results list with 1000+ records. | Page loads in < 5 seconds. Pagination works. | P2 | |
| P-004 | PDF report: 200 student results | Print Student Result Summary for 200 students. | PDF generates in < 20 seconds. | P2 | |
| P-005 | Bulk attendance generation | Generate attendance sheets for 50 classrooms simultaneously. | All sheets created correctly. No partial failures. | P2 | |
| P-006 | Bulk assessment generation wizard | Generate assessments for 5 classrooms × 30 students each. | 150 records created. No timeout. | P2 | |
| P-007 | Batch promotion: 300 students | Run batch promotion wizard for 300 students. | Completes in < 60 seconds. All progressions updated. | P1 | |

---

## SECTION 16 — DATA INTEGRITY VERIFICATION

Run these checks **after** a full test cycle:

| ID | Check | Query / Verification Method | Expected | Priority | Status |
|---|---|---|---|---|---|
| DI-001 | No orphaned subject components | Check edu.result.subject.component where result_subject_line_id is deleted. | 0 orphan records. | P1 | |
| DI-002 | Student result count = subject line student count | For each result session: count(distinct student_id in subject lines) = count(student results). | Counts match. | P1 | |
| DI-003 | No duplicate active progressions | Each student has at most 1 active progression history. | 0 duplicate active records. | P1 | |
| DI-004 | All superseded lines have replacement | Subject lines with superseded_by_result_subject_line_id set → referenced line exists. | No dangling references. | P1 | |
| DI-005 | Snapshot fields populated | All edu.result.subject.line records have non-null: student_progression_history_id, batch_id, program_term_id, subject_id. | 0 null snapshot fields. | P1 | |
| DI-006 | Marksheet attempt tracking | For any student-paper pair: exactly one marksheet has is_latest_attempt=True. | 0 papers with multiple latest attempts. | P1 | |
| DI-007 | Payment allocation integrity | For each payment: sum(allocation.allocated_amount) ≤ payment.amount. | No over-allocated payments. | P1 | |
| DI-008 | Due amount integrity | For each due: sum(allocations.allocated_amount) ≤ due.due_amount. | No over-allocated dues. | P1 | |
| DI-009 | Enrollment uniqueness | Each application_id appears on exactly one enrollment. | 0 duplicate application enrollments. | P1 | |
| DI-010 | Fee plan per enrollment | Each enrollment has at most 1 fee plan. | 0 enrollments with multiple fee plans. | P1 | |

---

## SECTION 17 — REGRESSION CHECKLIST

After every code change, re-run these minimum tests:

- [ ] M1-007 (Create Program) + M1-008 (Generate terms)
- [ ] M1-020 → M1-022 (Batch lifecycle)
- [ ] M4-001 → M4-009 (Enrollment pipeline)
- [ ] M5-001 → M5-016 (Fee plan and payment)
- [ ] M6-004 (Batch promotion)
- [ ] M9-007 → M9-012 (Exam session lifecycle)
- [ ] M9-026 → M9-035 (Marksheet entry)
- [ ] M11-033 → M11-054 (Result computation)
- [ ] M11-063 → M11-070 (Result session states)
- [ ] M11-072 → M11-088 (Back exam recomputation)
- [ ] E2E-001 → E2E-010 (Full end-to-end)

---

## DEFECT REPORTING TEMPLATE

When a test case fails, file the defect with:

```
Defect ID   : DEF-XXXX
Test Case ID: (from above)
Priority    : P1 / P2 / P3
Module      : (e.g. edu_result)
Title       : Short description of failure

Environment:
  Odoo Version  : 19
  Module Version: 19.0.1.0.0
  User Role     : (e.g. result_officer)
  Browser       :

Steps to Reproduce:
  1.
  2.
  3.

Expected Result:
  (what should happen)

Actual Result:
  (what actually happened)

Server Error (if any):
  (paste traceback)

Screenshots: (attach)

Notes:
  (any additional context)
```

---

## TEST SIGN-OFF

| Module | Tester | Date Tested | P1 Pass | P2 Pass | Defects Filed | Sign-off |
|---|---|---|---|---|---|---|
| edu_academic_structure | | | | | | |
| edu_pre_admission_crm | | | | | | |
| edu_admission | | | | | | |
| edu_enrollment | | | | | | |
| edu_fees | | | | | | |
| edu_fees_accounting | | | | | | |
| edu_academic_progression | | | | | | |
| edu_classroom | | | | | | |
| edu_attendance | | | | | | |
| edu_exam | | | | | | |
| edu_assessment | | | | | | |
| edu_result | | | | | | |
| Integration Tests | | | | | | |
| **OVERALL** | | | | | | |

**System accepted for production use when:** All P1 test cases pass AND no open P1/P2 defects remain unresolved.
