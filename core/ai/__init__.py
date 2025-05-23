"""
Core AI Module
Contains utilities for AI-based analysis of emails and attachments.
""" 

import logging
logger = logging.getLogger(__name__)

# Apply the attachment analyzer patch on startup
try:
    from .attachment_analyzer_fix import apply_patch
    
    # Try to apply the patch
    patch_success = apply_patch()
    if patch_success:
        logger.info("Successfully applied improved Turkish pattern matching to attachment analyzer")
    else:
        logger.warning("Failed to apply Turkish pattern matching patch to attachment analyzer")
except Exception as e:
    logger.error(f"Error applying attachment analyzer patch: {str(e)}") 