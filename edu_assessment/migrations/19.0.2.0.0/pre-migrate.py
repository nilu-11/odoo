import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return
    _logger.info("Migrating assessment states...")
    cr.execute("UPDATE edu_continuous_assessment_record SET state = 'confirmed' WHERE state = 'locked';")
    _logger.info("Assessment state migration complete.")
