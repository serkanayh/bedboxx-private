"""
Attachment analyzer module for email attachments.
Extracts text and data from various file types.
"""

import os
import logging
from django.conf import settings
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

# For PDF processing
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    
# For Excel processing
try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# For Word processing
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

logger = logging.getLogger(__name__)

class AttachmentAnalyzer:
    """
    Analyzer for email attachments.
    Supports PDF, Excel, Word, and other file types.
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the attachment analyzer
        
        Args:
            api_key (str, optional): API key for Claude or other AI services
        """
        self.api_key = api_key
        
    def analyze_attachment(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze an attachment file and extract structured data
        
        Args:
            file_path (str): Path to the attachment file
            
        Returns:
            Dict: Extracted data and metadata
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {"error": "File not found", "file_path": file_path}
        
        file_ext = os.path.splitext(file_path)[1].lower()
        extracted_text = self.extract_text(file_path)
        
        # Basic metadata
        result = {
            "file_path": file_path,
            "file_extension": file_ext,
            "file_size": os.path.getsize(file_path),
            "extracted_text": extracted_text,
            "extracted_data": None
        }
        
        # TODO: Add AI-based extraction for structured data
        
        return result
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from an attachment based on file type
        
        Args:
            file_path (str): Path to the attachment file
            
        Returns:
            str: Extracted text content
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.pdf':
                return self._extract_pdf_text(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return self._extract_excel_text(file_path)
            elif file_ext == '.docx':
                return self._extract_word_text(file_path)
            elif file_ext == '.txt':
                return self._extract_text_file(file_path)
            else:
                logger.warning(f"Unsupported file extension for text extraction: {file_ext}")
                return f"[Unsupported file type: {file_ext}]"
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return f"[Error extracting text: {str(e)}]"
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF files"""
        if not PYPDF_AVAILABLE:
            return "[PDF extraction not available. Install pypdf package.]"
        
        text = ""
        try:
            with open(file_path, 'rb') as f:
                pdf = PdfReader(f)
                for page_num in range(len(pdf.pages)):
                    page = pdf.pages[page_num]
                    text += page.extract_text() + "\n\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return f"[PDF extraction error: {str(e)}]"
    
    def _extract_excel_text(self, file_path: str) -> str:
        """Extract text from Excel files"""
        if not EXCEL_AVAILABLE:
            return "[Excel extraction not available. Install openpyxl package.]"
        
        text = ""
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                text += f"\n--- Sheet: {sheet_name} ---\n"
                
                for row in sheet.rows:
                    row_text = []
                    for cell in row:
                        if cell.value is not None:
                            row_text.append(str(cell.value))
                    text += " | ".join(row_text) + "\n"
            
            return text
        except Exception as e:
            logger.error(f"Error extracting Excel text: {str(e)}")
            return f"[Excel extraction error: {str(e)}]"
    
    def _extract_word_text(self, file_path: str) -> str:
        """Extract text from Word documents"""
        if not DOCX_AVAILABLE:
            return "[Word extraction not available. Install python-docx package.]"
        
        text = ""
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
            
            # Also extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        row_text.append(cell.text)
                    text += " | ".join(row_text) + "\n"
            
            return text
        except Exception as e:
            logger.error(f"Error extracting Word text: {str(e)}")
            return f"[Word extraction error: {str(e)}]"
    
    def _extract_text_file(self, file_path: str) -> str:
        """Extract text from plain text files"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}")
            return f"[Text file extraction error: {str(e)}]"
    
    def analyze(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze an attachment file (high-level method)
        """
        return self.analyze_attachment(file_path)
        
    def analyze_text(self, file_path: str) -> str:
        """
        Analyze a text file
        """
        return self.extract_text(file_path)
        
    def extract_rules_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract rules from text content
        
        Args:
            text (str): Text content to extract rules from
            
        Returns:
            List[Dict]: List of rule dictionaries
        """
        rules = []
        
        # Extract hotel names
        hotels = self._extract_hotel_names(text)
        
        # Extract room types
        rooms = self._extract_room_types(text)
        
        # Extract dates
        dates = self._extract_dates(text)
        
        # Extract markets
        markets = self._extract_markets(text)
        
        # If we found hotels, create rules
        if hotels:
            # Default to the first hotel if multiple found
            hotel = hotels[0]
            
            # Default room type
            room_type = "All Room" if not rooms else rooms[0]
            
            # Default market
            market = "ALL" if not markets else markets[0]
            
            # Default dates (today and tomorrow if not found)
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=1)
            if dates and len(dates) >= 2:
                start_date = dates[0]
                end_date = dates[1]
            elif dates and len(dates) == 1:
                start_date = end_date = dates[0]
            
            # Create rule
            rule = {
                "hotel_name": hotel,
                "room_type": room_type,
                "market": market,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "sale_type": "stop"  # Default to stop sale
            }
            
            rules.append(rule)
        
        return rules
    
    def _extract_hotel_names(self, text: str) -> List[str]:
        """
        Extract hotel names from text content
        
        Args:
            text (str): Text content to extract hotel names from
            
        Returns:
            List[str]: List of hotel names
        """
        # Simple example implementation - in a real system, this would be more sophisticated
        # using regex, ML or other techniques
        hotel_names = []
        
        # Look for common hotel name patterns
        hotel_keywords = ["hotel", "resort", "palace", "suites", "inn"]
        
        # Split text into lines
        lines = text.split("\n")
        
        for line in lines:
            for keyword in hotel_keywords:
                if keyword.lower() in line.lower():
                    # Found potential hotel name
                    words = line.strip().split()
                    if len(words) >= 2:  # At least two words for hotel name
                        hotel_name = " ".join(words[:3])  # Take up to first 3 words 
                        hotel_names.append(hotel_name)
                        break
        
        return hotel_names
    
    def _extract_room_types(self, text: str) -> List[str]:
        """
        Extract room types from text content
        
        Args:
            text (str): Text content to extract room types from
            
        Returns:
            List[str]: List of room types
        """
        # Simple example implementation
        room_types = []
        
        # Look for common room type patterns
        room_keywords = ["room", "suite", "deluxe", "standard", "junior", "family"]
        
        # Split text into lines
        lines = text.split("\n")
        
        for line in lines:
            for keyword in room_keywords:
                if keyword.lower() in line.lower():
                    # Found potential room type
                    line_parts = line.lower().split(keyword.lower())
                    if len(line_parts) > 1:
                        before = line_parts[0].strip()
                        after = line_parts[1].strip()
                        
                        # Construct room type
                        if before and len(before.split()) <= 2:
                            room_type = before + " " + keyword
                        else:
                            room_type = keyword + " " + after.split()[0] if after else keyword
                            
                        room_types.append(room_type.strip().title())
                        break
        
        return room_types
    
    def _extract_dates(self, text: str) -> List[datetime.date]:
        """
        Extract dates from text content
        
        Args:
            text (str): Text content to extract dates from
            
        Returns:
            List[datetime.date]: List of dates
        """
        import re
        from datetime import datetime
        
        dates = []
        
        # Define date patterns to search for
        date_patterns = [
            # DD.MM.YYYY or DD/MM/YYYY
            r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b',
            # YYYY-MM-DD
            r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b',
            # Month name DD, YYYY
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b'
        ]
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    if "January" in pattern:  # Month name pattern
                        month_name = match.group(1)
                        day = int(match.group(2))
                        year = int(match.group(3))
                        
                        month_map = {
                            "january": 1, "february": 2, "march": 3, "april": 4,
                            "may": 5, "june": 6, "july": 7, "august": 8,
                            "september": 9, "october": 10, "november": 11, "december": 12
                        }
                        
                        month = month_map.get(month_name.lower())
                        if month:
                            date_obj = datetime(year, month, day).date()
                            dates.append(date_obj)
                    elif "-" in pattern:  # YYYY-MM-DD pattern
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                        
                        date_obj = datetime(year, month, day).date()
                        dates.append(date_obj)
                    else:  # DD/MM/YYYY pattern
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                        
                        date_obj = datetime(year, month, day).date()
                        dates.append(date_obj)
                except (ValueError, IndexError):
                    # Invalid date, skip
                    pass
        
        return dates
    
    def _extract_markets(self, text: str) -> List[str]:
        """
        Extract markets from text content
        
        Args:
            text (str): Text content to extract markets from
            
        Returns:
            List[str]: List of markets
        """
        # Simple example implementation
        markets = []
        
        # Look for common market keywords
        market_keywords = [
            "market", "all market", "all markets", "pazar", "pazarlar",
            "european market", "uk market", "german market"
        ]
        
        # Common market names that might appear
        common_markets = [
            "UK", "German", "Russia", "Turkish", "Dutch", "Poland", "Belgium",
            "Scandinavia", "Balkan", "European", "Middle East", "CIS"
        ]
        
        # Split text into lines
        lines = text.split("\n")
        
        for line in lines:
            line_lower = line.lower()
            
            # Check for market keywords
            for keyword in market_keywords:
                if keyword.lower() in line_lower:
                    # Extract text around the keyword
                    parts = line_lower.split(keyword.lower())
                    if len(parts) > 1:
                        if parts[1].strip():
                            # Take the words after the keyword
                            market = parts[1].strip().split()[0].upper()
                            markets.append(market)
                        elif parts[0].strip():
                            # Take the words before the keyword
                            market = parts[0].strip().split()[-1].upper()
                            markets.append(market)
                    break
            
            # Check for common market names
            for market in common_markets:
                if market.lower() in line_lower:
                    markets.append(market.upper())
        
        # If no markets found, default to "ALL"
        if not markets:
            markets.append("ALL")
        
        return markets 