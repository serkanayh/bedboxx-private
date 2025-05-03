import os
import sys
import unittest
from datetime import datetime
import tempfile

# Add project directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the AttachmentAnalyzer
from core.ai.attachment_analyzer import AttachmentAnalyzer

class TestAttachmentAnalyzer(unittest.TestCase):
    """Test cases for the AttachmentAnalyzer class."""
    
    def setUp(self):
        """Set up the test environment."""
        self.analyzer = AttachmentAnalyzer()
        self.temp_files = []
    
    def tearDown(self):
        """Clean up temporary files."""
        for file_path in self.temp_files:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def create_temp_file(self, content, extension):
        """Create a temporary file with the given content and extension."""
        fd, file_path = tempfile.mkstemp(suffix=f'.{extension}')
        os.close(fd)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.temp_files.append(file_path)
        return file_path
    
    def test_extract_hotel_names(self):
        """Test extracting hotel names from text."""
        # Test case 1: Simple hotel name with Hotel: prefix
        text1 = "Hotel: Grand Plaza\nThe hotel is closed for renovation."
        hotels1 = self.analyzer._extract_hotel_names(text1)
        self.assertIn("Grand Plaza", hotels1)
        
        # Test case 2: Multiple hotel names
        text2 = "Hotel: Sunshine\nResort: Paradise"
        hotels2 = self.analyzer._extract_hotel_names(text2)
        self.assertTrue(len(hotels2) >= 1)
        
        # Test case 3: No hotel names
        text3 = "There are no accommodations mentioned here."
        hotels3 = self.analyzer._extract_hotel_names(text3)
        self.assertEqual(len(hotels3), 0)
    
    def test_extract_room_types(self):
        """Test extracting room types from text."""
        # Test case 1: Simple room type
        text1 = "Room Type: Deluxe Suite"
        rooms1 = self.analyzer._extract_room_types(text1)
        self.assertIn("Deluxe Suite", rooms1)
        
        # Test case 2: Multiple room types
        text2 = "Room Type: Standard\nRoom Type: Family Suite"
        rooms2 = self.analyzer._extract_room_types(text2)
        self.assertEqual(len(rooms2), 2)
        
        # Test case 3: No room types
        text3 = "There are no room types mentioned here."
        rooms3 = self.analyzer._extract_room_types(text3)
        self.assertEqual(len(rooms3), 0)
    
    def test_extract_dates(self):
        """Test extracting dates from text."""
        # Test case 1: DD/MM/YYYY format
        text1 = "Period: 15/06/2024 - 30/06/2024"
        dates1 = self.analyzer._extract_dates(text1)
        self.assertEqual(len(dates1), 2)
        self.assertIn("2024-06-15", dates1)
        self.assertIn("2024-06-30", dates1)
        
        # Test case 2: YYYY-MM-DD format
        text2 = "Period: 2024-07-01 - 2024-07-15"
        dates2 = self.analyzer._extract_dates(text2)
        self.assertEqual(len(dates2), 2)
        self.assertIn("2024-07-01", dates2)
        self.assertIn("2024-07-15", dates2)
        
        # Test case 3: Written date format
        text3 = "From 1st January 2024 until 15th January 2024"
        dates3 = self.analyzer._extract_dates(text3)
        self.assertEqual(len(dates3), 2)
        self.assertIn("2024-01-01", dates3)
        self.assertIn("2024-01-15", dates3)
    
    def test_extract_markets(self):
        """Test extracting markets from text."""
        # Test case 1: Simple market
        text1 = "Market: UK"
        markets1 = self.analyzer._extract_markets(text1)
        self.assertIn("UK", markets1)
        
        # Test case 2: Multiple markets
        text2 = "Market: UK, DE, FR"
        markets2 = self.analyzer._extract_markets(text2)
        self.assertEqual(len(markets2), 3)
        self.assertIn("UK", markets2)
        self.assertIn("DE", markets2)
        self.assertIn("FR", markets2)
        
        # Test case 3: Special market "ALL"
        text3 = "Market: ALL"
        markets3 = self.analyzer._extract_markets(text3)
        self.assertIn("ALL", markets3)
    
    def test_extract_rules_from_text(self):
        """Test extracting rules from text."""
        # Test case: Complete text with hotel, room, dates, market and action
        text = """
        STOP SALE NOTIFICATION
        
        Hotel: Grand Plaza Resort
        Room Type: Deluxe Suite
        Period: 15/06/2024 - 30/06/2024
        Market: UK, DE
        
        Please stop sales for the above period.
        """
        
        rules = self.analyzer.extract_rules_from_text(text)
        self.assertTrue(len(rules) > 0)
        
        # Check the first rule
        rule = rules[0]
        self.assertEqual(rule['name'], "Grand Plaza Resort")
        self.assertEqual(rule['room_type'], "Deluxe Suite")
        self.assertEqual(rule['action'], "stop_sale")
        self.assertIn("UK", rule['market'])
    
    def test_analyze_text_file(self):
        """Test analyzing a text file."""
        content = """
        STOP SALE NOTIFICATION
        
        Hotel: Grand Plaza Resort
        Room Type: Deluxe Suite
        Period: 15/06/2024 - 30/06/2024
        Market: UK, DE
        
        Please stop sales for the above period.
        """
        
        file_path = self.create_temp_file(content, 'txt')
        result = self.analyzer.analyze_text(file_path)
        
        self.assertIn('hotels', result)
        self.assertTrue(len(result['hotels']) > 0)
        
        # Check the first rule
        rule = result['hotels'][0]
        self.assertEqual(rule['name'], "Grand Plaza Resort")
        self.assertEqual(rule['room_type'], "Deluxe Suite")
        self.assertEqual(rule['action'], "stop_sale")
    
    def test_analyze(self):
        """Test the main analyze method."""
        content = """
        OPEN SALE NOTIFICATION
        
        Hotel: Sunshine Resort
        Room Type: All Rooms
        Period: 01/07/2024 - 31/08/2024
        Market: ALL
        
        Please open sales for the above period.
        """
        
        file_path = self.create_temp_file(content, 'txt')
        result = self.analyzer.analyze(file_path)
        
        self.assertIn('hotels', result)
        self.assertTrue(len(result['hotels']) > 0)
        
        # Check the first rule
        rule = result['hotels'][0]
        self.assertEqual(rule['name'], "Sunshine Resort")
        self.assertEqual(rule['room_type'], "All Rooms")
        self.assertEqual(rule['action'], "open_sale")
        self.assertEqual(rule['market'], "ALL")

if __name__ == '__main__':
    unittest.main()
