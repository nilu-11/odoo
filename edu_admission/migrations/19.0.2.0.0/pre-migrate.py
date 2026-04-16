import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating admission application states...")

    # Map old states to new
    cr.execute("""
        UPDATE edu_admission_application SET state = 'under_review'
        WHERE state IN ('submitted', 'scholarship_review');
    """)
    cr.execute("""
        UPDATE edu_admission_application SET state = 'approved'
        WHERE state IN ('offered', 'offer_accepted', 'ready_for_enrollment');
    """)
    cr.execute("""
        UPDATE edu_admission_application SET state = 'rejected'
        WHERE state IN ('offer_rejected', 'cancelled');
    """)

    # Add new columns with defaults
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS flow_preset VARCHAR DEFAULT 'standard';
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_academic_review BOOLEAN DEFAULT TRUE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_scholarship_review BOOLEAN DEFAULT FALSE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_offer_letter BOOLEAN DEFAULT TRUE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_odoo_sign BOOLEAN DEFAULT FALSE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_register
        ADD COLUMN IF NOT EXISTS require_payment_confirmation BOOLEAN DEFAULT TRUE;
    """)
    cr.execute("""
        ALTER TABLE edu_admission_application
        ADD COLUMN IF NOT EXISTS payment_received BOOLEAN DEFAULT FALSE;
    """)

    _logger.info("Admission state migration complete.")
