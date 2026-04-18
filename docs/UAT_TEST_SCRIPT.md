# EMIS UAT Test Script
**Version:** 19.0 | **Project:** Lincoln College EMIS
**Prepared by:** Tech Lead | **Date:** 2026-04-17
**Deadline:** Friday EOD

---

## How to Use This Script

1. Follow each step exactly as written
2. Mark each step **PASS** or **FAIL**
3. If FAIL — write what happened, take a screenshot, log it in the bug sheet below
4. Do NOT fix bugs yourself — log them and continue testing
5. If stuck for 2 hours: ask the tech lead immediately

**Bug reporting format:**
```
BUG-001 | Module | Step # | What you did | What happened | What should have happened
```

---

## Test Data to Use

Before starting, create this test data (or confirm it already exists):
- **Academic Year:** 2025-2026 (active)
- **Program:** BCA (Bachelor of Computer Application) — 6 semesters
- **Program:** +2 Science — 2 years / 4 terms
- **Batch:** BCA-2025
- **Section:** Section A
- **Fee Structure:** BCA Standard Fee

If any of this doesn't exist, create it first using the user guide, or ask the tech lead.

---

## RAJESH — Pre-Admission to Enrollment (Phases 1-4)

**Your job:** Test the complete flow from first student inquiry to student creation.
**Time estimate:** 2 days
**Report bugs to:** Tech lead

---

### TEST BLOCK 1: Academic Structure Setup

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 1.1 | Go to **Education > Academic > Academic Years** | List of academic years shown | | |
| 1.2 | Open the active academic year 2025-2026 | Year details shown with terms listed | | |
| 1.3 | Confirm at least 2 terms exist (Semester 1, Semester 2) | Terms visible with start/end dates | | |
| 1.4 | Go to **Education > Configuration > Programs** | Program list shown | | |
| 1.5 | Open BCA program — confirm 6 progression stages exist (Sem 1 to Sem 6) | 6 stages visible | | |
| 1.6 | Go to **Education > Academic > Batches** | Batch list shown | | |
| 1.7 | Open BCA-2025 batch — confirm Section A exists | Section A listed under batch | | |
| 1.8 | Try creating a new batch with no name — confirm error shown | Validation error, cannot save | | |

---

### TEST BLOCK 2: Pre-Admission CRM

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 2.1 | Go to **Education > Pre-Admission > Inquiries & Leads** | Kanban/list view shown | | |
| 2.2 | Create a new inquiry: Name = "Ram Sharma", Program = BCA, Phone = 9800000001 | Inquiry created in "Inquiry" stage | | |
| 2.3 | Move inquiry to "Prospect" stage | Stage changes to Prospect | | |
| 2.4 | Move inquiry to "Qualified" stage | Stage changes to Qualified | | |
| 2.5 | Click **Create Applicant Profile** from the inquiry | Applicant profile form opens | | |
| 2.6 | Fill in applicant: DOB, gender, address, citizenship number | All fields accept input | | |
| 2.7 | Add a guardian: Name = "Hari Sharma", Relation = Father, Phone = 9800000002 | Guardian saved on profile | | |
| 2.8 | Add academic history: +2 Science, 2023, GPA 3.2 | Academic history saved | | |
| 2.9 | Click **Mark Ready for Application** | Status changes, button disappears or changes | | |
| 2.10 | Try creating a second inquiry with the same phone number | Check: does system warn about duplicate? Log result either way | | |

---

### TEST BLOCK 3: Admission

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 3.1 | Go to **Education > Admission > Applications** | Application list shown | | |
| 3.2 | Click **Convert to Application** from the applicant profile (Ram Sharma) | Application created, linked to applicant | | |
| 3.3 | Open the application — verify applicant details are pulled correctly | Name, DOB, program auto-filled | | |
| 3.4 | Click **Submit** application | Status changes to "Submitted" | | |
| 3.5 | Click **Review** application | Status changes to "Under Review" | | |
| 3.6 | Click **Scholarship Review** — enter 10% scholarship | Scholarship saved on application | | |
| 3.7 | Click **Generate Offer Letter** | Offer letter document generated, visible as attachment or PDF | | |
| 3.8 | Click **Accept Offer** | Status changes to "Accepted", fees/scholarship frozen | | |
| 3.9 | Try to change scholarship amount after accepting offer | Should be blocked or show warning | | |
| 3.10 | Click **Mark Ready for Enrollment** | Status changes to "Ready for Enrollment" | | |
| 3.11 | Try to reject an accepted application — what happens? | Log result | | |

---

