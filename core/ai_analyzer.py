import json
import re
import anthropic
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from django.conf import settings
from datetime import datetime, date, timedelta
from bs4 import BeautifulSoup  # HTML işleme için gerekli
import os # os modülünü import et

# --- Model Imports ---
# Import Market and MarketAlias here
from hotels.models import Market, MarketAlias

# --- Attachment Text Extraction Libraries --- 
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from docx import Document
except ImportError:
    Document = None
# --- End Attachment Libraries --- 

logger = logging.getLogger(__name__)

# --- Unified System Prompt --- 
UNIFIED_SYSTEM_PROMPT = """
You are an AI analyzing email content to extract hotel stop/open sale rules.
The user will provide the email content structured like this:
SUBJECT: <Email Subject Here>
BODY:
<Cleaned Email Body Here>

Your primary goal is to return a JSON list of rule objects based on the SUBJECT and BODY provided.

**EXTREMELY IMPORTANT RULES FOR HOTEL NAME:**
1. **USE THE SUBJECT LINE FIRST** to identify the hotel name. The subject often follows patterns like "<Hotel Name> STOP SALE" or "STOP SALE: <Hotel Name>". Extract ONLY the actual hotel name, not the entire subject.
2. **If no clear hotel name is found in the subject**, THEN look in the BODY (e.g., near company signatures, headers, or letterhead).
3. **USE THE SAME HOTEL NAME FOR ALL RULES** unless there is explicit indication of multiple hotels.
4. **NEVER use room type codes as hotel names** (e.g., don't use codes like "DROOF", "DLV", "DSEA", "DLAGE" as hotel names).
5. **WATCH FOR SIGNATURES at the end of emails** which often contain the official hotel name.

For each rule found, extract:
- hotel_name: The name of the hotel following the critical rules above.
- room_type: Specific room type or 'All Room' (for general terms like 'all rooms', 'tüm odalar').
- markets: List of markets, or ["ALL"] if unspecified.
- start_date: YYYY-MM-DD format.
- end_date: YYYY-MM-DD format. (Use start_date if only one date given).
- sale_status: 'stop' or 'open'.

ADDITIONAL INSTRUCTIONS:
- If the BODY looks like a table/list from an attachment, treat each row/item as a separate rule.
- ALWAYS format dates as YYYY-MM-DD. Assume current year if missing.
- Output ONLY the valid JSON list. No extra text, explanations, or markdown.

Example JSON Output:
```json
[
  {
    "hotel_name": "Example Hotel Name",
    "room_type": "Standard Room",
    "markets": ["UK", "DE"],
    "start_date": "2025-05-10",
    "end_date": "2025-05-15",
    "sale_status": "stop"
  },
  {
    "hotel_name": "Example Hotel Name",
    "room_type": "All Room",
    "markets": ["ALL"],
    "start_date": "2025-06-01",
    "end_date": "2025-06-01",
    "sale_status": "open"
  }
]
```

Now, analyze the following structured content:
"""
# --- End Unified System Prompt --- 


