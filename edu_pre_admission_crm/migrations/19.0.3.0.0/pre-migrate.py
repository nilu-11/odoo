"""
Pre-migration: counselor_id changes from res.users to hr.employee.

Drop the old foreign key and clear stale user IDs so the ORM can
re-create the FK pointing to hr_employee.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Pre-migration 19.0.3.0.0: converting counselor_id from res.users to hr.employee")

    # Drop old FK constraint on crm_lead.counselor_id (points to res_users)
    cr.execute("""
        ALTER TABLE crm_lead
        DROP CONSTRAINT IF EXISTS crm_lead_counselor_id_fkey;
    """)

    # Remap existing user IDs to their hr.employee IDs where possible
    cr.execute("""
        UPDATE crm_lead cl
        SET counselor_id = he.id
        FROM hr_employee he
        WHERE he.user_id = cl.counselor_id
          AND cl.counselor_id IS NOT NULL;
    """)

    # Clear any remaining values that couldn't be mapped
    cr.execute("""
        UPDATE crm_lead
        SET counselor_id = NULL
        WHERE counselor_id IS NOT NULL
          AND counselor_id NOT IN (SELECT id FROM hr_employee);
    """)

    # Same for edu_interaction_log if it exists
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'edu_interaction_log'
        );
    """)
    if cr.fetchone()[0]:
        cr.execute("""
            ALTER TABLE edu_interaction_log
            DROP CONSTRAINT IF EXISTS edu_interaction_log_counselor_id_fkey;
        """)
        cr.execute("""
            UPDATE edu_interaction_log il
            SET counselor_id = he.id
            FROM hr_employee he
            WHERE he.user_id = il.counselor_id
              AND il.counselor_id IS NOT NULL;
        """)
        cr.execute("""
            UPDATE edu_interaction_log
            SET counselor_id = NULL
            WHERE counselor_id IS NOT NULL
              AND counselor_id NOT IN (SELECT id FROM hr_employee);
        """)

    _logger.info("Pre-migration 19.0.3.0.0: counselor_id conversion complete")
