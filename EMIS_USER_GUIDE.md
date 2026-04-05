# EMIS — Education Management Information System
## Comprehensive End-User Guide

**Version:** 19.0 | **Author:** Innovax Solutions | **Last Updated:** April 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Getting Started](#2-getting-started)
3. [Module 1: Academic Structure](#3-academic-structure)
4. [Module 2: Pre-Admission CRM](#4-pre-admission-crm)
5. [Module 3: Fee Structure](#5-fee-structure)
6. [Module 4: Admission](#6-admission)
7. [Module 5: Student Records](#7-student-records)
8. [Module 6: Enrollment](#8-enrollment)
9. [Module 7: Academic Progression](#9-academic-progression)
10. [Module 8: Classrooms](#10-classrooms)
11. [Module 9: Attendance](#11-attendance)
12. [Module 10: Examinations](#12-examinations)
13. [Module 11: Continuous Assessment](#13-continuous-assessment)
14. [Module 12: Results](#14-results)
15. [Module 13: Student Finance](#15-student-finance)
16. [Module 14: Finance Accounting Integration](#16-finance-accounting-integration)
17. [Security & Roles Reference](#17-security--roles-reference)
18. [Complete Workflow: Student Lifecycle](#18-complete-workflow-student-lifecycle)

---

## 1. System Overview

The **Education Management Information System (EMIS)** is a suite of 14 tightly integrated Odoo 19 modules that manage the complete lifecycle of students in a school, college, or university — from their first inquiry through graduation and alumni status.

### What EMIS Covers

| Area | Modules | What It Does |
|------|---------|-------------|
| **Foundation** | Academic Structure | Academic years, programs, batches, sections, subjects, curriculum |
| **Recruitment** | Pre-Admission CRM | Inquiry tracking, applicant profiles, counselor management |
| **Admission** | Admission | Applications, scholarship assessment, offer letters |
| **Onboarding** | Enrollment, Student Records | Enrollment checklists, official student identity creation |
| **Academics** | Academic Progression, Classrooms | Semester promotion, section assignment, teaching hubs |
| **Day-to-Day** | Attendance, Examinations, Assessment | Session attendance, exam papers/marks, continuous assessment |
| **Outcomes** | Results | Configurable result computation, grading, backlog management |
| **Finance** | Fee Structure, Student Finance, Accounting | Fee plans, dues, payments, invoicing, deposits |

### How Data Flows Through EMIS

```
Inquiry (CRM Lead)
    |
    v
Applicant Profile (identity, guardians, academic history)
    |
    v
Admission Application (review, scholarship, offer letter)
    |
    v
Enrollment (academic + financial snapshot, checklist)
    |
    v
Student Record (permanent institutional identity)
    |
    v
Academic Progression (semester placement, section assignment)
    |
    v
Classrooms (subject x section x term teaching hub)
    |
    +---> Attendance (daily session tracking)
    +---> Examinations (papers, marksheets, raw marks)
    +---> Continuous Assessment (assignments, tests, projects)
    |
    v
Results (weighted computation, grading, backlog, promotion)
    |
    v
Finance (fee plans, dues, payments, invoices, deposits)
```

---

## 2. Getting Started

### User Roles at a Glance

EMIS uses role-based access. Each module has its own set of roles, but the common pattern is:

| Role Level | What You Can Do |
|-----------|----------------|
| **Viewer** | Read-only access to records |
| **Officer** | Create and edit records; run day-to-day operations |
| **Teacher** | Access scoped to own classrooms only (attendance, exams, assessment) |
| **Manager** | Publish results, approve scholarships, override fee blocks |
| **Administrator** | Full control including delete, configuration, and overrides |

Your system administrator assigns you the appropriate roles. You will only see menus and buttons relevant to your assigned permissions.

### Navigation Structure

EMIS organizes its menus under the **Education** root menu:

```
Education
├── Academic         (years, terms, batches, sections)
├── Pre-Admission    (inquiries, applicant profiles)
├── Admission        (registers, applications, scholarships)
├── Enrollment       (enrollment records, checklists)
├── Classrooms       (all classrooms, my classrooms)
├── Attendance       (registers, sheets, reports, matrix)
├── Examinations     (sessions, papers, marksheets, report cards)
├── Continuous Assessment (records, categories)
├── Results          (sessions, subject/student results, reports)
├── Student Finance  (fee plans, dues, payments, deposits)
├── Fees             (fee structures, fee heads, fee terms)
├── Configuration    (programs, subjects, curriculum, schemes, policies)
```

---

## 3. Academic Structure

**Menu:** Education > Academic | Education > Configuration

The Academic Structure module is the **foundation** of the entire system. It defines how your institution is organized academically.

### Key Concepts

| Concept | What It Represents | Example |
|---------|-------------------|---------|
| **Academic Year** | One complete academic cycle | 2025-2026 |
| **Term** | A division of the academic year | Semester 1, Semester 2 |
| **Department** | Organizational unit | Computer Science, Business |
| **Program** | A degree or course offering | Bachelor of Computer Science (BCS) |
| **Program Term** | A progression stage within a program | Semester 1, Semester 2, ... Semester 8 |
| **Batch** | An intake cohort of students | BCS - 2025-2026 |
| **Section** | A class division within a batch | Section A, Section B |
| **Subject** | A course that can be taught | Data Structures, Calculus |
| **Curriculum Line** | A subject mapped to a program term | Data Structures in BCS Semester 3 |

### Setting Up an Academic Year

1. Go to **Academic > Academic Years** and click **Create**
2. Enter the year name (e.g., "2025-2026"), code, and start/end dates
3. Select the **Term Structure** (Semester, Trimester, Quarter, or Annual)
4. Click **Generate Terms** to auto-create terms with date splits
5. Review and adjust term dates if needed
6. Click **Set Active** — only one year can be active at a time

### Setting Up a Program

1. Go to **Configuration > Departments** and create your department (if new)
2. Go to **Configuration > Programs** and click **Create**
3. Fill in: name, code, department, type (Undergraduate/Postgraduate/etc.), duration, term system
4. Set **Total Progressions** (e.g., 8 for a 4-year semester program)
5. Click **Generate Progressions** to auto-create program terms (Semester 1 through 8)

### Setting Up Curriculum

1. Go to **Configuration > Subjects** and create all subjects with credit hours and marks
2. Go to **Configuration > Curriculum** (or open a Program Term)
3. For each program term, add subjects with:
   - **Subject Category**: Compulsory, Elective, or Optional
   - **Credit Hours, Full Marks, Pass Marks** (defaults from subject, can override)

### Creating a Batch

1. Go to **Academic > Batches** and click **Create**
2. Select **Program** and **Academic Year**
3. Optionally add an **Intake Name** (e.g., "Fall") to differentiate multiple intakes
4. A default Section "A" is auto-created; add more sections as needed
5. Set section capacities if required
6. Click **Activate** when ready (academic year must be active first)

### Important Rules

- Only **one academic year** can be active per company at a time
- Term dates must fall within their academic year and cannot overlap
- Section capacity must fit within batch capacity
- A subject can only appear once per program term
- Records cannot be deleted if they have dependent data — use archive instead

---

## 4. Pre-Admission CRM

**Menu:** Pre-Admission

This module manages the initial inquiry and prospect pipeline before formal admission begins.

### Key Concepts

| Concept | Purpose |
|---------|---------|
| **CRM Lead** | Tracks an inquiry through the pre-admission pipeline |
| **Applicant Profile** | Structured identity record for the prospective student |
| **Guardian** | Parent, sponsor, or responsible adult linked to an applicant |
| **Academic History** | Past qualifications and educational achievements |

### The Pre-Admission Pipeline

Leads progress through six stages via dedicated buttons (not drag-and-drop):

```
Inquiry --> Prospect --> Qualified --> Ready for Application --> Converted --> Lost
```

### Recording a New Inquiry

1. Go to **Pre-Admission > Inquiries & Leads** and click **Create**
2. Enter: name, phone, email, source (how they heard about you)
3. Status starts as **Inquiry**
4. Assign a **Counselor** for follow-up

### Moving Through the Pipeline

1. **Mark as Prospect** — initial qualification complete
2. **Mark as Qualified** — enter a quick name to auto-create an Applicant Profile, or select an existing one
3. Set the **Interested Program** (required for next step)
4. **Ready for Application** — validates profile and program are set
5. **Convert to Application** — creates a formal admission application (requires `edu_admission` module)

### Building an Applicant Profile

From the Applicant Profile, you can manage:
- **Personal details**: Name, gender, date of birth, nationality
- **Guardians tab**: Add parents/sponsors with relationship type, primary contact flag, financial contact flag
- **Academic History tab**: Add past qualifications with institution, score, and year

### Duplicate Detection

The system automatically flags leads with matching phone numbers or email addresses. Look for the red "Duplicate" badge on kanban cards.

---

## 5. Fee Structure

**Menu:** Education > Fees

This module defines **what fees are charged** and **how they can be collected** — separate from actual student billing.

### Key Concepts

| Concept | Purpose | Example |
|---------|---------|---------|
| **Fee Head** | A reusable fee component type | Tuition Fee, Lab Fee, Admission Fee |
| **Fee Term** | A payment timing label | At Admission, Installment 1 |
| **Fee Structure** | Complete fee plan for a program intake | BCA Fee Structure 2026 Intake |
| **Fee Structure Line** | One fee for one progression stage | Tuition Fee for Semester 1: Rs. 50,000 |
| **Payment Plan** | How fees are collected | Installment Plan, Monthly Plan |

### Creating a Fee Structure

1. Go to **Fees > Fee Structures** and click **Create**
2. Select **Program**, **Academic Year**, and optionally a specific **Batch**
3. Click **Generate Fee Lines** to auto-create one line per program term
4. For each line, set the **Fee Head**, **Amount**, and flags:
   - **Mandatory**: Cannot be waived
   - **Scholarship Allowed**: Can receive discount
   - **Refundable**: Can be returned
5. Add **Payment Plans**:
   - **Installment Plan**: Define which fee heads are due at each installment
   - **Monthly Plan**: Set number of months and excluded fee heads
6. Click **Activate** when complete

### Fee Structure States

| State | What You Can Do |
|-------|----------------|
| **Draft** | Full editing — add/remove lines and plans freely |
| **Active** | Amounts and flags are editable, but you cannot change which fee is assigned to which term |
| **Closed** | Read-only; no changes allowed |

---

## 6. Admission

**Menu:** Admission

The Admission module handles the formal application lifecycle, from submission through scholarship assessment to enrollment handoff.

### Key Concepts

| Concept | Purpose |
|---------|---------|
| **Admission Register** | An admission intake/opening for a specific program and year |
| **Application** | One applicant's formal admission record |
| **Scholarship Scheme** | Master definition of a scholarship type with rules |
| **Scholarship Review** | Per-application scholarship assessment and approval |

### Opening Admission for a Program

1. Go to **Admission > Admission Registers** and click **Create**
2. Select **Program** and **Academic Year**
3. Set application start/end dates and seat limit
4. System auto-resolves the **Fee Structure** from the matching fee structure record
5. Confirm available **Payment Plans** and set the default
6. Click **Open** to accept applications

### Processing an Application

The application flows through these states:

```
Draft --> Submitted --> Under Review --> Scholarship Review --> Offered
    --> Offer Accepted --> Ready for Enrollment --> Enrolled
```

**Step-by-step:**

1. **Create application** — select applicant profile and program
2. **Submit** — validates required fields
3. **Start Review** — conduct academic assessment
4. **Mark Review Complete** — academic review done
5. **Start Scholarship Review** — if applicable
6. **Assess scholarships** — create review lines, check eligibility, recommend awards
7. **Approve scholarships** — approver finalizes each scholarship
8. **Generate Offer** — creates PDF offer letter with fee breakdown
9. **Accept Offer** — freezes fees and scholarships permanently
10. **Mark Ready for Enrollment** — validates all prerequisites
11. **Create Enrollment** — generates the enrollment record

### Scholarship System

EMIS supports sophisticated scholarship management:

- **Award Types**: Percentage, fixed amount, full waiver, or custom
- **Stacking**: Multiple scholarships can stack (combine) unless marked exclusive
- **Stacking Groups**: Only one scholarship per group (e.g., only one Merit award)
- **Per-Line Caps**: Maximum discount percent or amount per scholarship
- **Global Cap**: Total discount never exceeds the scholarship-eligible total
- **Eligibility Hints**: Merit scores, family income, sibling count, sports level, etc.
- **Scheme Snapshots**: Approved values are frozen at offer acceptance for audit

### Offer Letter

The system generates a PDF offer letter showing:
- Application details and program information
- Base fee breakdown by fee type
- Scholarship discount (if any)
- Net fee payable
- Selected payment plan
- Offer expiry date

---

## 7. Student Records

**Menu:** Admission > Students

The Student module creates and manages the permanent institutional student identity.

### How Students Are Created

Students are **always created from an active enrollment** — never manually:

1. Navigate to an active enrollment record
2. Click the **Create Student** button
3. System auto-generates:
   - **Student Number**: STU/2026/00001 (globally unique)
   - **Roll Number**: 2026-BCA-0001 (unique per batch)

### Student Lifecycle

```
Active --> On Leave --> (back to Active)
Active --> Suspended --> (back to Active or Withdrawn)
Active --> Graduated --> Alumni --> Inactive
Active --> Withdrawn --> Inactive
```

Each transition:
- Stamps the relevant date (graduation_date, withdrawal_date, etc.)
- Creates an audit record in **Status History**
- Is recorded with the user who made the change

### Identity Protection

Once set, the following fields **cannot be changed**:
- Student Number, Roll Number
- Partner (contact record), Applicant Profile
- Source Enrollment

Academic placement (program, batch, section, term) can be updated while the student is in **Active** state.

### Smart Buttons

From the student form, quickly navigate to:
- **Applicant** — full applicant profile
- **Guardians** — linked guardians
- **Enrollment** — source enrollment record
- **Progressions** — academic progression history
- **Attendance** — all attendance records
- **Exam Marksheets** — all exam results
- **Assessments** — continuous assessment records
- **Fee Plans / Dues / Payments** — financial records
- **Deposit Ledger** — security deposit balance

---

## 8. Enrollment

**Menu:** Admission > Enrollment

Enrollment is the bridge between admission and the student lifecycle. It creates a permanent institutional record that snapshots academic and financial context.

### Enrollment Workflow

```
Draft --> Confirmed --> Active --> Completed
           (or Cancelled at any point except Completed)
```

1. **Draft**: Created from admission application; all fields editable
2. **Confirmed**: Validates required fields and fee confirmation; locks academic/financial fields
3. **Active**: Checklist complete; student can be created from this enrollment
4. **Completed**: Historical record; fully read-only

### Enrollment Checklist

Each enrollment has a checklist of requirements that must be completed before activation:

1. Open the **Checklist** tab on the enrollment form
2. Add requirements (e.g., "Submit vaccination certificate", "Complete orientation")
3. Mark each item as **Complete** — records who completed it and when
4. Once all **required** items are checked, the enrollment can be activated

### Key Features

- **Snapshot Preservation**: Academic placement and financial context are frozen at enrollment time and cannot change retroactively
- **Duplicate Protection**: Only one enrollment per application; one enrollment per applicant per batch/year
- **Readiness Validation**: System shows blocking reasons if prerequisites are missing
- **Audit Trail**: Records who confirmed, who activated, and when

---

## 9. Academic Progression

**Menu:** Academic > Progression

This module tracks each student's journey through their program, semester by semester.

### Key Concepts

| Concept | Purpose |
|---------|---------|
| **Progression History** | One record per student per term — the academic anchor for all operations |
| **Batch Promotion** | Advances all students in a batch to the next semester |
| **Section Assignment** | Bulk-assign students to classroom sections |

### How Progression Records Are Created

When a student is created from an enrollment, an **initial progression history** record is automatically created in **Active** state, linked to their current batch, program term, and section.

### Batch Promotion

When a semester ends and students need to advance:

1. Open the **Batch** record
2. Click **Promote Batch** button
3. Set the **Effective Date** and **Academic Year** for the new term
4. Choose **Section Mode**:
   - **Keep Current Section** — students stay in their sections
   - **Clear Section** — sections cleared for reassignment
5. Click **Promote**

The system:
- Closes all current progression records (state = "promoted")
- Creates new active progression records at the next term
- Links old and new records via promotion chain
- Updates the batch's current program term

### Bulk Section Assignment

To assign or reassign students to sections:

1. Open the **Batch** record and click **Assign Sections**
2. Select the target **Sections** and **Assignment Method**:
   - **Alphabetical**: Sort by name, distribute evenly
   - **Roll Number**: Sort by roll number, distribute evenly
   - **Round Robin**: Cycle through sections A-B-C-A-B-C
   - **Manual**: Generate lines for manual assignment
3. Toggle **Respect Section Capacity** if needed
4. Click **Generate Preview** to review assignments
5. Edit any assignments manually in the preview
6. Click **Confirm Assignment** to apply

### Elective Subjects

Students can select elective or optional subjects for their current term:
- Open the student's active progression record
- In the **Elected Curriculum Lines** field, select elective subjects
- The **Effective Curriculum** automatically combines compulsory + elected subjects

---

## 10. Classrooms

**Menu:** Classrooms

A classroom is the central operational hub where a teacher, a section of students, and a subject come together for a specific term.

### What Is a Classroom?

Each classroom record represents one unique combination of:
- **Batch** + **Section** + **Subject** (Curriculum Line) + **Program Term**

For example: "BCS-2025 / Section A / Data Structures / Semester 3"

### Creating Classrooms

**Bulk Generation (Recommended):**
1. Open the **Batch** record (must be Active with a current program term)
2. Click **Generate Classrooms**
3. System creates one classroom per subject for each section
4. Assign teachers to each classroom

**Manual Creation:**
1. Go to **Classrooms > All Classrooms** and click **Create**
2. Select Batch, Section, Program Term, and Curriculum Line

### Classroom Lifecycle

```
Draft --> Active --> Closed
```

- **Draft**: Setup phase — identity fields are editable
- **Active**: Operational — identity fields locked; attendance register auto-created; teachers can work
- **Closed**: End of term — all operations complete

### For Teachers

Teachers see only their assigned classrooms:
1. Go to **Classrooms > My Classrooms**
2. Click a classroom to open it
3. Use smart buttons:
   - **Students** — view the class roster
   - **Sessions** — manage attendance
   - **Take Attendance Today** — one-click attendance recording
   - **Marks Entry** — enter exam marks (when papers are in marks entry state)

---

## 11. Attendance

**Menu:** Attendance

The attendance module provides session-based student attendance tracking with automated student population, matrix reports, and Excel export.

### How Attendance Works

```
Classroom Activation
    |
    v
Attendance Register (auto-created, one per classroom)
    |
    v
Attendance Sheets (one per session/day)
    |
    v
Attendance Lines (one per student per session)
```

### Taking Attendance (Teacher Workflow)

**Quick Method (Recommended):**
1. Open your classroom from **Classrooms > My Classrooms**
2. Click **Take Attendance Today**
3. All students are auto-populated as "Present"
4. Change status for absentees: **Absent**, **Late**, or **Excused**
5. Click **Submit** to finalize

**Manual Method:**
1. Go to **Attendance > My Sheets** and click **Create**
2. Select the register, date, and time
3. Click **Start Session** to generate student lines
4. Mark attendance statuses
5. Click **Submit**

### Attendance Statuses

| Status | Meaning | Counts as Attended? |
|--------|---------|-------------------|
| **Present** | Student attended | Yes |
| **Late** | Student attended but was late | Yes |
| **Absent** | Student did not attend | No |
| **Excused** | Absence excused | Depends on policy |

### Viewing Reports

**Attendance Report** (Pivot/Graph):
- Go to **Attendance > Attendance Report**
- View pivot tables or bar charts showing attendance patterns
- Identify students below the threshold (default: 75%)

**Attendance Matrix**:
- Go to **Attendance > Attendance Matrix**
- Set date range and filters (classroom, batch, section)
- Click **Generate Report** to see a date-by-student grid
- Color-coded cells: Green (P), Red (A), Yellow (L), Blue (E)
- Click **Download Excel** to export a formatted spreadsheet

### Submitted Sheets Are Locked

Once an attendance sheet is submitted:
- All data is locked and cannot be edited
- Only an **Attendance Administrator** can reset it to draft for corrections

---

## 12. Examinations

**Menu:** Examinations

The examination module manages the complete exam lifecycle from session creation through marks entry, publication, and report card printing.

### Key Concepts

| Concept | Purpose |
|---------|---------|
| **Exam Session** | A collection of exam papers for a specific scope (batch, program, etc.) |
| **Exam Paper** | One subject's exam within a session |
| **Paper Component** | Sub-parts of a paper (Theory, Practical, Viva) |
| **Marksheet** | One student's marks for one paper |
| **Assessment Scheme** | Defines how exam components contribute to results |
| **Back Exam Policy** | Rules for retake attempts |

### Exam Session Workflow

```
Draft --> Planned --> Ongoing --> Marks Entry --> Published --> Closed
```

### Conducting an Exam (Officer Workflow)

1. **Create Exam Session**
   - Go to **Examinations > Exam Sessions** and click **Create**
   - Set: scope (batch/program), exam type (internal/terminal/final), dates
   - Optionally attach an **Assessment Scheme**

2. **Generate Exam Papers**
   - Click **Generate Exam Papers** button
   - Choose scope: **From Classrooms** (uses active classrooms) or **From Curriculum** (uses program term subjects)
   - Review the preview, deselect unwanted papers
   - Click **Generate**

3. **Schedule Papers**
   - For each paper, set exam date, time, room
   - Add components (Theory/Practical splits) if needed
   - Transition session to **Planned**, then **Ongoing**

4. **Generate Marksheets**
   - Click **Generate Marksheets** button
   - Select papers and attempt type (Regular for first attempt)
   - Toggle **Snapshot Attendance** to capture attendance percentage
   - Click **Generate**

5. **Enter Marks**
   - Teachers go to **My Exam Papers**, find their paper, click **Enter Marks**
   - Enter raw marks and set status (Present/Absent/Exempt/Withheld/Malpractice)
   - Click **Verify** to timestamp the entry
   - Click **Lock** to prevent accidental changes

6. **Publish Results**
   - **Publish Manager** or **Admin** clicks **Publish** on each paper
   - Then **Publish** on the session

### Report Cards

1. Go to **Examinations > Print Report Card**
2. Select the exam session
3. Optionally select specific students
4. Toggle **Show Component Breakdown** for detailed theory/practical marks
5. Click **Print** to generate PDF report cards showing:
   - Per-subject marks, status, and pass/fail
   - Total marks, percentage, and overall status

### Back Exams

For students who failed:

1. Go to **Examinations > Back Exams**
2. Click **Generate Back Exam** button
3. Select failed candidates from the result session
4. Choose attempt type (Back/Makeup/Improvement/Special)
5. System creates papers and marksheets with attempt tracking
6. Conduct the back exam following the same workflow

### Marks Entry from Classroom

Teachers can also enter marks directly from their classroom:
1. Open the classroom from **My Classrooms**
2. Click the **Marks Entry** smart button
3. Opens a dedicated editable list view for bulk marks entry

---

## 13. Continuous Assessment

**Menu:** Continuous Assessment

This module captures ongoing, non-exam academic evaluations — assignments, class tests, projects, practicals, participation, and more.

### Assessment Categories

Pre-configured categories include:

| Category | Default Max Marks | Contributes to Result? |
|----------|------------------|----------------------|
| Assignment | 100 | Yes |
| Class Test | 25 | Yes |
| Project | 100 | Yes |
| Practical / Continuous | 50 | Yes |
| Class Performance | 20 | Yes |
| Participation | 10 | Yes |
| Attendance Score | 10 | Yes |
| Observation | 10 | No |
| Manual / Internal | 100 | Yes |

### Recording Assessments (Teacher Workflow)

**Individual Entry:**
1. Go to **Continuous Assessment > My Assessments** and click **Create**
2. Select: Category, Student, Classroom
3. Enter: Assessment Title, Date, Max Marks, Marks Obtained
4. Percentage auto-computes
5. Click **Confirm** when ready

**Bulk Generation:**
1. Use the **Bulk Generate** wizard
2. Select a Classroom and Category
3. Enter Title, Date, and Max Marks
4. Click **Generate** — creates one draft record per active student
5. Enter marks inline in the list view

### Assessment States

| State | Who Can Change | What's Locked |
|-------|---------------|---------------|
| **Draft** | Teacher | Nothing — full editing |
| **Confirmed** | Teacher confirms | Minor protection |
| **Locked** | Officer/Admin locks | All assessment data; only Remarks remain editable |

To correct a locked record, an **Admin** must click **Reset to Draft**.

### Bulk Confirm / Lock

1. Select multiple records in list view
2. Click the **Action** menu
3. Choose **Confirm Selected** or **Lock Selected**

### Attendance Score Integration

For the "Attendance Score" category, a **Snapshot Attendance** button fetches the student's attendance percentage from the attendance module and auto-fills marks proportionally.

---

## 14. Results

**Menu:** Results

The Result module is the culmination of exam and assessment data — it computes final grades, determines pass/fail, manages backlogs, and produces official result documents.

### Configuration (Admin Setup)

**Assessment Scheme** — defines how marks from different sources are weighted:
- Each "line" represents a component (e.g., Terminal Exam 40%, Internal 30%, Assignment 20%, Attendance 10%)
- Source types include: exam sessions, assignments, attendance, projects, practicals
- Aggregation methods: total, average, best-of, latest, weighted average
- Weightages must sum to 100%

**Grading Scheme** — maps percentages to grades:
- Grade bands with min/max percentages
- Grade letters (A+, A, B+, B, C, D, F)
- Grade points (4.0, 3.7, 3.3, etc.)
- Result remarks (Distinction, First Division, Pass, Fail)

**Result Rule** — defines pass/fail logic:
- Minimum overall percentage (e.g., 40%)
- Mandatory component rules
- Backlog allowance and limits
- Attendance shortage action (ignore/warn/withhold/fail)
- Malpractice handling

**Back Exam Policy** — governs retake behavior:
- Maximum attempts per subject
- Which marks to carry forward (internal, practical, attendance)
- Result replacement method (latest, highest, average)
- Grade cap after back exam

### Computing Results (Officer Workflow)

1. Go to **Results > Result Sessions** and click **Create**
2. Select: Academic Year, Program, Batch, Program Term
3. Link: Assessment Scheme, Grading Scheme, Result Rule
4. Click **Compute Results** wizard
5. System processes all students:
   - Aggregates marks from exams, assessments per scheme lines
   - Normalizes and applies weightages
   - Calculates final percentage/GPA
   - Determines pass/fail per component and subject
   - Flags backlogs
6. Review results in **Subject Results** and **Student Results** tabs

### Result Session Workflow

```
Draft --> Processing --> Verified --> Published --> Closed
```

- **Processing**: Computation running
- **Verified**: Quality-checked by a reviewer
- **Published**: Visible to students/parents (Publish Manager only)
- **Closed**: No further modifications

### After Back Exams

1. Open the original result session
2. Click **Recompute After Back Exam** wizard
3. Select the published back exam session
4. Select the back exam policy
5. System:
   - Keeps carried-forward marks (per policy)
   - Takes new marks from back exam
   - Recomputes percentage/GPA
   - Creates new subject line (old one marked as superseded)
   - Updates student result status

### Available Reports

| Report | Shows | Use Case |
|--------|-------|----------|
| **Result Sheet** | One student's complete subject-wise results | Official transcript |
| **Subject Tabulation** | All students' results for each subject | Teacher/coordinator review |
| **Student Result Summary** | All students' overall results | Administration dashboard |
| **Backlog Report** | Failed subjects with attempt tracking | Remedial planning |
| **Back Exam Eligibility** | Students eligible for back exams | Registration/notification |

---

## 15. Student Finance

**Menu:** Student Finance

The Student Finance module manages student billing — from fee plan generation through payment tracking.

### Key Concepts

| Concept | Purpose |
|---------|---------|
| **Student Fee Plan** | Per-enrollment fee plan generated from fee structure |
| **Fee Plan Line** | Individual fee charge for a specific term |
| **Fee Due** | A payable obligation with due date |
| **Student Payment** | A payment received from or on behalf of a student |
| **Schedule Template** | Defines how fees are split into installments |

### How Fee Plans Are Created

Fee plans are **auto-generated** when an enrollment is created:
1. System reads the fee structure linked to the enrollment
2. Creates fee plan lines for each term's fees
3. Distributes scholarship discounts proportionally across eligible lines
4. Generates enrollment-required dues automatically

### Fee Due States

```
Draft --> Due --> Partial --> Paid
                    |
                    v
                 Overdue (if past due date)
```

### Recording Payments

1. Go to **Student Finance > Payments** and click **Create**
2. Select **Enrollment** and enter: amount, payment method, reference
3. Add allocation lines to link payment to specific dues, or click **Auto-Allocate** (oldest dues first)
4. Click **Post** to finalize
5. Due states update automatically (Partial, Paid)

### Enrollment Fee Blocking

Certain fee heads can be marked as **Required for Enrollment**. If the student has unpaid required dues:
- Enrollment confirmation is **blocked**
- A manager with override permission can enter a reason and bypass the block
- The override is fully audited (who, when, why)

### Finance Dashboard

**On the Student form**, a Finance tab shows:
- Total planned fees, discounts, dues, payments, and outstanding balance
- Smart buttons for Fee Plans, Dues, and Payments

---

## 16. Finance Accounting Integration

**Menu:** Student Finance > Accounting, Student Finance > Deposits

This module bridges EMIS with Odoo Accounting for proper financial management.

### Invoice Generation

1. Go to **Student Finance > Fee Dues**
2. Select one or more outstanding dues
3. Click **Create Invoice**
4. System creates invoices grouped by enrollment, with proper accounts and taxes
5. Review and **Post** the invoice in Accounting

### Payment Reconciliation

When an EMIS payment is posted:
1. System creates an accounting payment entry
2. Automatically reconciles with related invoices
3. Due states sync daily via a scheduled job

### Credit Notes

For corrections after invoicing:
1. Select an invoiced due
2. Click **Create Credit Note**
3. Review and post the credit note

### Security Deposits

**Deposit Ledger** — one per student, tracking:
- **Collected**: Total deposits paid
- **Adjusted**: Deductions (damage, forfeiture)
- **Refunded**: Amounts returned
- **Balance**: Available deposit

**Deposit Adjustments** (deductions):
```
Draft --> Submitted --> Approved (creates journal entry)
```

**Deposit Refunds** (returns to student):
```
Draft --> Submitted --> Approved --> Done (creates outbound payment)
```

Both adjustments and refunds require **Deposit Approver** authorization.

### Financial Reports

Available as pivot/graph views:
- **Fee Collection**: Dues by fee type and term
- **Outstanding Dues**: Unpaid balances by enrollment
- **Fee Plan Summary**: Planned fees by program and batch
- **Payment Analysis**: Payment volume by method and month
- **Deposit Summary**: Deposit balances by student

---

## 17. Security & Roles Reference

### Role Summary by Module

| Module | Viewer | Teacher/Officer | Manager/Admin |
|--------|--------|----------------|---------------|
| **Academic Structure** | View all records | Create/edit records | Full CRUD + config |
| **Pre-Admission** | View leads & profiles | Manage pipeline & profiles | Full CRUD |
| **Admission** | View applications | Process applications | Full CRUD + config |
| **Enrollment** | View enrollments | Confirm/activate enrollments | Full CRUD + admin cancel |
| **Student** | View students | Create/edit students | Suspend/withdraw/delete |
| **Progression** | View history | Create/edit records | Promote batches, full CRUD |
| **Classroom** | View all classrooms | Create/manage classrooms | Full CRUD |
| **Attendance** | View reports | Take attendance (own classes) | Full CRUD + reset sheets |
| **Examinations** | View results | Create/manage exams | Publish results, full CRUD |
| **Assessment** | View assessments | Create/confirm (own classes) | Lock/unlock, full CRUD |
| **Results** | View published results | Compute results | Publish/close, full CRUD |
| **Finance** | View fee data | Manage plans/dues/payments | Full CRUD + override |

### Special Roles

| Role | Purpose |
|------|---------|
| **Scholarship Reviewer** | Assess eligibility and recommend awards |
| **Scholarship Approver** | Approve/reject scholarship applications |
| **Exam Publish Manager** | Publish exam results (restricted action) |
| **Result Publish Manager** | Publish computed results |
| **Enrollment Fee Override** | Bypass enrollment fee payment block |
| **Deposit Approver** | Approve deposit adjustments and refunds |
| **Cashier** | Process refund payments and manage deposit ledgers |
| **Batch Promotion Manager** | Run batch promotion wizard |
| **Section Assignment Officer/Admin** | Bulk-assign students to sections |

---

## 18. Complete Workflow: Student Lifecycle

Here is the end-to-end journey of a student through EMIS:

### Phase 1: Setup (Admin, once per intake)
1. Create/activate **Academic Year** with terms
2. Create **Programs** with progression stages and curriculum
3. Create **Batches** with sections
4. Create **Fee Structures** with fee lines and payment plans
5. Configure **Assessment Schemes**, **Grading Schemes**, and **Result Rules**

### Phase 2: Recruitment (Pre-Admission Officer)
1. Log inquiry as **CRM Lead**
2. Move through pipeline: Inquiry > Prospect > Qualified
3. Create **Applicant Profile** with guardians and academic history
4. Mark **Ready for Application** when qualified

### Phase 3: Admission (Admission Officer)
1. Open **Admission Register** for the program
2. **Convert** lead to admission application (or create directly)
3. **Submit** and **Review** the application
4. Conduct **Scholarship Review** (if applicable)
5. **Generate Offer Letter** and send to applicant
6. **Accept Offer** (freezes fees and scholarships)
7. **Mark Ready for Enrollment**

### Phase 4: Enrollment (Enrollment Officer)
1. **Create Enrollment** from the accepted application
2. **Confirm** enrollment (validates all prerequisites)
3. Complete the **Enrollment Checklist** (document verification)
4. **Activate** enrollment
5. **Create Student** from the active enrollment

### Phase 5: Academic Operations (Teachers & Officers)
1. **Promote batch** to next semester (creates new progression records)
2. **Assign sections** using the bulk assignment wizard
3. **Generate classrooms** for the batch
4. **Activate classrooms** and assign teachers

### Phase 6: Day-to-Day Teaching (Teachers)
1. **Take attendance** daily via classroom quick-action
2. **Record assessments** (assignments, tests, projects) throughout the term
3. **Enter exam marks** when exam papers are in marks entry state

### Phase 7: Examinations (Exam Officer)
1. **Create exam session** for the term
2. **Generate papers** and **schedule** them
3. **Generate marksheets** for all students
4. Have teachers **enter and verify marks**
5. **Publish** results (Publish Manager)
6. **Print report cards** for students

### Phase 8: Results (Result Officer)
1. **Create result session** with assessment scheme
2. **Compute results** (aggregates exams + assessments + attendance)
3. **Verify** and **Publish** results
4. Manage **backlogs** and conduct **back exams** as needed
5. **Recompute** results after back exams

### Phase 9: Finance (Finance Officer)
1. Fee plans are **auto-generated** at enrollment
2. **Generate dues** with payment schedules
3. **Record payments** and allocate to dues
4. **Create invoices** for accounting
5. Track **deposits**, process **adjustments** and **refunds**

### Phase 10: Completion
1. **Graduate** the student (Student Officer)
2. Mark as **Alumni** (optional)
3. **Close** the batch when all students have completed

---

## Quick Reference: Common Tasks

| I need to... | Where to go |
|-------------|------------|
| Set up a new academic year | Academic > Academic Years |
| Create a new batch of students | Academic > Batches |
| Log a new student inquiry | Pre-Admission > Inquiries & Leads |
| Process an admission application | Admission > Applications |
| Generate an offer letter | Application form > Generate Offer |
| Create a student from enrollment | Enrollment form > Create Student |
| Promote students to next semester | Batch form > Promote Batch |
| Assign students to sections | Batch form > Assign Sections |
| Create classrooms for a batch | Batch form > Generate Classrooms |
| Take daily attendance | Classroom form > Take Attendance Today |
| Create an exam session | Examinations > Exam Sessions |
| Enter exam marks | Examinations > My Exam Papers > Enter Marks |
| Print student report cards | Examinations > Print Report Card |
| Record an assignment score | Continuous Assessment > My Assessments |
| Compute term results | Results > Result Sessions > Compute |
| View a student's result | Results > Student Results |
| Check outstanding fee dues | Student Finance > Fee Dues |
| Record a student payment | Student Finance > Payments |
| Create an invoice from dues | Fee Dues list > Select dues > Create Invoice |
| Process a deposit refund | Student Finance > Deposits > Refunds |
| View attendance matrix/report | Attendance > Attendance Matrix |
| Find students below attendance threshold | Attendance > Attendance Report |
| Check backlog subjects | Results > Reports > Backlog Report |

---

*This guide covers the EMIS v19.0 module suite. For technical documentation, refer to CLAUDE.md. For testing procedures, refer to TESTING_PLAN.md.*
