import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating enrollment states...")
    cr.execute("UPDATE edu_enrollment SET state = 'active' WHERE state = 'confirmed';")
    _logger.info("Enrollment state migration complete.")
