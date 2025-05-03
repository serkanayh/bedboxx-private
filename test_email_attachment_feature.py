import os
import sys
import unittest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add project directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the necessary modules
from core.ai.attachment_analyzer import AttachmentAnalyzer

# Mock Django models and functions
class MockEmail:
    def __init__(self, id=1, subject="Test Email", sender="test@example.com", 
                 body_text="Test body", has_attachments=True):
        self.id = id
        self.subject = subject
        self.sender = sender
        self.body_text = body_text
        self.has_attachments = has_attachments
        self.attachments = []
        self.rows = []
        self.status = "pending"
        self.processed_by = None
        
    def save(self):
        pass

class MockAttachment:
    def __init__(self, id=1, filename="test.pdf", content_type="application/pdf", 
                 file_path="/tmp/test.pdf", size=1024):
        self.id = id
        self.filename = filename
        self.content_type = content_type
        self.file = MagicMock()
        self.file.path = file_path
        self.size = size

class MockEmailRow:
    def __init__(self, id=1, email=None, hotel_name="Test Hotel", room_type="Standard Room",
                 market="UK", start_date=None, end_date=None, sale_type="stop",
                 status="pending", ai_extracted=True, from_attachment=True):
        self.id = id
        self.email = email
        self.hotel_name = hotel_name
        self.room_type = room_type
        self.market = market
        self.start_date = start_date or datetime.now().date()
        self.end_date = end_date or (datetime.now() + timedelta(days=7)).date()
        self.sale_type = sale_type
        self.status = status
        self.ai_extracted = ai_extracted
        self.from_attachment = from_attachment
        self.juniper_hotel = None
        self.juniper_room = None
        self.processed_by = None
        self.processed_at = None
        
    def save(self):
        pass

class MockHotel:
    def __init__(self, id=1, juniper_hotel_name="Test Hotel", juniper_code="TH001"):
        self.id = id
        self.juniper_hotel_name = juniper_hotel_name
        self.juniper_code = juniper_code

class MockRoom:
    def __init__(self, id=1, hotel=None, juniper_room_type="Standard Room"):
        self.id = id
        self.hotel = hotel
        self.juniper_room_type = juniper_room_type

