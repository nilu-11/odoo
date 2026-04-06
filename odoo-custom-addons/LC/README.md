# Letter of Credit (LC) Management - Odoo 19

This module provides a complete Letter of Credit workflow for Odoo 19 with:

- LC lifecycle management (Draft -> Issued -> Approved -> Closed/Cancelled)
- LC configuration through LC Types
- Required document templates per LC Type
- Submitted document tracking per LC
- Chatter integration and activity scheduling
- Menu entries in both a standalone LC app and Invoicing/Finance

## Module Technical Name

`LC`

## Dependencies

- `base`
- `mail`
- `account`

## Data Loaded

- Security access: `security/ir.model.access.csv`
- Sequence: `data/letter_of_credit_sequence.xml`
- Views: `views/letter_of_credit_views.xml`
- Menus/actions: `views/menu.xml`

## Business Models

### 1) Letter of Credit
Model: `letter.of.credit`

Main fields:

- `name`: LC Number (auto-generated from sequence `letter.of.credit`)
- `state`: `draft`, `issued`, `approved`, `closed`, `cancelled`
- `type_id`: LC Type
- `applicant_id`, `beneficiary_id`: commercial parties
- `bank_id`, `advising_bank_id`, `confirming_bank_id`
- `amount`, `currency_id`
- `issue_date`, `expiry_date`, `latest_shipment_date`
- `payment_term_id`, `incoterm_id`
- `port_of_loading`, `port_of_discharge`
- `document_ids`: submitted LC documents
- `mandatory_document_count`, `received_document_count`, `is_expired`
- `notes`: terms and conditions

Key behavior:

- On create, if name is `New`, sequence is assigned.
- On create, if LC Type is set and no documents are provided, required document lines are generated from the selected LC Type.
- Inherits `mail.thread` and `mail.activity.mixin`.
- Tracking enabled for important fields such as state and amount.

### 2) LC Type
Model: `letter.of.credit.type`

Purpose:

- Define reusable LC templates (Sight, Usance, Revolving, etc.).
- Maintain required document templates via one2many lines.

Main fields:

- `name`, `code`, `description`, `active`
- `required_document_ids`

Constraint:

- Unique `code`

### 3) LC Type Required Document
Model: `letter.of.credit.type.document`

Fields:

- `type_id`
- `name`
- `mandatory`
- `sequence`

### 4) LC Document (Submitted/Tracked)
Model: `letter.of.credit.document`

Fields:

- `lc_id`
- `name`
- `mandatory`
- `status`: `pending`, `received`, `accepted`, `discrepant`
- `received_date`
- `file` (binary attachment) and `file_name`
- `note`

## Workflow

### State Flow

- Draft -> Issue -> Issued
- Issued -> Approve -> Approved
- Approved -> Close -> Closed
- Draft/Issued/Approved -> Cancel -> Cancelled

Validation checks:

- Amount must be greater than 0.
- Expiry date must be after issue date.
- Applicant and Beneficiary must be different.
- Approve action requires all mandatory documents to be received/accepted.

## Menus and Navigation

### Standalone LC App (Dashboard Tile)

- Letter of Credit
  - Operations
    - Letters of Credit
    - Documents
  - Configuration
    - LC Types

### Finance Integration

- Invoicing/Finance
  - Letter of Credit
    - Letters of Credit

## Views Included

### LC Views

- List
- Form (header actions + statusbar + notebook + documents one2many)
- Search

### LC Type Views

- List
- Form (required document templates)
- Search

### LC Document Views

- List
- Form
- Search

## Security

Internal users (`base.group_user`) are granted CRUD access to:

- `letter.of.credit`
- `letter.of.credit.type`
- `letter.of.credit.type.document`
- `letter.of.credit.document`

## Recommended Usage Flow

1. Go to **Letter of Credit > Configuration > LC Types** and create one or more LC Types.
2. Add required document templates for each type.
3. Go to **Letter of Credit > Operations > Letters of Credit** and create an LC.
4. Select the LC Type; required documents are auto-generated.
5. Update document statuses and upload files as they are received.
6. Use action buttons in order: Issue -> Approve -> Close.
7. If needed, cancel before closure.

## Upgrade Instructions

After code changes, upgrade the module:

```bash
./odoo-bin -c odoo.conf -u LC -d <your_database>
```

Then refresh the web client.
