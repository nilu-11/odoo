import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating CRM lead education statuses...")
    cr.execute("""
        UPDATE crm_lead SET lead_education_status = 'qualified'
        WHERE lead_education_status IN ('prospect', 'ready_for_application');
    """)
    _logger.info("CRM lead status migration complete.")
