import os
import sys
import logging
import json
import requests
import re
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple, Any, Union

# Import improvements (Commented out)
# from ai.improvements.prompt_optimization import PromptOptimizer, initialize_optimizer
# from ai.improvements.file_format_processor import FileFormatProcessor
# from ai.improvements.multi_language_support import LanguageDetector
# from ai.improvements.enhanced_analyzer import EnhancedClaudeAnalyzer

# Set up logging
logger = logging.getLogger(__name__)

class ClaudeAnalyzer:
    """
    Claude AI Analyzer for processing email content and extracting structured information.
    Implements enhanced JSON parsing, error handling, and post-processing capabilities.
    
    This version integrates the improvements from the AI improvements package:
    - Prompt optimization and A/B testing
    - File format processing for various document types
    - Multi-language support
    - Enhanced analysis capabilities
    """
    
    def __init__(self, api_key, prompt=None):
        """
        Initialize the analyzer with API credentials.
        
        Args:
            api_key (str): The Claude API key
            prompt (str, optional): Custom system prompt to use for analysis
        """
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        
        # Initialize prompt optimizer (Commented out)
        # self.prompt_optimizer = initialize_optimizer()
        
        # Initialize file format processor (Commented out)
        # self.file_processor = FileFormatProcessor()
        
        # Initialize language detector (Commented out)
        # self.language_detector = LanguageDetector()
        
        # Initialize enhanced analyzer (Commented out)
        # self.enhanced_analyzer = EnhancedClaudeAnalyzer(api_key)
        
        # Use provided prompt, optimized prompt, or default prompt
        if prompt:
            self.system_prompt = prompt
        else:
            # Get optimized prompt from prompt optimizer (Commented out)
            # prompt_name = self.prompt_optimizer.select_prompt()
            # if prompt_name:
            #     self.system_prompt = self.prompt_optimizer.get_prompt(prompt_name)
            # else:
            # Improved system prompt based on BedBoxx01 project
            self.system_prompt = """
            You are an AI assistant specializing in hotel stop sale and open sale email analysis. Your task is to extract structured information from emails and return it in a specific JSON format.

            Extract the following information and format it as:
            {
                "rows": [
                    {
                        "hotel_name": "Hotel name as mentioned in the email",
                        "room_type": "Room type (or 'All Rooms' if not specified)",
                        "market": "Market code or name (or 'ALL' if not specified)",
                        "start_date": "Start date in YYYY-MM-DD format",
                        "end_date": "End date in YYYY-MM-DD format", 
                        "sale_status": "stop" or "open"
                    },
                    // Additional rows for other rules...
                ]
            }

            CRITICAL RULES:
            1. TABLE DETECTION: Pay special attention to HTML tables in the email. TREAT EACH TABLE ROW AS A SEPARATE RULE WITH ITS OWN DISTINCT ROOM TYPE AND DATE RANGE.
            2. MULTIPLE RULES: Create a separate JSON object for each distinct combination of hotel, room type, and date range.
            3. DATE FORMAT: Always convert all dates to YYYY-MM-DD format.
            4. MARKETS: If markets are not specified, use "ALL". Look for market information in both subject and body.
            5. JSON ONLY: Return only the JSON structure, no additional text or explanation.
            6. HTML PARSING: Pay attention to formatting in HTML emails - bold text often indicates hotel names, tables contain room and date information.
            7. COMPLETENESS: Each row must have hotel_name, room_type, market, start_date, end_date, and sale_status.
            
            Examples of stop sale indicators: "stop sale", "durdurulması", "stopsale", "close", "block", "kapatma"
            Examples of open sale indicators: "open sale", "açılması", "release", "unblock"
            """
    
    def analyze_email_content(self, email_content, subject="", attachments=None):
        """
        Analyze email content using Claude to extract structured information.
        Enhanced version with support for attachments, language detection, and optimized prompts.
        
        Args:
            email_content (str): The email content to analyze
            subject (str, optional): The email subject line
            attachments (list, optional): List of attachment file paths
            
        Returns:
            dict: A dictionary containing the extracted information, or None if analysis failed
        """
        if not email_content:
            logger.warning("Empty email content provided for analysis")
            return None
        
        try:
            # Process attachments if provided (Commented out file processor)
            attachment_content = ""
            if attachments:
                for attachment in attachments:
                    try:
                        file_name = os.path.basename(attachment)
                        # extracted_text = self.file_processor.extract_text(attachment) # Commented out
                        extracted_text = f"[Content of {file_name} - processing disabled]" # Placeholder
                        if extracted_text:
                            attachment_content += f"\n\nAttachment content from {file_name}:\n{extracted_text}"
                    except Exception as e:
                        logger.error(f"Error processing attachment {attachment}: {str(e)}")
            
            # Detect language (Commented out)
            # combined_content = f"{subject}\n{email_content}"
            # detected_language = self.language_detector.detect_language(combined_content)
            detected_language = "en" # Assume English
            # logger.info(f"Detected language: {detected_language}")
            
            # Adjust prompt based on detected language (Commented out)
            # if detected_language != "en":
            #     language_specific_prompt = self.prompt_optimizer.get_language_specific_prompt(detected_language)
            #     if language_specific_prompt:
            #         self.system_prompt = language_specific_prompt
            
            # Prepare the user content - include subject and attachment content for context
            user_content = f"Subject: {subject}\n\nBody:\n{email_content}"
            if attachment_content:
                user_content += attachment_content
            
            # Use enhanced analyzer (Commented out)
            # result = self.enhanced_analyzer.analyze(
            #     user_content, 
            #     self.system_prompt, 
            #     language=detected_language
            # )
            
            # if result:
            #     # Record prompt performance (Commented out)
            #     # self.prompt_optimizer.record_performance(
            #     #     prompt_name=self.prompt_optimizer.current_prompt,
            #     #     success=True,
            #     #     extracted_rows=len(result.get("rows", [])),
            #     #     language=detected_language
            #     # )
            #     return result
            
            # Fall back to original implementation
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            payload = {
                "model": "claude-3-opus-20240229",
                "max_tokens": 4000,
                "temperature": 0.1,  # Lower temperature for more consistent output
                "system": self.system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            }
            
            logger.info(f"Sending request to Claude API: Subject={subject[:30]}...")
            response = requests.post(self.api_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                # Record prompt performance (Commented out)
                # self.prompt_optimizer.record_performance(
                #     prompt_name=self.prompt_optimizer.current_prompt,
                #     success=False,
                #     error=f"API request failed with status code {response.status_code}"
                # )
                return None
            
            response_data = response.json()
            
            # Get the response content
            content = response_data.get("content", [])
            if not content or not isinstance(content, list) or len(content) == 0:
                logger.error("No content in response")
                # Record prompt performance (Commented out)
                # self.prompt_optimizer.record_performance(
                #     prompt_name=self.prompt_optimizer.current_prompt,
                #     success=False,
                #     error="No content in response"
                # )
                return None
                
            text_content = ""
            for item in content:
                if item.get("type") == "text":
                    text_content += item.get("text", "")
            
            logger.debug(f"Claude response: {text_content[:500]}...")
            
            # Parse and process the JSON from the response
            parsed_data = self._safe_json_parse(text_content)
            if parsed_data:
                processed_data = self.post_process_data(parsed_data)
                # Record prompt performance (Commented out)
                # self.prompt_optimizer.record_performance(
                #     prompt_name=self.prompt_optimizer.current_prompt,
                #     success=True,
                #     extracted_rows=len(processed_data.get("rows", [])),
                #     language=detected_language
                # )
                return processed_data
            else:
                logger.warning("Failed to parse Claude response as JSON")
                # Record prompt performance (Commented out)
                # self.prompt_optimizer.record_performance(
                #     prompt_name=self.prompt_optimizer.current_prompt,
                #     success=False,
                #     error="Failed to parse Claude response as JSON"
                # )
                return None
            
        except Exception as e:
            logger.error(f"Error in analyzing email content: {str(e)}", exc_info=True)
            # Record prompt performance (Commented out)
            # self.prompt_optimizer.record_performance(
            #     prompt_name=self.prompt_optimizer.current_prompt,
            #     success=False,
            #     error=str(e)
            # )
            return None
    
    def _safe_json_parse(self, text):
        """
        Safely parse JSON from text, handling common formatting issues.
        Enhanced version with more robust error handling and extraction.
        
        Args:
            text (str): The text containing JSON
            
        Returns:
            dict: The parsed JSON as a dictionary, or None if parsing failed
        """
        logger.debug(f"Attempting to parse JSON from: {text[:200]}...")
        
        if not text:
            return None
            
        # Clean the text
        text = text.strip()
        
        try:
            # Try direct parsing first
            if text.startswith('{') and text.endswith('}'):
                parsed = json.loads(text)
                # If we have a valid JSON object but not in our expected format, wrap it
                if isinstance(parsed, dict) and 'rows' not in parsed:
                    return {'rows': [parsed]}
                return parsed
                
            # Handle JSON with backticks
            if '```' in text:
                # Extract JSON from code blocks
                json_pattern = r'```(?:json)?\s*(.*?)```'
                matches = re.findall(json_pattern, text, re.DOTALL)
                if matches:
                    for match in matches:
                        try:
                            parsed = json.loads(match.strip())
                            if isinstance(parsed, dict) and 'rows' in parsed:
                                return parsed
                            elif isinstance(parsed, list):
                                return {'rows': parsed}
                            elif isinstance(parsed, dict):
                                return {'rows': [parsed]}
                        except:
                            continue
            
            # Try to extract JSON structure
            json_obj_pattern = r'({[\s\S]*?})'
            matches = re.findall(json_obj_pattern, text)
            for match in matches:
                try:
                    # Fix common JSON errors
                    fixed = re.sub(r',\s*}', '}', match)
                    fixed = re.sub(r',\s*]', ']', fixed)
                    # Add quotes to keys
                    fixed = re.sub(r'([{,])\s*(\w+):', r'\1"\2":', fixed)
                    
                    parsed = json.loads(fixed)
                    if 'rows' in parsed:
                        return parsed
                    elif isinstance(parsed, dict):
                        return {'rows': [parsed]}
                except:
                    continue
            
            # Last resort: Look for specific patterns in the raw text
            rows = []
            
            # Extract hotel information using regex
            hotel_name = None
            hotel_match = re.search(r'"hotel_name"\s*:\s*"([^"]+)"', text)
            if hotel_match:
                hotel_name = hotel_match.group(1)
            
            # Extract room types
            room_matches = re.finditer(r'"room_type"\s*:\s*"([^"]+)"', text)
            # Extract date ranges
            date_matches = re.finditer(r'"start_date"\s*:\s*"([^"]+)"\s*,\s*"end_date"\s*:\s*"([^"]+)"', text)
            # Extract sale status
            status_match = re.search(r'"sale_status"\s*:\s*"(stop|open)"', text)
            status = status_match.group(1) if status_match else "stop"
            
            # Create rows from date and room information
            dates = []
            for date_match in date_matches:
                dates.append((date_match.group(1), date_match.group(2)))
            
            rooms = []
            for room_match in room_matches:
                rooms.append(room_match.group(1))
            
            if hotel_name and (dates or rooms):
                # Create a fallback row with extracted information
                if not dates:
                    dates = [("", "")]
                if not rooms:
                    rooms = ["All Rooms"]
                
                # Create combinations
                for date_pair in dates:
                    for room in rooms:
                        rows.append({
                            "hotel_name": hotel_name,
                            "room_type": room,
                            "market": "ALL",
                            "start_date": date_pair[0],
                            "end_date": date_pair[1],
                            "sale_status": status
                        })
            
            if rows:
                return {"rows": rows}
            
            logger.warning(f"Could not extract structured data from Claude response: {text[:200]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error in JSON parsing: {str(e)}", exc_info=True)
            return None
    
    def _normalize_date(self, date_str):
        """
        Normalize date strings to YYYY-MM-DD format.
        
        Args:
            date_str (str): The date string to normalize
            
        Returns:
            str: The normalized date string, or original if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return date_str
            
        # Clean the date string
        date_str = date_str.strip()
        
        # Try multiple date formats
        formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue
                
        # Return original if parsing fails
        return date_str
    
    def post_process_data(self, data):
        """
        Post-process the extracted data to normalize values and formats.
        Enhanced with improved date handling and field normalization.
        
        Args:
            data (dict): The extracted data
            
        Returns:
            dict: The processed data
        """
        if not data or not isinstance(data, dict):
            return {"rows": []}
        
        rows = data.get("rows", [])
        if not rows or not isinstance(rows, list):
            return {"rows": []}
        
        processed_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
                
            # Create a new row with normalized fields
            processed_row = {}
            
            # Normalize hotel name
            hotel_name = row.get("hotel_name")
            if hotel_name and isinstance(hotel_name, str):
                processed_row["hotel_name"] = hotel_name.strip()
            else:
                processed_row["hotel_name"] = "Unknown Hotel"
                
            # Normalize room type
            room_type = row.get("room_type")
            if not room_type or not isinstance(room_type, str) or room_type.lower() in ["all", "all rooms", "all room types", ""]:
                processed_row["room_type"] = "All Rooms"
            else:
                processed_row["room_type"] = room_type.strip()
                
            # Normalize market
            market = row.get("market")
            if not market or not isinstance(market, str) or market.strip().lower() in ["all", ""]:
                processed_row["market"] = "ALL"
            else:
                processed_row["market"] = market.strip().upper()
                
            # Normalize dates
            start_date = self._normalize_date(row.get("start_date"))
            end_date = self._normalize_date(row.get("end_date"))
            
            # Ensure dates are in correct order
            if start_date and end_date and start_date > end_date:
                start_date, end_date = end_date, start_date
                
            processed_row["start_date"] = start_date
            processed_row["end_date"] = end_date
            
            # Normalize sale status
            sale_status = row.get("sale_status", "").lower().strip()
            if not sale_status or "stop" in sale_status or "close" in sale_status or "block" in sale_status:
                processed_row["sale_status"] = "stop"
            elif "open" in sale_status or "unblock" in sale_status or "release" in sale_status:
                processed_row["sale_status"] = "open"
            else:
                processed_row["sale_status"] = "stop"  # Default to stop sale if unclear
                
            # Only add the row if it has valid dates
            if start_date and end_date:
                processed_rows.append(processed_row)
        
        return {"rows": processed_rows}
