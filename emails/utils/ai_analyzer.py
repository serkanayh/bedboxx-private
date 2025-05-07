import os
import json
import logging
import re
from datetime import datetime
import time
from django.utils import timezone
from django.conf import settings
from emails.models import Email, EmailRow, Market, MarketAlias

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Claude system prompt for analyzing stop sales
SYSTEM_PROMPT = """
You are an AI assistant that specializes in analyzing hotel stop sale notifications. Your task is to extract structured information from email content. 

Analyze the provided email text and extract the following information:
1. Hotel name
2. Room type(s) affected
3. Market(s) affected (e.g., UK, DE, etc.)
4. Start date of the stop sale
5. End date of the stop sale
6. Sale status type (default to "stop" if unclear)

Return the information in the following JSON format:
[
  {
    "hotel_name": "Name of hotel",
    "room_type": "Type of room affected",
    "markets": ["Market1", "Market2"],
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "sale_status": "stop|open|etc."
  },
  {
    // Additional rules if multiple are found
  }
]

IMPORTANT RULES:
- If you cannot determine specific dates, set both start_date and end_date to "UNCERTAIN"
- Do NOT make up or guess dates that aren't clearly stated in the email
- If the email mentions attachments containing the information but doesn't state the dates, return "UNCERTAIN" for the dates
- Do not include explanations or notes - respond ONLY with the JSON format
- If multiple hotels, dates, or room types are mentioned, create separate entries in the array
- Always check if the dates mentioned refer to booking dates or actual stay dates - use stay dates only
- Parse dates in any format but convert to YYYY-MM-DD in your response
- If no room type is specified, use "All Room"
- If no market is specified, use ["ALL"]
- Return an empty array if no stop sale information can be extracted
"""

# Define a standalone function for checking attachment references
def body_mentions_attachment(text):
    """
    Checks if the email body mentions attachments.
    
    Args:
        text (str): The email body text
        
    Returns:
        bool: True if attachments are mentioned, False otherwise
    """
    if not text:
        return False
        
    text = text.lower()
    
    # Keywords that might indicate attachments
    attachment_keywords = [
        'ekte', 'ekli', 'ekteki', 'ek olarak', 'attachment', 
        'attached', 'enclosed', 'ek dosya', 'ekli dosya',
        'ekte belirtilen', 'ekte gönderilen', 'ekte yer alan',
        'ektedir', 'eklerde', 'eklerde belirtilen',
        'pdf', 'excel', 'xls', 'xlsx', 'doc', 'docx',
        'attach', 'ekler', 'the attached', 'in attachment',
        'please find attached', 'lütfen ekte', 'attached file',
        'ekli belge', 'ekli doküman', 'detayları ekte', 'details attached',
        'details in attachment', 'details in the attached'
    ]
    
    # Check if any of the keywords are in the text
    return any(keyword in text for keyword in attachment_keywords)

