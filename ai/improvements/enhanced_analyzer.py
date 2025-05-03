"""
Enhanced AI Analyzer Integration Module for StopSale Automation System

This module integrates the prompt optimization, file format processing, and multi-language
support modules into the existing ClaudeAnalyzer class.
"""

import os
import time
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Import the enhanced modules
from prompt_optimization import PromptOptimizer, initialize_optimizer
from file_format_processor import EmailAttachmentProcessor
from multi_language_support import MultiLanguageAnalyzer

# Set up logging
logger = logging.getLogger(__name__)

class EnhancedClaudeAnalyzer:
    """
    Enhanced Claude AI Analyzer with improved prompt optimization, file format support,
    and multi-language capabilities.
    """
    
    def __init__(self, api_key, base_prompt=None):
        """
        Initialize the enhanced analyzer
        
        Args:
            api_key (str): The Claude API key
            base_prompt (str, optional): Custom base prompt to use for analysis
        """
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        
        # Initialize the prompt optimizer
        self.prompt_optimizer = initialize_optimizer()
        
        # Initialize the file processor
        self.file_processor = EmailAttachmentProcessor()
        
        # Initialize the multi-language analyzer
        self.language_analyzer = MultiLanguageAnalyzer()
        
        # Set the base prompt if provided
        if base_prompt:
            self.prompt_optimizer.add_prompt(
                "custom_base", 
                base_prompt,
                "Custom base prompt provided by user"
            )
            self.prompt_optimizer.set_active_prompt("custom_base")
        
        # Enable A/B testing by default with a weighted distribution
        # favoring the enhanced_detail prompt
        self.prompt_optimizer.enable_testing({
            "enhanced_detail": 0.4,
            "with_examples": 0.2,
            "multilingual": 0.2,
            "structured_extraction": 0.2
        })
        
        # Performance metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.total_processing_time = 0
        self.total_tokens_used = 0
    
    def analyze_email_content(self, email_content, subject="", attachments=None):
        """
        Analyze email content using Claude to extract structured information.
        Enhanced with prompt optimization, multi-language support, and attachment processing.
        
        Args:
            email_content (str): The email content to analyze
            subject (str, optional): The email subject line
            attachments (list, optional): List of paths to email attachments
            
        Returns:
            dict: A dictionary containing the extracted information, or None if analysis failed
        """
        start_time = time.time()
        self.total_calls += 1
        
        if not email_content:
            logger.warning("Empty email content provided for analysis")
            return None
        
        try:
            # Step 1: Preprocess the email for language detection
            preprocessing = self.language_analyzer.preprocess_email(email_content, subject)
            detected_language = preprocessing["language"]
            logger.info(f"Detected language: {preprocessing['language_name']} ({detected_language})")
            
            # Step 2: Process attachments if provided
            attachment_content = ""
            structured_data_from_attachments = []
            
            if attachments:
                logger.info(f"Processing {len(attachments)} attachments")
                attachment_results = self.file_processor.process_attachments(attachments)
                
                for result in attachment_results:
                    if result["success"]:
                        attachment_content += f"\n\nAttachment content: {result['content'][:1000]}..."
                        structured_data_from_attachments.extend(result["structured_data"])
            
            # Step 3: Select and enhance prompt
            prompt_name = self.prompt_optimizer.select_prompt()
            base_prompt = self.prompt_optimizer.get_prompt_content(prompt_name)
            
            # Enhance prompt with language-specific instructions
            enhanced_prompt = self.language_analyzer.enhance_prompt(base_prompt, preprocessing)
            
            # Step 4: Prepare the user content
            user_content = f"Subject: {subject}\n\nBody:\n{email_content}"
            
            # Add attachment content if available
            if attachment_content:
                user_content += attachment_content
            
            # Step 5: Call the Claude API
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            payload = {
                "model": "claude-3-opus-20240229",
                "max_tokens": 4000,
                "temperature": 0.1,  # Lower temperature for more consistent output
                "system": enhanced_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            }
            
            logger.info(f"Sending request to Claude API using prompt '{prompt_name}': Subject={subject[:30]}...")
            
            import requests
            response = requests.post(self.api_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                
                # Record failed result in prompt optimizer
                self.prompt_optimizer.record_result(
                    prompt_name,
                    success=False,
                    extraction_count=0,
                    confidence=0.0,
                    processing_time=time.time() - start_time
                )
                
                return None
            
            response_data = response.json()
            
            # Get the response content
            content = response_data.get("content", [])
            if not content or not isinstance(content, list) or len(content) == 0:
                logger.error("No content in response")
                
                # Record failed result in prompt optimizer
                self.prompt_optimizer.record_result(
                    prompt_name,
                    success=False,
                    extraction_count=0,
                    confidence=0.0,
                    processing_time=time.time() - start_time
                )
                
                return None
                
            text_content = ""
            for item in content:
                if item.get("type") == "text":
                    text_content += item.get("text", "")
            
            logger.debug(f"Claude response: {text_content[:500]}...")
            
            # Step 6: Parse and process the JSON from the response
            parsed_data = self._safe_json_parse(text_content)
            
            if parsed_data:
                # Step 7: Post-process the data
                processed_data = self._post_process_data(parsed_data)
                
                # Step 8: Merge with structured data from attachments if available
                if structured_data_from_attachments:
                    self._merge_attachment_data(processed_data, structured_data_from_attachments)
                
                # Step 9: Add metadata
                processed_data["metadata"] = {
                    "detected_language": detected_language,
                    "detected_language_name": preprocessing["language_name"],
                    "prompt_used": prompt_name,
                    "processing_time": time.time() - start_time,
                    "has_attachments": bool(attachments),
                    "attachments_processed": len(attachment_results) if attachments else 0,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Record successful result in prompt optimizer
                extraction_count = len(processed_data.get("rows", []))
                self.prompt_optimizer.record_result(
                    prompt_name,
                    success=True,
                    extraction_count=extraction_count,
                    confidence=0.9,  # Could be calculated based on certainty
                    processing_time=time.time() - start_time
                )
                
                # Update performance metrics
                self.successful_calls += 1
                self.total_processing_time += time.time() - start_time
                
                logger.info(f"Successfully extracted {extraction_count} rules from email using prompt '{prompt_name}'")
                return processed_data
            else:
                logger.warning(f"Failed to parse Claude response as JSON using prompt '{prompt_name}'")
                
                # Record failed result in prompt optimizer
                self.prompt_optimizer.record_result(
                    prompt_name,
                    success=False,
                    extraction_count=0,
                    confidence=0.0,
                    processing_time=time.time() - start_time
                )
                
                return None
            
        except Exception as e:
            logger.error(f"Error in analyzing email content: {str(e)}", exc_info=True)
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
                import re
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
            import re
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
    
    def _post_process_data(self, data):
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
    
    def _merge_attachment_data(self, processed_data, attachment_data):
        """
        Merge structured data from attachments with processed data
        
        Args:
            processed_data (dict): The processed data from email content
            attachment_data (list): Structured data from attachments
            
        Returns:
            dict: The merged data
        """
        if not attachment_data:
            return processed_data
            
        rows = processed_data.get("rows", [])
        
        # Process each item from attachment data
        for item in attachment_data:
            # Try to extract hotel, room, date information
            hotel_name = None
            room_type = "All Rooms"
            start_date = None
            end_date = None
            market = "ALL"
            sale_status = "stop"  # Default
            
            # Look for hotel name in various fields
            for key, value in item.items():
                key_lower = key.lower()
                if "hotel" in key_lower or "property" in key_lower:
                    hotel_name = value
                    break
            
            # Look for room type
            for key, value in item.items():
                key_lower = key.lower()
                if "room" in key_lower or "type" in key_lower or "category" in key_lower:
                    room_type = value
                    break
            
            # Look for dates
            for key, value in item.items():
                key_lower = key.lower()
                if "start" in key_lower or "from" in key_lower or "begin" in key_lower:
                    start_date = self._normalize_date(value)
                elif "end" in key_lower or "to" in key_lower or "until" in key_lower:
                    end_date = self._normalize_date(value)
            
            # Look for market
            for key, value in item.items():
                key_lower = key.lower()
                if "market" in key_lower or "country" in key_lower or "region" in key_lower:
                    market = value.upper()
                    break
            
            # Look for sale status
            for key, value in item.items():
                key_lower = key.lower()
                value_lower = str(value).lower()
                if "status" in key_lower or "action" in key_lower or "operation" in key_lower:
                    if "open" in value_lower or "release" in value_lower or "unblock" in value_lower:
                        sale_status = "open"
                    break
            
            # Only add if we have hotel name and dates
            if hotel_name and start_date and end_date:
                rows.append({
                    "hotel_name": hotel_name,
                    "room_type": room_type,
                    "market": market,
                    "start_date": start_date,
                    "end_date": end_date,
                    "sale_status": sale_status,
                    "source": "attachment"
                })
        
        processed_data["rows"] = rows
        return processed_data
    
    def get_performance_metrics(self):
        """
        Get performance metrics for the analyzer
        
        Returns:
            dict: Performance metrics
        """
        success_rate = 0
        avg_processing_time = 0
        
        if self.total_calls > 0:
            success_rate = (self.successful_calls / self.total_calls) * 100
            
        if self.successful_calls > 0:
            avg_processing_time = self.total_processing_time / self.successful_calls
            
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "success_rate": success_rate,
            "avg_processing_time": avg_processing_time,
            "prompt_performance": self.prompt_optimizer.get_performance_report()
        }
    
    def get_best_prompt(self, min_calls=10):
        """
        Get the best performing prompt
        
        Args:
            min_calls (int): Minimum number of calls required to consider a prompt
            
        Returns:
            str: Name of the best prompt
        """
        return self.prompt_optimizer.get_best_prompt(min_calls)
    
    def set_active_prompt(self, prompt_name):
        """
        Set the active prompt
        
        Args:
            prompt_name (str): Name of the prompt to set as active
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.prompt_optimizer.set_active_prompt(prompt_name)
    
    def disable_testing(self):
        """Disable A/B testing mode"""
        self.prompt_optimizer.disable_testing()
        
    def enable_testing(self, distribution=None):
        """
        Enable A/B testing mode
        
        Args:
            distribution (dict, optional): Distribution of prompts
        """
        self.prompt_optimizer.enable_testing(distribution)
    
    def save_performance_report(self, filename):
        """
        Save performance report to a file
        
        Args:
            filename (str): Path to save the report
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.prompt_optimizer.save_report(filename)


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize the enhanced analyzer
    api_key = os.environ.get("CLAUDE_API_KEY", "your_api_key_here")
    analyzer = EnhancedClaudeAnalyzer(api_key)
    
    # Example email content
    email_content = """
    Subject: Stop Sale Notification
    
    Please be informed that the following hotel will be closed for sales:
    
    Hotel: Grand Resort Antalya
    Room Types: All Rooms
    Dates: 15.07.2025 - 30.07.2025
    Markets: UK, Germany
    
    Thank you,
    Reservation Department
    """
    
    # Analyze the email
    result = analyzer.analyze_email_content(email_content, "Stop Sale Notification")
    
    if result:
        print(f"Analysis successful! Extracted {len(result['rows'])} rows.")
        print(json.dumps(result, indent=2))
    else:
        print("Analysis failed.")
    
    # Get performance metrics
    metrics = analyzer.get_performance_metrics()
    print(f"Performance metrics: {metrics['success_rate']:.2f}% success rate")
    
    # Get best prompt
    best_prompt = analyzer.get_best_prompt(min_calls=1)
    if best_prompt:
        print(f"Best performing prompt: {best_prompt}")
        
        # Set as active prompt
        analyzer.set_active_prompt(best_prompt)
        analyzer.disable_testing()
        print(f"Set {best_prompt} as active prompt and disabled testing.")