### TEST BLOCK 4: Enrollment

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 4.1 | Go to **Education > Enrollment** | Enrollment list shown | | |
| 4.2 | Click **Create Enrollment** from Ram Sharma's accepted application | Enrollment form opens, linked to application | | |
| 4.3 | Verify fee plan is auto-populated from the fee structure | Fee lines visible on enrollment | | |
| 4.4 | Click **Confirm** enrollment | Status changes to Confirmed | | |
| 4.5 | Complete the enrollment checklist — mark all documents as received | Checklist items checked | | |
| 4.6 | Click **Activate** enrollment | Status changes to Active | | |
| 4.7 | Click **Create Student** from the active enrollment | Student record created, student number assigned | | |
| 4.8 | Open the student record — verify: name, program, batch, section are correct | All fields populated correctly | | |
| 4.9 | Verify smart buttons are visible: Applicant, Guardians, Enrollment, Progressions | All smart buttons clickable and open correct records | | |
| 4.10 | Try to change the student number — should be locked | Field is read-only after creation | | |
| 4.11 | Try to create a second enrollment for the same application | Should be blocked | | |

**Edge case — repeat full flow for a +2 student (different program):**
Create a second inquiry → applicant → application → enrollment → student for a +2 Science student. Verify the flow works for both program types.

---

## NILIMA — Academic Operations to Results (Phases 5-8)

**Your job:** Test everything after a student is created — classroom, attendance, exams, results.
**Prerequisite:** At least 2 students must exist (ask Rajesh for test students, or create 2 yourself using Block 4 above).
**Time estimate:** 2 days
**Report bugs to:** Tech lead

---

### TEST BLOCK 5: Academic Progression & Classrooms

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 5.1 | Go to **Education > Academic > Batches** — open BCA-2025 | Batch detail with students listed | | |
| 5.2 | Click **Promote Batch** to Semester 1 | Progression records created for all students | | |
| 5.3 | Click **Assign Sections** — assign all students to Section A | Students assigned, shown on section | | |
| 5.4 | Click **Generate Classrooms** for the batch | Classrooms created (one per subject per section) | | |
| 5.5 | Go to **Education > Classrooms** — verify classrooms are listed | Classrooms visible with subject, section, teacher fields | | |
| 5.6 | Open one classroom — assign a teacher | Teacher saved | | |
| 5.7 | Click **Activate** on the classroom | Status changes to Active | | |
| 5.8 | Try to delete an active classroom — should be blocked | Error or warning shown | | |
| 5.9 | Open classroom — verify student list is populated | Students in section shown | | |

---

### TEST BLOCK 6: Attendance

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 6.1 | Open an active classroom — click **Take Attendance Today** | Attendance form opens with student list | | |
| 6.2 | Mark 1 student Present, 1 student Absent | Status saved per student | | |
| 6.3 | Save and close — reopen — verify attendance is saved | Same marks shown | | |
| 6.4 | Try to take attendance again for the same day | Should warn about duplicate or show existing record | | |
| 6.5 | Go to **Education > Attendance > Attendance Matrix** | Matrix showing student vs date attendance | | |
| 6.6 | Go to **Education > Attendance > Attendance Report** | Report showing attendance % per student | | |
| 6.7 | Verify a student with 100% absence shows correctly in report | Student flagged or shown with 0% | | |
| 6.8 | Take attendance for 5 consecutive days for one classroom | All days recorded, matrix shows all 5 days | | |

---

### TEST BLOCK 7: Examinations

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 7.1 | Go to **Education > Examinations > Exam Sessions** | Session list shown | | |
| 7.2 | Create an exam session for BCA Semester 1, current term | Session created in Draft state | | |
| 7.3 | Click **Generate Papers** | Exam papers created for each subject in the batch | | |
| 7.4 | Open one exam paper — set exam date and full marks | Date and marks saved | | |
| 7.5 | Click **Schedule** on the exam session | Status changes to Scheduled | | |
| 7.6 | Click **Generate Marksheets** | Marksheets created for all enrolled students | | |
| 7.7 | Open a marksheet — click **Enter Marks** | Marks entry form opens with student list | | |
| 7.8 | Enter marks for all students in one paper | Marks saved per student | | |
| 7.9 | Enter marks higher than full marks — confirm validation | Error: marks cannot exceed full marks | | |
| 7.10 | Enter negative marks — confirm validation | Error: marks cannot be negative | | |
| 7.11 | Click **Verify Marks** on the paper | Status changes to Verified | | |
| 7.12 | Go to **Examinations > Print Report Card** for one student | Report card PDF generated with marks | | |
| 7.13 | Try to change marks after verification — should be blocked or require re-verification | Log what happens | | |

---

### TEST BLOCK 8: Continuous Assessment

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 8.1 | Go to **Education > Continuous Assessment** | Assessment list shown | | |
| 8.2 | Create an assessment: type = Assignment, subject, full marks = 20 | Assessment record created | | |
| 8.3 | Enter scores for all students | Scores saved | | |
| 8.4 | Enter a score above full marks — confirm error | Validation error | | |
| 8.5 | Create a second assessment: type = Internal Test, full marks = 30 | Assessment created | | |

---

