{
    'name': 'Education: Finance Accounting Integration',
    'version': '19.0.1.0.0',
    'summary': (
        'Odoo Accounting integration for student finance — Stage 2. '
        'Invoice generation, accounting payments, deposit handling, '
        'credit notes, and finance reporting.'
    ),
    'description': """
Education Finance Accounting — Stage 2
========================================

Extends the Stage 1 student finance module with full Odoo Accounting
integration:

* Fee‑head ↔ product / account mapping
* Invoice generation from student dues (``account.move``)
* Accounting‑backed payment posting (``account.payment``)
* Automatic reconciliation of payments with invoices
* Security‑deposit liability tracking, adjustment, and refund
* Credit‑note creation for corrections and post‑invoice waivers
* Overdue / state synchronisation between EMIS and Accounting
* Finance reporting foundations (pivot, graph)
* Deposit‑approver and cashier security groups

Backward‑compatible — existing fee heads, structures, dues, and
payments continue to operate.  New accounting fields are optional
until configured.
""",
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'edu_fees',
        'edu_fees_structure',
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/cron_data.xml',
        'views/edu_fee_head_views.xml',
        'views/edu_student_fee_due_views.xml',
        'views/edu_student_payment_views.xml',
        'views/edu_student_views.xml',
        'views/account_move_views.xml',
        'views/edu_deposit_ledger_views.xml',
        'views/edu_deposit_adjustment_views.xml',
        'views/edu_deposit_refund_views.xml',
        'views/edu_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