class ClaudeAnalyzer:
    """
    Utilizes Claude AI API to analyze email content and extract structured data about stop sales.
    """
    
    def __init__(self):
        """Initialize the Claude API client using the API key from settings."""
        self.claude_client = None
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        
        if not self.api_key and 'ANTHROPIC_API_KEY' in os.environ:
            self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        
        if self.api_key and ANTHROPIC_AVAILABLE:
            try:
                self.claude_client = Anthropic(api_key=self.api_key)
                logger.info("ClaudeAnalyzer initialized.")
            except Exception as e:
                logger.error(f"Error initializing Claude client: {str(e)}")
        else:
            if not self.api_key:
                logger.error("No Anthropic API key found in settings or environment")
            if not ANTHROPIC_AVAILABLE:
                logger.error("Anthropic Python SDK not available")
    
    def analyze_email(self, email_obj):
        """
        Analyze an Email object to extract structured data.
        
        Args:
            email_obj: An Email model instance
            
        Returns:
            list: A list of dictionaries with structured data
        """
        if not self.claude_client:
            logger.error("Claude client not initialized")
            return []
        
        try:
            # Prepare the content to analyze
            email_text = email_obj.body_text or ""
            email_subject = email_obj.subject or ""
            
            # Create the content to analyze with subject for context
            content_to_analyze = f"SUBJECT: {email_subject}\n\nBODY:\n{email_text}"
            
            # Call Claude API
            response = self.claude_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": content_to_analyze}
                ]
            )
            
            # Log the raw response for debugging
            response_text = response.content[0].text
            logger.info(f"[RAW AI RESPONSE DUMP] Email ID {email_obj.id}:\n{response_text}")
            
            # Try to parse the JSON response
            try:
                rows = json.loads(response_text)
                return self._post_process_results(rows)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Claude JSON response for email {email_obj.id}")
                return []
                
        except Exception as e:
            logger.error(f"Error analyzing email {email_obj.id}: {str(e)}")
            return []
    
    def analyze_attachment(self, email_obj, attachment_text, filename):
        """
        Analyze text extracted from an attachment to extract structured data.
        
        Args:
            email_obj: The Email model instance
            attachment_text: Text extracted from the attachment
            filename: The filename of the attachment for context
            
        Returns:
            list: A list of dictionaries with structured data
        """
        if not self.claude_client:
            logger.error("Claude client not initialized")
            return []
        
        try:
            # Create content with context about the attachment
            email_subject = email_obj.subject or ""
            content_to_analyze = f"SUBJECT: {email_subject}\n\nATTACHMENT FILENAME: {filename}\n\nATTACHMENT CONTENT:\n{attachment_text}"
            
            # Call Claude API
            response = self.claude_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": content_to_analyze}
                ]
            )
            
            # Log the raw response for debugging
            response_text = response.content[0].text
            logger.info(f"[RAW AI RESPONSE DUMP] Email ID {email_obj.id} Attachment {filename}:\n{response_text}")
            
            # Try to parse the JSON response
            try:
                rows = json.loads(response_text)
                return self._post_process_results(rows)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Claude JSON response for attachment {filename}")
                return []
                
        except Exception as e:
            logger.error(f"Error analyzing attachment {filename}: {str(e)}")
            return []
    
    def _post_process_results(self, rows):
        """
        Post-process the results from Claude to ensure consistency.
        
        Args:
            rows: List of dictionaries with the extracted data
            
        Returns:
            list: The post-processed data
        """
        if not isinstance(rows, list):
            logger.warning(f"Expected list but got {type(rows)}. Returning empty list.")
            return []
        
        processed_rows = []
        
        for i, row in enumerate(rows):
            try:
                # Ensure all required fields exist
                processed_row = {
                    "hotel_name": row.get("hotel_name", "Unknown Hotel"),
                    "room_type": row.get("room_type", "All Room"),
                    "markets": row.get("markets", ["ALL"]),
                    "start_date": row.get("start_date", "UNCERTAIN"),
                    "end_date": row.get("end_date", "UNCERTAIN"),
                    "sale_status": row.get("sale_status", row.get("sale_type", "stop"))
                }
                
                # Ensure markets is a list
                if not isinstance(processed_row["markets"], list):
                    logger.warning(f"Rule #{i}: Markets is not a list. Converting to list.")
                    processed_row["markets"] = [processed_row["markets"]]
                
                # Process market names to ensure they're uppercase
                for j, market in enumerate(processed_row["markets"]):
                    if market.lower() == "all":
                        processed_row["markets"][j] = "ALL"
                    else:
                        # Check if this market name exists in the database
                        market_obj = Market.objects.filter(name__iexact=market).first()
                        if not market_obj:
                            # Check if it's a known alias
                            alias = MarketAlias.objects.filter(alias__iexact=market).first()
                            if not alias:
                                logger.warning(f"Rule #{i}: Market/Alias '{market}' not found in DB. Adding as is (uppercase).")
                                # Keep it but ensure uppercase
                                processed_row["markets"][j] = market.upper()
                            else:
                                # Replace with actual market name(s)
                                market_names = [m.name for m in alias.markets.all()]
                                logger.info(f"Rule #{i}: Resolved alias '{market}' to markets: {market_names}")
                                if j == 0:  # If this is the first market
                                    processed_row["markets"][j] = market_names[0]  # Replace first item
                                    # Add any additional markets
                                    processed_row["markets"].extend(market_names[1:])
                                else:
                                    # Replace current item with first market, will add others later
                                    processed_row["markets"][j] = market_names[0]
                                    # Add any additional markets
                                    processed_row["markets"].extend(market_names[1:])
                
                processed_rows.append(processed_row)
                
            except Exception as e:
                logger.error(f"Error processing rule #{i}: {str(e)}")
                # Skip this row
        
        logger.info(f"Post-processed {len(processed_rows)} rules from AI.")
        return processed_rows 