### TEST BLOCK 9: Results

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 9.1 | Go to **Education > Results > Result Sessions** | Session list shown | | |
| 9.2 | Create a result session for BCA Semester 1 | Session created | | |
| 9.3 | Click **Compute Results** | Results computed, subject results listed per student | | |
| 9.4 | Verify grades are assigned based on marks | Grade shown per subject | | |
| 9.5 | Verify a student with 0 marks across all subjects shows as Fail | Status = Fail | | |
| 9.6 | Click **Verify** results | Status changes to Verified | | |
| 9.7 | Click **Publish** results | Status changes to Published, students can view | | |
| 9.8 | Try to change a mark after results are published — what happens? | Log result | | |
| 9.9 | Go to **Results > Reports > Backlog Report** — verify students with fails are listed | Failed students appear in backlog | | |
| 9.10 | **Recompute** results after changing one mark (requires unpublish first if blocked) | Recomputed result reflects the change | | |

---

## AASHRIYA — Finance + General Navigation (Phase 9 + Smoke Tests)

**Your job:** Test the fee/payment flow and do a general navigation smoke test across all menus.
**Prerequisite:** At least 1 enrolled active student.
**Time estimate:** 1.5 days
**Report bugs to:** Tech lead

---

### TEST BLOCK 10: Student Finance

| # | Step | Expected Result | Pass/Fail | Bug # |
|---|------|----------------|-----------|-------|
| 10.1 | Go to **Education > Student Finance > Fee Dues** | Dues list shown | | |
| 10.2 | Open dues for an enrolled student — verify fee lines match their fee structure | Correct fee amounts shown | | |
| 10.3 | Click **Generate Dues** with a payment schedule | Due dates created (e.g. monthly installments) | | |
| 10.4 | Go to **Student Finance > Payments** — create a payment for one due | Payment recorded, due marked as paid | | |
| 10.5 | Record a payment larger than the due amount — what happens? | Overpayment handled or error shown — log result | | |
| 10.6 | Record a partial payment | Partial payment shown, remaining balance visible | | |
| 10.7 | Click **Create Invoice** from the dues list | Invoice created in Odoo Accounting | | |
| 10.8 | Go to **Student Finance > Deposits** — create a security deposit | Deposit record created | | |
| 10.9 | Process a deposit refund | Refund processed | | |
| 10.10 | View a student with no payments — confirm outstanding dues are visible | Outstanding amount shown clearly | | |

---

### TEST BLOCK 11: General Navigation Smoke Test

For each menu item, just open it and confirm it loads without error. Mark PASS (loads fine) or FAIL (error/blank screen).

| # | Menu Path | Pass/Fail | Error Message (if any) |
|---|-----------|-----------|----------------------|
| 11.1 | Education > Academic > Academic Years | | |
| 11.2 | Education > Academic > Batches | | |
| 11.3 | Education > Pre-Admission > Inquiries & Leads | | |
| 11.4 | Education > Admission > Applications | | |
| 11.5 | Education > Enrollment | | |
| 11.6 | Education > Classrooms | | |
| 11.7 | Education > Attendance > Attendance Matrix | | |
| 11.8 | Education > Attendance > Attendance Report | | |
| 11.9 | Education > Examinations > Exam Sessions | | |
| 11.10 | Education > Examinations > My Exam Papers | | |
| 11.11 | Education > Continuous Assessment | | |
| 11.12 | Education > Results > Result Sessions | | |
| 11.13 | Education > Results > Student Results | | |
| 11.14 | Education > Results > Reports > Backlog Report | | |
| 11.15 | Education > Student Finance > Fee Dues | | |
| 11.16 | Education > Student Finance > Payments | | |
| 11.17 | Education > Student Finance > Deposits | | |
| 11.18 | Education > Configuration (all sub-items) | | |

---

### TEST BLOCK 12: Role-Based Access

Test with a user who has only **Teacher** role (not Admin):

| # | Test | Expected Result | Pass/Fail |
|---|------|----------------|-----------|
| 12.1 | Can teacher see their own classrooms? | Yes | |
| 12.2 | Can teacher see OTHER teachers' classrooms? | No — should be hidden or read-only | |
| 12.3 | Can teacher take attendance for their classroom? | Yes | |
| 12.4 | Can teacher enter exam marks for their papers? | Yes | |
| 12.5 | Can teacher access Admission or Enrollment menus? | No — should not be visible | |
| 12.6 | Can teacher publish results? | No — Publish Manager role required | |

---

## Bug Sheet

Copy and fill this for every bug found:

| Bug ID | Module | Test # | Steps to Reproduce | Actual Result | Expected Result | Severity (High/Med/Low) |
|--------|--------|--------|--------------------|---------------|-----------------|------------------------|
| BUG-001 | | | | | | |
| BUG-002 | | | | | | |

**Severity guide:**
- **High:** Blocks a core flow (can't create student, can't save marks, crash)
- **Medium:** Wrong behavior but can work around it
- **Low:** UI issue, label wrong, minor inconsistency

---

## Final Checklist Before Handing Back to Tech Lead

- [ ] All test blocks completed (or documented as skipped with reason)
- [ ] All bugs logged in the bug sheet above
- [ ] Screenshots attached for all High severity bugs
- [ ] This document filled in and shared with tech lead by Friday EOD
