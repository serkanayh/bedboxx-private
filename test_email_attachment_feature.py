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
        email = Mock(spec=Email)
        email.id = 1
        user = Mock(spec=User)
        user.id = 1
        
        # Mock a list of attachments
        attachment1 = Mock(spec=EmailAttachment)
        attachment1.id = 1
        attachment1.file.path = 'test.pdf'
        attachment1.filename = 'test.pdf'
        
        email.attachments.all.return_value = [attachment1]
        
        # Mock the AttachmentAnalyzer
        with patch('Bedboxx_stopsale.emails.views.AttachmentAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.analyze_attachment.return_value = {
                'extracted_text': 'Test text',
                'extracted_data': [
                    {
                        'hotel_name': 'Test Hotel',
                        'room_type': 'Standard Room',
                        'market': 'ALL',
                        'start_date': '2023-01-01',
                        'end_date': '2023-01-10',
                        'sale_type': 'stop'
                    }
                ]
            }
            
            # Mock EmailRow.objects.create
            with patch('Bedboxx_stopsale.emails.views.EmailRow.objects.create', return_value=MockEmailRow()) as mock_create:
            # Call the function
                from emails.views import process_email_attachments
                result = process_email_attachments(email, user)
            
                # Verify that the analyzer was called
                mock_analyzer.analyze_attachment.assert_called_once_with(attachment1.file.path)
            
                # Verify that EmailRow was created
                mock_create.assert_called_once()
            
                # Verify the result
                self.assertTrue(result)
    
    def test_confirm_attachment_analysis(self):
        """Test confirming attachment analysis results."""
        # Mock request
        request = Mock()
        request.method = 'POST'
        request.POST = {'confirm': True}
        
        # Mock email
        email = Mock(spec=Email)
        email.id = 1
        email.attachment_analysis_results = {
            '1': {
                'extracted_text': 'Test text',
                'extracted_data': [
                    {
                        'hotel_name': 'Test Hotel',
                        'room_type': 'Standard Room',
                        'market': 'ALL',
                        'start_date': '2023-01-01',
                        'end_date': '2023-01-10',
                        'sale_type': 'stop'
                    }
                ]
            }
        }
        
        with patch('Bedboxx_stopsale.emails.views.EmailRow.objects.filter') as mock_filter:
            mock_filter.return_value.exists.return_value = False
            
            # Mock get_object_or_404
            with patch('Bedboxx_stopsale.emails.views.get_object_or_404', return_value=email):
                # Mock EmailRow.objects.create
                with patch('Bedboxx_stopsale.emails.views.EmailRow.objects.create', return_value=MockEmailRow()) as mock_create:
                    # Mock messages
                    with patch('Bedboxx_stopsale.emails.views.messages') as mock_messages:
                        # Mock redirect
                        with patch('Bedboxx_stopsale.emails.views.redirect') as mock_redirect:
                            # Call the function
                    from emails.views import confirm_attachment_analysis
                            confirm_attachment_analysis(request, email.id)
                    
                            # Verify that EmailRow was created
                            mock_create.assert_called_once()
                    
                            # Verify that messages.success was called
                            mock_messages.success.assert_called_once()
                    
                            # Verify that redirect was called with the correct args
                            mock_redirect.assert_called_once()
    
    def test_manual_mapping(self):
        """Test manually mapping email row data."""
        # Mock request
        request = Mock()
        request.method = 'POST'
        request.POST = {
            'hotel_id': '1',
            'room_ids': ['2'],
            'start_date': '2023-01-01',
            'end_date': '2023-01-10',
            'market': 'ALL',
            'sale_type': 'stop'
        }
        
        # Mock email row
        row = Mock(spec=EmailRow)
        row.id = 1
        row.email_id = 2
        
        # Mock hotel and room
        hotel = Mock(spec=Hotel)
        hotel.id = 1
        hotel.juniper_hotel_name = 'Test Hotel'
        
        room = Mock(spec=Room)
        room.id = 2
        room.juniper_room_type = 'Standard Room'
        
        with patch('Bedboxx_stopsale.emails.views.Hotel.objects.get', return_value=hotel) as mock_hotel_get:
            with patch('Bedboxx_stopsale.emails.views.Room.objects.filter') as mock_room_filter:
                mock_room_filter.return_value = [room]
                
                # Mock get_object_or_404
                with patch('Bedboxx_stopsale.emails.views.get_object_or_404', return_value=row):
                    # Mock messages
                    with patch('Bedboxx_stopsale.emails.views.messages') as mock_messages:
                        # Mock redirect
                        with patch('Bedboxx_stopsale.emails.views.redirect') as mock_redirect:
                            # Call the function
                            from emails.views import manual_mapping
                            manual_mapping(request, row.id)
                            
                            # Verify that the hotel and room were set
                            self.assertEqual(row.juniper_hotel, hotel)
                            self.assertEqual(list(row.juniper_rooms.add.call_args)[0][0], room)
                            
                            # Verify that messages.success was called
                            mock_messages.success.assert_called_once()
                            
                            # Verify that redirect was called with the correct args
                            mock_redirect.assert_called_once()

if __name__ == '__main__':
    unittest.main()
