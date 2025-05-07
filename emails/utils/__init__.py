# Utility modules for emails app
from emails.utils.ai_analyzer import ClaudeAnalyzer, body_mentions_attachment

def check_for_attachment_references(text):
    """
    Utility function to check if email body mentions attachments.
    Delegates to the implementation in ai_analyzer.
    """
    return body_mentions_attachment(text)

# Function to extract text from attachments
def extract_text_from_attachment(attachment):
    """
    Extract text from email attachments.
    
    Args:
        attachment: EmailAttachment instance
        
    Returns:
        str: Extracted text or empty string if extraction fails
    """
    import os
    from django.core.files.storage import default_storage
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not attachment or not attachment.file:
        return ""
    
    try:
        file_path = attachment.file.path
        return extract_text_from_file(file_path)
    except Exception as e:
        logger.error(f"Error extracting text from attachment {attachment.filename}: {str(e)}")
        return ""

def extract_text_from_file(file_path):
    """
    Extract text from a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: Extracted text or empty string if extraction fails
    """
    import os
    import logging
    import subprocess
    from django.conf import settings
    
    logger = logging.getLogger(__name__)
    
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return ""
    
    # Get file extension
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        # PDF extraction using pdftotext or pdfminer
        if file_ext == '.pdf':
            try:
                # Try using pdftotext command first
                result = subprocess.run(['pdftotext', '-layout', file_path, '-'], 
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                       text=True, timeout=30)
                if result.returncode == 0:
                    return result.stdout
                else:
                    logger.warning(f"pdftotext failed: {result.stderr}")
                    raise Exception("pdftotext failed")
            except Exception as pdf_err:
                logger.warning(f"Falling back to python PDF extraction: {str(pdf_err)}")
                try:
                    from pdfminer.high_level import extract_text
                    return extract_text(file_path)
                except Exception as e:
                    logger.error(f"Failed to extract text from PDF: {str(e)}")
                    return ""
                    
        # DOCX extraction
        elif file_ext == '.docx':
            try:
                import docx
                doc = docx.Document(file_path)
                return '\n'.join([para.text for para in doc.paragraphs])
            except Exception as e:
                logger.error(f"Failed to extract text from DOCX: {str(e)}")
                return ""
                
        # DOC extraction (old Word format)
        elif file_ext == '.doc':
            try:
                # Try using antiword if available
                result = subprocess.run(['antiword', file_path], 
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                       text=True, timeout=30)
                if result.returncode == 0:
                    return result.stdout
                else:
                    logger.warning(f"antiword failed: {result.stderr}")
                    raise Exception("antiword failed")
            except Exception as doc_err:
                logger.warning(f"Antiword failed or not installed: {str(doc_err)}")
                return ""
                
        # Text files
        elif file_ext in ['.txt', '.csv', '.md', '.html', '.htm']:
            with open(file_path, 'r', errors='ignore') as f:
                return f.read()
                
        # Excel files
        elif file_ext in ['.xls', '.xlsx']:
            try:
                import pandas as pd
                # Try to read all sheets
                df_dict = pd.read_excel(file_path, sheet_name=None)
                text = ""
                for sheet_name, df in df_dict.items():
                    text += f"Sheet: {sheet_name}\n"
                    text += df.to_string(index=False) + "\n\n"
                return text
            except Exception as e:
                logger.error(f"Failed to extract text from Excel: {str(e)}")
                return ""
                
        # Unsupported format
        else:
            logger.warning(f"Unsupported file format: {file_ext}")
            return f"[Unsupported file format: {file_ext}]"
            
    except Exception as e:
        logger.error(f"Error extracting text from file {file_path}: {str(e)}")
        return ""

def is_stop_sale_chart_file(filename):
    """
    Check if the file is a stop sale chart file that should be excluded from processing.
    
    Args:
        filename: Name of the file
        
    Returns:
        bool: True if it's a chart file that should be skipped
    """
    if not filename:
        return False
        
    filename_lower = filename.lower()
    
    # Keywords to exclude from processing
    exclude_keywords = ['chart', 'summary', 'overview', 'rapor', 'özet']
    
    # Check if any exclude keyword is in the filename
    return any(keyword in filename_lower for keyword in exclude_keywords) 