class TestEmailAttachmentFeature(unittest.TestCase):
    """Test cases for the email attachment analysis feature."""
    
    def setUp(self):
        """Set up the test environment."""
        self.attachment_analyzer = AttachmentAnalyzer()
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
    
    def test_process_email_attachments(self):
        """Test processing email attachments."""
        # Create a mock email with attachments
        email = MockEmail()
        
        # Create a temporary text file with stop sale information
        content = """
        STOP SALE NOTIFICATION
        
        Hotel: Grand Plaza Resort
        Room Type: Deluxe Suite
        Period: 15/06/2024 - 30/06/2024
        Market: UK, DE
        
        Please stop sales for the above period.
        """
        
        file_path = self.create_temp_file(content, 'txt')
        
        # Create a mock attachment
        attachment = MockAttachment(file_path=file_path)
        email.attachments.append(attachment)
        
        # Mock the EmailRow.objects.create method
        with patch('project.emails.views.EmailRow.objects.create', return_value=MockEmailRow()) as mock_create:
            # Import the process_email_attachments function
            from emails.views import process_email_attachments
            
            # Call the function
            result = process_email_attachments(email, None)
            
            # Check that the function returned True
            self.assertTrue(result)
            
            # Check that EmailRow.objects.create was called
            mock_create.assert_called()
            
            # Check that the email status was updated
            self.assertEqual(email.status, "processed")
    
    def test_confirm_attachment_analysis(self):
        """Test confirming attachment analysis results."""
        # Create a mock email with attachment rows
        email = MockEmail()
        
        # Create mock attachment rows
        row1 = MockEmailRow(id=1, email=email)
        row2 = MockEmailRow(id=2, email=email)
        email.rows.append(row1)
        email.rows.append(row2)
        
        # Mock the request object
        request = MagicMock()
        request.method = 'POST'
        request.POST.getlist.return_value = [1]  # Only select row1
        request.user = MagicMock()
        request.META.get.return_value = '127.0.0.1'
        
        # Mock the get_object_or_404 function
        with patch('django.shortcuts.get_object_or_404', return_value=email) as mock_get:
            # Mock the EmailRow.objects.filter method
            with patch('project.emails.views.EmailRow.objects.filter') as mock_filter:
                # Mock the filter().exclude().delete() chain
                mock_filter.return_value.exclude.return_value.delete.return_value = None
                
                # Mock the filter(id__in=[1]) to return a queryset with row1
                mock_queryset = MagicMock()
                mock_queryset.__iter__.return_value = [row1]
                mock_filter.return_value.filter.return_value = mock_queryset
                
                # Mock the UserLog.objects.create method
                with patch('project.emails.views.UserLog.objects.create') as mock_log:
                    # Import the confirm_attachment_analysis function
                    from emails.views import confirm_attachment_analysis
                    
                    # Call the function
                    response = confirm_attachment_analysis(request, email.id)
                    
                    # Check that get_object_or_404 was called with the correct arguments
                    mock_get.assert_called_with(email.__class__, id=email.id)
                    
                    # Check that EmailRow.objects.filter was called
                    mock_filter.assert_called()
                    
                    # Check that UserLog.objects.create was called
                    mock_log.assert_called()
                    
                    # Check that the row status was updated
                    self.assertEqual(row1.status, "pending")
                    
                    # Check that the email status was updated
                    self.assertEqual(email.status, "processed")
    
    def test_manual_mapping(self):
        """Test manually mapping email row data."""
        # Create a mock email
        email = MockEmail()
        
        # Create a mock row
        row = MockEmailRow(id=1, email=email)
        
        # Create a mock hotel and room
        hotel = MockHotel()
        room = MockRoom(hotel=hotel)
        
        # Mock the request object
        request = MagicMock()
        request.method = 'POST'
        request.POST.get.side_effect = lambda key, default=None: {
            'hotel_id': hotel.id,
            'market_id': 1,
            'start_date': '2024-06-15',
            'end_date': '2024-06-30',
            'sale_type': 'stop',
        }.get(key, default)
        request.POST.getlist.return_value = [room.id]
        request.user = MagicMock()
        request.META.get.return_value = '127.0.0.1'
        
        # Mock the get_object_or_404 function to return the row
        with patch('django.shortcuts.get_object_or_404', side_effect=[row]) as mock_get:
            # Mock the Hotel.objects.get method to return the hotel
            with patch('project.emails.views.Hotel.objects.get', return_value=hotel) as mock_hotel_get:
                # Mock the Market.objects.get method
                with patch('project.emails.views.Market.objects.get', return_value=MagicMock()) as mock_market_get:
                    # Mock the Room.objects.get method to return the room
                    with patch('project.emails.views.Room.objects.get', return_value=room) as mock_room_get:
                        # Mock the UserLog.objects.create method
                        with patch('project.emails.views.UserLog.objects.create') as mock_log:
                            # Import the manual_mapping function
                            from emails.views import manual_mapping
                            
                            # Call the function
                            response = manual_mapping(request, row.id)
                            
                            # Check that get_object_or_404 was called with the correct arguments
                            mock_get.assert_called_with(row.__class__, id=row.id)
                            
                            # Check that Hotel.objects.get was called
                            mock_hotel_get.assert_called()
                            
                            # Check that Market.objects.get was called
                            mock_market_get.assert_called()
                            
                            # Check that Room.objects.get was called
                            mock_room_get.assert_called()
                            
                            # Check that UserLog.objects.create was called
                            mock_log.assert_called()
                            
                            # Check that the row was updated
                            self.assertEqual(row.juniper_hotel, hotel)
                            self.assertEqual(row.juniper_room, room)
                            self.assertEqual(row.hotel_name, hotel.juniper_hotel_name)
                            self.assertEqual(row.room_type, room.juniper_room_type)

if __name__ == '__main__':
    unittest.main()