class ClaudeAnalyzer:
    """
    A unified class to analyze email content (body or extracted attachment text) 
    using the Claude API.
    Also includes methods for extracting text from attachments.
    """
    
    def __init__(self, api_key=None, prompt=None):
        """
        Initialize the analyzer with API credentials and a system prompt
        """
        self.api_key = api_key or getattr(settings, 'ANTHROPIC_API_KEY', '')
        self.system_prompt = prompt or UNIFIED_SYSTEM_PROMPT # Use unified prompt
        
        # Configure Anthropic client
        try:
            if not self.api_key:
                raise ValueError("Anthropic API key not found in settings or provided.")
            self.claude_client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("ClaudeAnalyzer initialized.")
        except ImportError:
             logger.error("Anthropic library not installed. pip install anthropic")
             self.claude_client = None
        except Exception as e:
            logger.error(f"Anthropic client failed to initialize: {e}", exc_info=True)
            self.claude_client = None
    
    # --- Text Extraction Methods (Moved from AttachmentAnalyzer) --- 
    def extract_text_from_attachment(self, file_path: str) -> Tuple[str, Optional[str]]:
        """Extracts text from a supported attachment file."""
        if not os.path.exists(file_path):
            return "", f"File not found: {os.path.basename(file_path)}"
        
        file_ext = os.path.splitext(file_path)[1].lower().strip('.')
        
        extraction_methods = {
            'pdf': self._extract_text_pdf,
            'xlsx': self._extract_text_excel,
            'xls': self._extract_text_excel,
            'docx': self._extract_text_word,
            'txt': self._extract_text_text
        }
        
        if file_ext in extraction_methods:
            return extraction_methods[file_ext](file_path)
        else:
            return "", f"Unsupported attachment format: {file_ext}"

    def _extract_text_pdf(self, file_path: str) -> Tuple[str, Optional[str]]:
        """Extracts text from PDF. Returns (text, error_message)."""
        if not PyPDF2:
            return "", 'PDF library (PyPDF2) not installed.'
        text_content = ""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                     try:
                          reader.decrypt('') # Try decrypting with empty password
                     except Exception as decrypt_err:
                          logger.warning(f"Could not decrypt PDF {os.path.basename(file_path)}: {decrypt_err}")
                          return "", f"Could not decrypt PDF: {os.path.basename(file_path)}"
                          
                for page in reader.pages:
                    try:
                        text_content += page.extract_text() or ""
                    except Exception as page_err: # Handle potential errors during page extraction
                         logger.warning(f"Error extracting text from a page in PDF {os.path.basename(file_path)}: {page_err}")
                         continue # Skip problematic pages
                         
            logger.info(f"Extracted {len(text_content)} chars from PDF: {os.path.basename(file_path)}")
            return text_content, None
        except Exception as e:
            logger.error(f"Error extracting text from PDF {os.path.basename(file_path)}: {e}", exc_info=True)
            return "", f'Error processing PDF: {str(e)}'

    def _extract_text_excel(self, file_path: str) -> Tuple[str, Optional[str]]:
        """Extracts text content from all sheets in an Excel file."""
        if not pd:
            return "", 'Excel library (pandas) not installed.'
        all_text = ""
        try:
            excel_data = pd.read_excel(file_path, sheet_name=None)
            for sheet_name, df in excel_data.items():
                # Convert entire sheet to string, preserving some structure
                sheet_text = df.to_string()
                all_text += f"\n\n--- Sheet: {sheet_name} ---\n{sheet_text}"
            logger.info(f"Extracted {len(all_text)} chars from Excel: {os.path.basename(file_path)}")
            return all_text, None
        except Exception as e:
            logger.error(f"Error extracting text from Excel {os.path.basename(file_path)}: {e}", exc_info=True)
            return "", f'Error processing Excel: {str(e)}'

    def _extract_text_word(self, file_path: str) -> Tuple[str, Optional[str]]:
         """Extracts text from DOCX files."""
         if not file_path.lower().endswith('.docx'):
             return "", '.doc file analysis requires manual conversion to .docx.'
         if not Document:
             return "", 'Word library (python-docx) not installed.'
         text_content = "" # For paragraphs
         all_text = "" # Initialize for table text
         try:
             doc = Document(file_path)
             for para in doc.paragraphs:
                 text_content += para.text + '\n'
                 
             # Optionally extract text from tables too
             if doc.tables:
                 for table in doc.tables:
                      # Ensure all_text exists before appending
                      all_text += "\n--- TABLE START ---\n"
                      try:
                           for row in table.rows:
                                row_text = []
                                for cell in row.cells:
                                     # Extract text from paragraphs within the cell
                                     cell_text = '\n'.join([p.text for p in cell.paragraphs])
                                     row_text.append(cell_text.strip())
                                all_text += " | ".join(row_text) + "\n" # Use pipe separator
                      except Exception as table_err:
                           logger.warning(f"Error processing a table in Word doc {os.path.basename(file_path)}: {table_err}")
                      all_text += "--- TABLE END ---\n"
                         
             # Combine paragraph and table text
             final_text = text_content + all_text 
             logger.info(f"Extracted {len(final_text)} chars from Word: {os.path.basename(file_path)}")
             return final_text, None # Return combined text
             
         except Exception as e:
             logger.error(f"Error extracting text from Word {os.path.basename(file_path)}: {e}", exc_info=True)
             # Check if the error is the specific UnboundLocalError
             if isinstance(e, UnboundLocalError) and 'all_text' in str(e):
                 return "", f"Error processing Word (variable assignment issue): {str(e)}"
             else:
                 return "", f'Error processing Word: {str(e)}'

    def _extract_text_text(self, file_path: str) -> Tuple[str, Optional[str]]:
        """Reads text directly from a TXT file."""
        try:
            # Try common encodings
            encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            text_content = None
            for enc in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        text_content = f.read()
                    logger.info(f"Read {len(text_content)} chars from TXT (encoding: {enc}): {os.path.basename(file_path)}")
                    break # Stop if successful
                except UnicodeDecodeError:
                    continue # Try next encoding
                except Exception as read_err: # Catch other potential errors
                     raise read_err # Re-raise other errors
                     
            if text_content is None:
                 raise ValueError("Could not decode TXT file with common encodings.")
                 
            return text_content, None
        except Exception as e:
            logger.error(f"Error reading TXT file {os.path.basename(file_path)}: {e}", exc_info=True)
            return "", f'Error reading TXT file: {str(e)}'
    # --- End Text Extraction Methods --- 
    
    # --- Email Body Cleaning --- 
    def clean_email_body(self, email_html: str, email_text: str) -> str:
        """Cleans email content, preferring HTML if available."""
        content_to_clean = email_html if email_html else email_text
        if not content_to_clean:
            return ""
            
        is_html = bool(email_html) and bool(re.search(r'<html|<body|<table|<div|<p>', email_html, re.IGNORECASE))
        
        cleaned_content = ""
        
        if is_html:
            try:
                soup = BeautifulSoup(email_html, 'html.parser')
                
                # Remove script, style, head elements
                for element in soup(["script", "style", "head", "title", "meta", "link"]):
                    element.extract()

                # Define common reply/forward markers
                REPLY_FORWARD_MARKERS_REGEX = r'(from:|sent:|to:|subject:|date:|cc:|bcc:|forwarded message|original message|begin forwarded message|on .* wrote:)'
                
                # --- NEW "Last Marker" Logic ---
                # Find ALL markers in the email content
                marker_elements = []
                
                # Search text nodes
                for element in soup.find_all(string=re.compile(REPLY_FORWARD_MARKERS_REGEX, re.IGNORECASE | re.DOTALL)):
                    parent = element.parent
                    if parent:
                        marker_elements.append(parent)
                
                # Also search style attributes that might indicate a quote separator
                quote_style_pattern = r'border-left:solid|border-left: solid|border-top:solid|border-top: solid'
                for element in soup.find_all(attrs={"style": re.compile(quote_style_pattern, re.IGNORECASE)}):
                    marker_elements.append(element)
                
                # Also check for common separator div IDs used by email clients
                for element in soup.find_all(id=re.compile(r'divRplyFwdMsg|mailRplyFwd|mailQuote', re.IGNORECASE)):
                    marker_elements.append(element)
                
                # Find the last marker in document order (if any exist)
                last_marker_element = None
                if marker_elements:
                    # Convert to a list of tag indices to find the last one in document order
                    all_tags = list(soup.find_all())
                    marker_indices = [(all_tags.index(elem) if elem in all_tags else -1) for elem in marker_elements]
                    valid_indices = [idx for idx in marker_indices if idx >= 0]
                    
                    if valid_indices:
                        last_marker_idx = max(valid_indices)
                        last_marker_element = all_tags[last_marker_idx]
                        
                        logger.info(f"Found last email marker element: {last_marker_element.name}")
                        
                        # Get all elements that follow the last marker in document order
                        nodes_to_remove = [last_marker_element] + list(last_marker_element.find_all_next())
                        
                        # Remove all the identified elements
                        for node in nodes_to_remove:
                            node.decompose()
                        
                        logger.info(f"Removed last marker and {len(nodes_to_remove)-1} subsequent elements")
                
                # --- End NEW Logic ---
                    
                # Remove common footer/disclaimer patterns more aggressively
                # (Add more patterns specific to your emails if needed)
                footer_patterns = [
                    r'confidentiality notice',
                    r'legal disclaimer',
                    r'unsubscribe',
                    r'view in browser',
                    r'sent from my iphone', 
                    r'sent from mobile',
                    r'powered by',
                    r'follow us on',
                    # Add regex patterns for specific signatures if identifiable
                ]
                for pattern in footer_patterns:
                    for element in soup.find_all(string=re.compile(pattern, re.IGNORECASE | re.DOTALL)):
                         # Try removing parent or grandparent elements if they seem like footers
                         parent = element.find_parent()
                         if parent and len(parent.get_text(strip=True)) < 300: # Heuristic: shorter elements are more likely footers
                              parent.extract()
                         elif parent and parent.find_parent() and len(parent.find_parent().get_text(strip=True)) < 300:
                              parent.find_parent().extract()
                
                # Special handling for tables (convert to text representation)
                for table in soup.find_all('table'):
                    table_text = "\n--- TABLE START ---\n"
                    try:
                        for row in table.find_all('tr'):
                            row_text = []
                            for cell in row.find_all(['td', 'th']):
                                cell_text = ' '.join(cell.get_text(strip=True, separator=' ').split())
                                row_text.append(cell_text)
                            table_text += " | ".join(row_text) + "\n"
                        table_text += "--- TABLE END ---\n"
                        # Replace table with text version
                        table.replace_with(BeautifulSoup(table_text, 'html.parser')) 
                    except Exception as table_err:
                         logger.warning(f"Error processing table in email body: {table_err}")
                         table_text += "--- TABLE PARSE ERROR ---\n"
                         table.replace_with(BeautifulSoup(table_text, 'html.parser'))
                         
                # Get text, trying to preserve some structure
                cleaned_content = soup.get_text(separator='\n', strip=True)
                
                # Final check: If cleaning resulted in empty content but original wasn't empty
                if not cleaned_content.strip() and content_to_clean.strip():
                    logger.warning("HTML cleaning resulted in empty content. Returning original content.")
                    return content_to_clean
                
            except Exception as e:
                logger.error(f"Error cleaning HTML email body: {e}. Falling back to text body.", exc_info=True)
                # Fallback to text cleaning if HTML fails
                cleaned_content = self._clean_plain_text(email_text)
        else:
             cleaned_content = self._clean_plain_text(content_to_clean)
        
        # Final whitespace cleanup
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content) # Limit consecutive newlines
        cleaned_content = re.sub(r'[ \t]{2,}', ' ', cleaned_content) # Replace multiple spaces/tabs with one
        
        return cleaned_content.strip()
    
    def _clean_plain_text(self, text_content: str) -> str:
        """Basic cleaning for plain text content."""
        if not text_content:
             return ""
        # Add basic cleaning rules if needed (e.g., remove common reply headers)
        lines = text_content.splitlines()
        cleaned_lines = []
        skip_patterns = [r'^>+', r'^On.*wrote:$', r'^From:.*$', r'^Sent:.*$', r'^To:.*$', r'^Subject:.*$']
        for line in lines:
             line_stripped = line.strip()
             if not any(re.match(p, line_stripped, re.IGNORECASE) for p in skip_patterns):
                  cleaned_lines.append(line_stripped)
                  
        cleaned_text = '\n'.join(cleaned_lines)
        # Remove excessive whitespace/newlines (apply again)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        cleaned_text = re.sub(r'[ \t]{2,}', ' ', cleaned_text)
        return cleaned_text.strip()
        
    # --- Main AI Analysis Method --- 
    def analyze_content(self, text_content: str, context_subject: str = '') -> Dict:
        """
        Analyzes provided text content (cleaned body OR extracted attachment text) using Claude.
        Accepts optional subject for context, but doesn't include it directly in the prompt.
        """
        result_template = {
            'rows': [],
            'raw_ai_response': None,
            'error': None,
            'analysis_source': 'ai' # Mark source as AI
        }
        
        if not self.claude_client:
            logger.error("Claude client not initialized. Cannot analyze content.")
            result_template['error'] = 'AI Analyzer not configured'
            return result_template

        if not text_content:
             logger.warning("No text content provided for analysis.")
             result_template['error'] = 'No content provided'
             return result_template
             
        # Limit content size before sending to AI
        max_chars = 150000 # Adjust based on typical token limits and safety margin
        if len(text_content) > max_chars:
            logger.warning(f"Content truncated for AI analysis. Original length: {len(text_content)}, truncated to {max_chars}")
            text_content = text_content[:max_chars]
            
        logger.debug(f"Sending content to Claude for analysis (first 500 chars):\n{text_content[:500]}...")
        
        try:
            message = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                temperature=0.1,
                system=self.system_prompt,
                messages=[{"role": "user", "content": text_content}]
            )
            
            raw_response = ""
            if message.content and isinstance(message.content, list):
                for block in message.content:
                    if hasattr(block, 'text'):
                        raw_response += block.text
            
            result_template['raw_ai_response'] = raw_response
            logger.debug(f"Raw response from Claude analysis: {raw_response}")
            logger.info(f"[RAW AI RESPONSE DUMP] Email ID {instance.id if 'instance' in locals() else 'N/A'}:\n{raw_response}")
            
            # Parse JSON response
            parsed_data = self._safe_json_parse(raw_response)
            
            if parsed_data is None:
                logger.error("Failed to parse JSON response from Claude analysis.")
                result_template['error'] = 'Failed to parse AI response'
                return result_template
            
            # Post-process data (normalize dates, validate, etc.)
            processed_rows = self.post_process_ai_rules(parsed_data)
            result_template['rows'] = processed_rows
            
            if not processed_rows:
                 logger.warning("AI analysis returned a valid response, but post-processing yielded no valid rows.")
                 # Keep success=True but rows=[] ? Or mark as error?
                 # Let's consider it a partial success for now, signal might check attachments.
                 pass 
                 
            logger.info(f"AI analysis successful. Extracted {len(processed_rows)} processed rows.")
            return result_template

        except anthropic.APIConnectionError as e:
             logger.error(f"Claude API connection error: {e}", exc_info=True)
             result_template['error'] = f'AI API connection error: {e}'
        except anthropic.RateLimitError as e:
             logger.error(f"Claude API rate limit exceeded: {e}", exc_info=True)
             result_template['error'] = f'AI API rate limit exceeded: {e}'
        except anthropic.APIStatusError as e:
             logger.error(f"Claude API status error: {e.status_code} - {e.response}", exc_info=True)
             result_template['error'] = f'AI API status error: {e.status_code}'
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI content analysis: {e}", exc_info=True)
            result_template['error'] = f'Unexpected AI analysis error: {e}'
            
        return result_template 

    # --- Helper methods for AI response processing --- 
    def _safe_json_parse(self, content: str) -> Optional[List[Dict]]:
        """Claude yanıtından JSON listesini güvenli bir şekilde çıkarmayı dener.
        
        Geliştirilmiş versiyon: Metin içindeki birden fazla JSON objesini bulmaya çalışır.
        """
        logger.debug(f"safe_json_parse input (ilk 500 char): {content[:500]}")
        extracted_rows = []

        if not content:
            return None
        
        # Outer try block for the whole parsing process
        try:
            # Temel temizleme
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed_successfully = False

            # --- Optimizasyon: Önce geçerli bir liste olarak ayrıştırmayı dene ---
            if content.startswith('['):
                try:
                    parsed_list = json.loads(content)
                    if isinstance(parsed_list, list):
                        logger.debug(f"Doğrudan JSON listesi başarıyla ayrıştırıldı ({len(parsed_list)} öğe).")
                        return parsed_list # Return directly if successful list parse
                    else:
                        # Parsed as JSON, but not a list
                        logger.warning("Doğrudan ayrıştırılan JSON bir liste değil, sonraki adımlara geçilecek.")
                except json.JSONDecodeError as e:
                    # Failed to parse as list
                    logger.warning(f"Doğrudan liste JSON ayrıştırma hatası: {e}. Sonraki adımlara geçilecek.")
            
            # --- Optimizasyon: Tek bir obje olarak ayrıştırmayı dene ---
            # Only try this if parsing as list failed or wasn't attempted
            # Use elif to connect it logically to the list check, but ensure it's at the correct indentation
            elif content.startswith('{') and content.endswith('}'): # Correct indentation for elif
                try:
                    single_obj = json.loads(content)
                    if isinstance(single_obj, dict):
                        logger.info("Tek JSON objesi bulundu ve liste içine alındı.")
                        return [single_obj] # Return directly if successful single object parse
                except json.JSONDecodeError as e:
                    # Failed to parse as single object
                    logger.warning(f"Tek obje JSON ayrıştırma hatası: {e}. Sonraki adımlara geçilecek.")

            # --- Ana Mantık: Metin içindeki objeleri non-greedy regex ile bul ve ayrıştır ---
            # This runs if direct list/object parsing failed or wasn't applicable
            # No need for 'if not parsed_successfully:' check here, as the code flow handles it
            
            json_obj_pattern = r'({.*?})'
            potential_matches = re.findall(json_obj_pattern, content, re.DOTALL)
            logger.debug(f"Potansiyel {len(potential_matches)} JSON objesi non-greedy regex ile bulundu.")

            match_index = 0
            for match_str in potential_matches:
                match_index += 1
                match_str = match_str.strip()
                if len(match_str) < 10 or ':' not in match_str:
                    logger.debug(f"---> [Parse Debug] Skipping potential match #{match_index} (too short or no colon): {match_str[:100]}...")
                    continue
                
                logger.debug(f"---> [Parse Debug] Attempting to parse potential match #{match_index}: {match_str[:200]}...")
                try: # Inner try for parsing each regex match
                    parsed_obj = json.loads(match_str)
                    if isinstance(parsed_obj, dict):
                        logger.info(f"---> [Parse Debug] Successfully parsed potential match #{match_index}. Keys: {list(parsed_obj.keys())}")
                        extracted_rows.append(parsed_obj)
                    else: # Corrected indentation for this else, belongs to inner if
                        logger.warning(f"---> [Parse Debug] Parsed structure for match #{match_index} is not a dict: {type(parsed_obj)}")
                # Except blocks for the inner try
                except json.JSONDecodeError as e: 
                    logger.error(f"---> [Parse Debug] FAILED to parse potential match #{match_index}. Error: {e}. Object (start): {match_str[:200]}...")
                except Exception as e: # Catch other errors during individual parsing
                    logger.error(f"---> [Parse Debug] Unexpected error processing potential match #{match_index}: {e}. Object (start): {match_str[:200]}...", exc_info=True)

            if extracted_rows:
                logger.info(f"Metinden {len(extracted_rows)} JSON objesi başarıyla ayıklandı.")
                return extracted_rows

            # If we reach here, no valid JSON was parsed by any method
            logger.warning("Metin içinden geçerli JSON objesi ayıklanamadı (tüm yöntemler denendi).")
            return None

        # Catch errors related to the outer try block (e.g., initial stripping)
        except Exception as e:
            logger.error(f"_safe_json_parse içinde beklenmeyen genel hata: {e}", exc_info=True)
            return None

    def post_process_ai_rules(self, rules: List[Dict]) -> List[Dict]:
        """Validates, normalizes rules extracted by AI, and resolves market names."""
        processed = []
        current_year = datetime.now().year

        # Pre-fetch all Market objects for efficiency
        all_markets_by_name = {m.name.strip().upper(): m for m in Market.objects.all()}
        # We will query aliases dynamically inside the loop if needed

        for rule_index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                logger.warning(f"Skipping non-dict item #{rule_index} in AI rules: {rule}")
                continue

            # --- Field Extraction and Validation ---
            hotel_name = rule.get('hotel_name')
            start_date_str = rule.get('start_date') # Expect YYYY-MM-DD
            end_date_str = rule.get('end_date')     # Expect YYYY-MM-DD
            sale_status = rule.get('sale_status') # Expect 'stop' or 'open'
            ai_markets_list = rule.get('markets', ['ALL']) # Expect list or ['ALL']

            if not all([hotel_name, start_date_str, end_date_str, sale_status]):
                logger.warning(f"Skipping rule #{rule_index} due to missing required fields (hotel, dates, status): {rule}")
                continue

            # --- Date Validation ---
            start_date = self._normalize_date(start_date_str, current_year)
            end_date = self._normalize_date(end_date_str, current_year)

            if not start_date or not end_date:
                logger.warning(f"Skipping rule #{rule_index} due to invalid date format after normalization: {rule}")
                continue

            # Ensure start <= end
            if start_date > end_date:
                logger.warning(f"Swapping start/end dates for rule #{rule_index}: {start_date} > {end_date}. Rule: {rule}")
                start_date, end_date = end_date, start_date

            rule['start_date'] = start_date.strftime('%Y-%m-%d')
            rule['end_date'] = end_date.strftime('%Y-%m-%d')

            # --- Room Type Normalization ---
            room_type = rule.get('room_type', 'All Room')
            if not room_type or str(room_type).strip().upper() in ['ALL ROOM TYPES', 'ALL ROOMS', 'TÜM ODA TIPLERI', '-']:
                room_type = 'All Room'
            rule['room_type'] = str(room_type).strip() # Ensure it's a string and stripped

            # --- Market Resolution & Normalization ---
            resolved_markets = set() # Stores resolved *canonical market names* (uppercase)
            if not isinstance(ai_markets_list, list):
                ai_markets_list = ['ALL'] # Treat non-lists as default

            for market_name in ai_markets_list:
                market_name_upper = str(market_name).strip().upper()
                if not market_name_upper:
                    continue

                if market_name_upper == "ALL":
                    resolved_markets.add("ALL")
                    # If 'ALL' is present, we can potentially break early,
                    # unless we need to log specific resolved markets alongside 'ALL'.
                    # For now, let's continue processing others for logging clarity.
                    continue

                # 1. Check direct Market name match
                matched_market = all_markets_by_name.get(market_name_upper)
                if matched_market:
                    resolved_markets.add(matched_market.name.strip().upper()) # Add the canonical name
                    logger.debug(f"Rule #{rule_index}: Market '{market_name}' matched directly.")
                    continue

                # 2. Check MarketAlias match (Query dynamically)
                try:
                    # Use filter with __iexact for case-insensitive alias matching
                    alias_obj = MarketAlias.objects.prefetch_related('markets').filter(alias__iexact=market_name_upper).first()
                    if alias_obj and alias_obj.markets.exists():
                        logger.debug(f"Rule #{rule_index}: Alias '{market_name}' found. Resolving associated markets.")
                        markets_added_from_alias = set()
                        for related_market in alias_obj.markets.all():
                            canonical_name = related_market.name.strip().upper()
                            resolved_markets.add(canonical_name)
                            markets_added_from_alias.add(canonical_name)
                        logger.debug(f"Rule #{rule_index}: Alias '{market_name}' resolved to -> {markets_added_from_alias}")
                        continue # Move to next market_name in ai_markets_list
                    else:
                         # If no alias found via iexact, proceed to step 3
                         pass
                except Exception as alias_lookup_err:
                     logger.error(f"Rule #{rule_index}: Error looking up alias '{market_name}': {alias_lookup_err}", exc_info=True)
                     # Continue to step 3 if alias lookup fails

                # 3. No direct market or alias match found
                logger.warning(f"Rule #{rule_index}: Market/Alias '{market_name}' not found in DB. Adding as is (uppercase).")
                resolved_markets.add(market_name_upper) # Add the original name (uppercase) if not found

            # Final market list handling
            final_markets = list(resolved_markets)
            if not final_markets:
                final_markets = ['ALL'] # Default to ALL if nothing resolved
            elif "ALL" in final_markets and len(final_markets) > 1:
                final_markets = ['ALL'] # If ALL is present with others, simplify to just ALL

            rule['markets'] = final_markets # Keep as list of canonical names
            rule['market'] = ", ".join(final_markets) # Comma-separated string of canonical names

            # --- Sale Status Validation & Standardization ---
            action = str(sale_status).lower().strip().replace('_sale', '') # Normalize
            if action not in ['stop', 'open']:
                logger.warning(f"Invalid sale_status '{sale_status}' in rule #{rule_index}, defaulting to stop. Rule: {rule}")
                action = 'stop'
            rule['sale_status'] = action # Use normalized 'stop' or 'open'
            rule['sale_type'] = action # For compatibility

            processed.append(rule)

        logger.info(f"Post-processed {len(processed)} rules from AI.")
        return processed

    def _normalize_date(self, date_str: Optional[str], current_year: int) -> Optional[date]:
        """Tries to parse date string into a date object, assuming current year if needed."""
        if not date_str or not isinstance(date_str, str):
            return None
    
        cleaned_date_str = date_str.strip()
        if not cleaned_date_str or cleaned_date_str.upper() in ["YYYY-MM-DD", "NULL"]:
            return None
            
        formats_to_try = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
            "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
            "%m-%d-%Y", "%m/%d/%Y", "%m.%d.%Y",
            # Formats potentially missing year
            "%d %b", "%d %B", # 15 May, 15 Mayis
            "%b %d", "%B %d", # May 15, Mayis 15
            "%d-%b", "%d-%B",
            "%b-%d", "%B-%d",
            "%d.%m", "%d/%m", "%d-%m", # 15.05, 15/05, 15-05
            "%m.%d", "%m/%d", "%m-%d"  # 05.15, 05/15, 05-15
        ]
        
        parsed_date = None
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(cleaned_date_str, fmt).date()
                # If format doesn't include year, add current year
                if '%Y' not in fmt and '%y' not in fmt:
                     parsed_date = parsed_date.replace(year=current_year)
                break # Success
            except (ValueError, TypeError):
                continue # Try next format
                
        # Handle Turkish month names if standard parsing failed
        if not parsed_date:
             month_tr_pattern = r'(\d{1,2})\s+((?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)[a-zA-ZğüşöçıİĞÜŞÖÇ]*)' 
             match = re.search(month_tr_pattern, cleaned_date_str, re.IGNORECASE)
             if match:
                 day = int(match.group(1))
                 month_name_tr = match.group(2).lower()
                 month_map_tr = {
                      'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6,
                      'temmuz': 7, 'ağustos': 8, 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12
                 }
                 month = month_map_tr.get(month_name_tr.split()[0]) # Get first word if needed
                 if month and 1 <= day <= 31:
                      try:
                           parsed_date = date(current_year, month, day)
                      except ValueError: # Handle invalid day for month (e.g., 31 Şubat)
                           logger.warning(f"Invalid day/month combination from Turkish name: {day} {month_name_tr}")
                           parsed_date = None # Mark as invalid

        if not parsed_date:
             logger.warning(f"Could not normalize date string: '{date_str}'")
             
        return parsed_date
        
    def _adjust_date_order(self, start_date: Optional[date], end_date: Optional[date]) -> tuple[Optional[date], Optional[date]]:
        """Tarih sırasını kontrol eder, gerekirse değiştirir."""
        if start_date and end_date and start_date > end_date:
            logger.warning(f"Tarihler değiştiriliyor: {start_date}, {end_date}")
            return end_date, start_date
        return start_date, end_date
    
    def _extract_key_value(self, text: str, regex: str, default: Optional[str] = None) -> Optional[str]:
        """Metin içinden regex pattern ile değer çıkarma."""
        if match := re.search(regex, text, re.IGNORECASE):
            return match.group(1).strip()
        return default
    
    def _is_date_valid(self, date_str: str) -> bool:
        """Tarih string'inin geçerli bir format olup olmadığını kontrol eder."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def _parse_date_range(self, date_range_str: str) -> tuple[Optional[date], Optional[date]]:
        """
        '10-12 MARCH', '10 - 15 APRIL' gibi tarih aralıklarını ayrıştırır.
        
        Args:
            date_range_str: Tarih aralığı string'i
            
        Returns:
            (start_date, end_date) tuple olarak iki tarih. Ayrıştırılamazsa (None, None).
        """
        if not date_range_str or not isinstance(date_range_str, str):
            return None, None
            
        date_range_str = date_range_str.strip().upper()
        
        # Month adı ve iki sayı (gün aralığı) içeren patternler için
        month_pattern = r'(\d{1,2})\s*[-\/to]+\s*(\d{1,2})\s+((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|OCAK|ŞUBAT|MART|NİSAN|MAYIS|HAZİRAN|TEMMUZ|AĞUSTOS|EYLÜL|EKİM|KASIM|ARALIK)[A-Za-z]*)'
        
        month_match = re.search(month_pattern, date_range_str)
        if month_match:
            start_day = int(month_match.group(1))
            end_day = int(month_match.group(2))
            month_name = month_match.group(3)
            
            # Ay adları sözlüğü 
            month_names = {
                "JANUARY": 1, "JAN": 1, "OCAK": 1,
                "FEBRUARY": 2, "FEB": 2, "ŞUBAT": 2, "SUBAT": 2,
                "MARCH": 3, "MAR": 3, "MART": 3,
                "APRIL": 4, "APR": 4, "NİSAN": 4, "NISAN": 4,
                "MAY": 5, "MAYIS": 5,
                "JUNE": 6, "JUN": 6, "HAZİRAN": 6, "HAZIRAN": 6,
                "JULY": 7, "JUL": 7, "TEMMUZ": 7,
                "AUGUST": 8, "AUG": 8, "AĞUSTOS": 8, "AGUSTOS": 8,
                "SEPTEMBER": 9, "SEP": 9, "EYLÜL": 9, "EYLUL": 9,
                "OCTOBER": 10, "OCT": 10, "EKİM": 10, "EKIM": 10,
                "NOVEMBER": 11, "NOV": 11, "KASIM": 11,
                "DECEMBER": 12, "DEC": 12, "ARALIK": 12
            }
            
            # Ay adını standardize et
            month_num = None
            for name, num in month_names.items():
                if month_name.startswith(name):
                    month_num = num
                    break
            
            if month_num and 1 <= start_day <= 31 and 1 <= end_day <= 31:
                # Geçerli yılı kullan
                current_year = datetime.now().year
                
                try:
                    start_date = date(current_year, month_num, start_day)
                    end_date = date(current_year, month_num, end_day)
                    
                    # end_date < start_date ise muhtemelen yanlış tarih sıralaması var
                    if end_date < start_date:
                        logger.warning(f"Tarih sıralaması düzeltiliyor: {start_day}-{end_day} {month_name}")
                        start_date, end_date = end_date, start_date
                        
                    return start_date, end_date
                except ValueError as e:
                    logger.warning(f"Geçersiz tarih aralığı: {start_day}-{end_day} {month_name}, hata: {e}")
        
        # Eğer standart pattern ile eşleşme bulunmazsa, iki tarihli formatlara bak
        # Örn: "10 MARCH - 15 APRIL 2023"
        two_dates_pattern = r'(\d{1,2})\s+((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|OCAK|ŞUBAT|MART|NİSAN|MAYIS|HAZİRAN|TEMMUZ|AĞUSTOS|EYLÜL|EKİM|KASIM|ARALIK)[A-Za-z]*)\s*[-\/to]+\s*(\d{1,2})\s+((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|OCAK|ŞUBAT|MART|NİSAN|MAYIS|HAZİRAN|TEMMUZ|AĞUSTOS|EYLÜL|EKİM|KASIM|ARALIK)[A-Za-z]*)'
        
        two_dates_match = re.search(two_dates_pattern, date_range_str)
        if two_dates_match:
            start_day = int(two_dates_match.group(1))
            start_month_name = two_dates_match.group(2)
            end_day = int(two_dates_match.group(3))
            end_month_name = two_dates_match.group(4)
            
            # Ay adları sözlüğü 
            month_names = {
                "JANUARY": 1, "JAN": 1, "OCAK": 1,
                "FEBRUARY": 2, "FEB": 2, "ŞUBAT": 2, "SUBAT": 2,
                "MARCH": 3, "MAR": 3, "MART": 3,
                "APRIL": 4, "APR": 4, "NİSAN": 4, "NISAN": 4,
                "MAY": 5, "MAYIS": 5,
                "JUNE": 6, "JUN": 6, "HAZİRAN": 6, "HAZIRAN": 6,
                "JULY": 7, "JUL": 7, "TEMMUZ": 7,
                "AUGUST": 8, "AUG": 8, "AĞUSTOS": 8, "AGUSTOS": 8,
                "SEPTEMBER": 9, "SEP": 9, "EYLÜL": 9, "EYLUL": 9,
                "OCTOBER": 10, "OCT": 10, "EKİM": 10, "EKIM": 10,
                "NOVEMBER": 11, "NOV": 11, "KASIM": 11,
                "DECEMBER": 12, "DEC": 12, "ARALIK": 12
            }
            
            # Ay adlarını standardize et
            start_month_num = None
            end_month_num = None
            
            for name, num in month_names.items():
                if start_month_name.startswith(name):
                    start_month_num = num
                if end_month_name.startswith(name):
                    end_month_num = num
            
            if start_month_num and end_month_num and 1 <= start_day <= 31 and 1 <= end_day <= 31:
                # Geçerli yılı kullan
                current_year = datetime.now().year
                
                try:
                    start_date = date(current_year, start_month_num, start_day)
                    end_date = date(current_year, end_month_num, end_day)
                    
                    # Eğer bitiş ayı başlangıç ayından önce ise, muhtemelen yıllar farklı
                    # Örn: Aralık 2023 - Ocak 2024
                    if end_month_num < start_month_num:
                        end_date = date(current_year + 1, end_month_num, end_day)
                        
                    return start_date, end_date
                except ValueError as e:
                    logger.warning(f"Geçersiz tarih aralığı: {start_day} {start_month_name} - {end_day} {end_month_name}, hata: {e}")
        
        # Hiçbir durumda eşleşme bulunamazsa
        return None, None
    
    def post_process_data(self, data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Ayrıştırılmış veriyi işleyerek normalleştirir ve filtreler."""
        if not data or not isinstance(data, list):
            return {"rows": []}
            
        processed_data = {"rows": []}
        for rule in data:
            if not isinstance(rule, dict):
                continue
                
            # Değerleri çıkar
            hotel_name = rule.get("hotel_name")
            room_type_mail_raw = rule.get("room_type") or rule.get("room_types", [])
            
            # Liste formatındaki oda tiplerini işle
            if isinstance(room_type_mail_raw, list):
                room_type_mail = ', '.join([str(rt) for rt in room_type_mail_raw if rt]) or "All Room Types"
            else:
                room_type_mail = str(room_type_mail_raw or "All Room Types").strip()
            if not room_type_mail:
                room_type_mail = "All Room Types"
            
            # Markets değerlerini işle
            markets_list = rule.get("markets", ["ALL"])
            if isinstance(markets_list, list):
                markets = ', '.join(m for m in markets_list if m and isinstance(m, str)).strip()
            else:
                markets = str(markets_list or 'ALL').strip()
            if not markets:
                markets = "ALL"
            
            # Satış durumunu işle
            sale_status_raw = str(rule.get("sale_status") or 'stop').lower().strip()
            sale_type = sale_status_raw if sale_status_raw in ['stop', 'open'] else 'stop'
            
            # Tarihleri işle
            start_dt = None
            end_dt = None
            
            # Eğer date_range (tarih aralığı) bilgisi doğrudan verilmişse
            date_range_str = rule.get("date_range")
            if date_range_str:
                start_dt, end_dt = self._parse_date_range(date_range_str)
            
            # Tarihi date_range'den alamazsak normal start_date/end_date'den almayı dene
            if not (start_dt and end_dt):
                start_dt = self._normalize_date(rule.get("start_date"))
                end_dt = self._normalize_date(rule.get("end_date"))
                start_dt, end_dt = self._adjust_date_order(start_dt, end_dt)
            
            # Tarihler geçerliyse kayıt oluştur
            if start_dt and end_dt:
                processed_data["rows"].append({
                    'hotel_name': hotel_name,
                    'room_type': room_type_mail,
                    'market': markets,
                    'start_date': start_dt.strftime('%d.%m.%Y'),
                    'end_date': end_dt.strftime('%d.%m.%Y'),
                    'sale_type': sale_type
                })
            else:
                logger.warning(f"Kural atlandı: Geçersiz/eksik tarihler - {rule.get('start_date')}, {rule.get('end_date')}")
                
        return processed_data
    
    def clean_email_content(self, email_content: str) -> str:
        """
        Clean and preprocess email content to reduce token usage while preserving structure
        
        Args:
            email_content: Raw email content
            
        Returns:
            Cleaned email content with preserved structure
        """
        if not email_content:
            return ""
        
        cleaned_content = "" # Initialize cleaned_content
        
        # Check if content is HTML
        is_html = bool(re.search(r'<html|<body|<table|<div|<p>', email_content, re.IGNORECASE))
        
        html_processed_successfully = False
        if is_html:
            try:
                # Try importing BeautifulSoup here, closer to where it's used
                from bs4 import BeautifulSoup 
                
                # Parse HTML content
                soup = BeautifulSoup(email_content, 'html.parser')
                
                # ... (rest of the HTML cleaning logic using soup) ...
                # (Assuming the existing logic inside this try block is correct)

                # Get text with some basic structure preservation
                lines = soup.get_text().split('\\n')
                cleaned_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        cleaned_lines.append(line)
                
                # Join with newlines to preserve paragraph structure
                cleaned_content = '\\n\\n'.join(cleaned_lines)
                
                html_processed_successfully = True # Mark success
                
            except ImportError: # This except belongs to the HTML try block
                logger.warning("BeautifulSoup not installed. Basic HTML cleaning will be used.")
                # html_processed_successfully remains False
            except Exception as e: # This except also belongs to the HTML try block
                logger.error(f"Error processing HTML content: {e}", exc_info=True)
                # html_processed_successfully remains False
        
        # If HTML processing failed or it wasn't HTML, use basic cleaning
        if not html_processed_successfully:
            logger.debug("Performing basic cleaning for plain text or as fallback.")
            # Basic cleaning for plain text 
            patterns_to_remove = [
                r'From:.*?(?=\\n\\n|\\Z)', 
                r'Sent:.*?(?=\\n\\n|\\Z)',
                r'To:.*?(?=\\n\\n|\\Z)',
                r'Subject:.*?(?=\\n\\n|\\Z)',
                r'Cc:.*?(?=\\n\\n|\\Z)',
                r'This email and any files.*?$',
                r'DISCLAIMER.*?$',
                r'Confidentiality Notice.*?$',
                r'[^s]+@[^s]+\\.[^s]+', # Remove most email addresses - corrected regex escaping
                r'(?:\\+\\d{1,3}|\\b)\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b' # Remove phone numbers - corrected regex escaping
            ]
            
            temp_cleaned_content = email_content # Start with original if HTML failed
            for pattern in patterns_to_remove:
                temp_cleaned_content = re.sub(pattern, '', temp_cleaned_content, flags=re.IGNORECASE | re.DOTALL)
            
            cleaned_content = temp_cleaned_content # Assign result to cleaned_content
        
        # Final whitespace cleanup (applied to both HTML extracted text and plain text)
        cleaned_content = re.sub(r'\\n{3,}', '\\n\\n', cleaned_content) # Limit consecutive newlines
        cleaned_content = re.sub(r'\\s{2,}', ' ', cleaned_content) # Replace multiple spaces/tabs with one
        
        return cleaned_content.strip()
        
    def analyze_email_content(self, email_content: str, email_subject: str = '') -> Dict:
        """
        Analyzes email content using Claude, returning structured data.
        Sends both subject and cleaned body to the AI.
        """
        logger.info("Proceeding with AI analysis for email content (including subject).")
        
        if not self.claude_client:
            logger.error("Claude client not initialized.")
            # Ensure consistent return structure on error
            return {'error': 'AI Analyzer not configured', 'rows': [], 'raw_ai_response': None, 'has_sale_info': False, 'should_analyze_attachments': False} 
        
        # Prepare content for Claude
        cleaned_content = self.clean_email_content(email_content)
        
        # --- Construct the input string including SUBJECT and BODY ---
        content_to_send = f"SUBJECT: {email_subject}\nBODY:\n{cleaned_content}"
        # --- End content construction ---
        
        # Limit content size (applied to combined string)
        max_tokens_approx = 100000  # Example limit, adjust based on model
        if len(content_to_send) > max_tokens_approx * 4: # Rough estimate: 1 token ~ 4 chars
            original_len = len(content_to_send)
            # Truncate primarily from the body part to preserve the subject
            subject_len = len(f"SUBJECT: {email_subject}\nBODY:\n")
            max_body_len = (max_tokens_approx * 4) - subject_len
            if max_body_len > 0:
                 content_to_send = f"SUBJECT: {email_subject}\nBODY:\n{cleaned_content[:max_body_len]}"
            else: # If subject itself is too long, truncate the whole thing
                 content_to_send = content_to_send[:max_tokens_approx * 4]
            logger.warning(f"Content truncated for AI analysis. Original length: {original_len}, Truncated length: {len(content_to_send)}")
            
        # Log the exact content being sent at INFO level for easier debugging
        logger.info(f"""[AI INPUT DUMP] Sending structured content to Claude:
SUBJECT: {email_subject}
BODY (first 1000 chars):
{cleaned_content[:1000]}...""")
        
        try:
            message = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                temperature=0.1,
                system=self.system_prompt, # Use the updated prompt
                messages=[
                    {
                        "role": "user",
                        "content": content_to_send # Send combined subject and body
                    }
                ]
            )
            
            # Extract response content
            raw_response_content = ""
            if message.content and isinstance(message.content, list):
                for block in message.content:
                    if hasattr(block, 'text'):
                        raw_response_content += block.text
            
            # Corrected multiline f-string for the second debug log
            logger.debug(f"""Raw response from Claude:
{raw_response_content}""")
            
            # Add the raw response dump log here for easier debugging
            logger.info(f"[RAW AI RESPONSE DUMP] Email Subject: {email_subject}\nResponse:\n{raw_response_content}")

            # Parse JSON response
            parsed_data = self._safe_json_parse(raw_response_content)
            
            if parsed_data is None:
                logger.error("Failed to parse JSON response from Claude.")
                # Ensure consistent return structure
                return {'error': 'Failed to parse AI response', 'rows': [], 'raw_ai_response': raw_response_content, 'has_sale_info': True, 'should_analyze_attachments': False} 
            
            # Post-process data (normalize dates, etc.)
            # Assuming post_process_data correctly handles the format from AI
            processed_result = self.post_process_data(parsed_data) 
            
            # Add raw response and flags to the final result
            processed_result['raw_ai_response'] = raw_response_content
            # Determine these flags based on whether rows were actually processed
            processed_result['has_sale_info'] = bool(processed_result.get('rows')) 
            processed_result['should_analyze_attachments'] = not bool(processed_result.get('rows')) # Suggest attachment if no rows

            logger.info(f"AI analysis successful. Extracted {len(processed_result.get('rows', []))} rows.")
            return processed_result
            
        except anthropic.APIConnectionError as e:
            logger.error(f"Claude API connection error: {e}", exc_info=True)
            return {'error': f'AI API connection error: {e}', 'rows': [], 'raw_ai_response': None, 'has_sale_info': False, 'should_analyze_attachments': True} # Suggest attachment on error
        except anthropic.RateLimitError as e:
            logger.error(f"Claude API rate limit exceeded: {e}", exc_info=True)
            return {'error': f'AI API rate limit exceeded: {e}', 'rows': [], 'raw_ai_response': None, 'has_sale_info': False, 'should_analyze_attachments': True}
        except anthropic.APIStatusError as e:
            logger.error(f"Claude API status error: {e.status_code} - {e.response}", exc_info=True)
            return {'error': f'AI API status error: {e.status_code}', 'rows': [], 'raw_ai_response': None, 'has_sale_info': False, 'should_analyze_attachments': True}
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI analysis: {e}", exc_info=True)
            return {'error': f'Unexpected AI analysis error: {e}', 'rows': [], 'raw_ai_response': None, 'has_sale_info': False, 'should_analyze_attachments': True}