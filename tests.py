from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from emails.models import Email, EmailRow
from hotels.models import Hotel, Room, Market
import datetime

User = get_user_model()

class EmailListViewTest(TestCase):
    """Test case for the email list view"""
    
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com',
            role='agent'
        )
        
        # Create some test emails
        Email.objects.create(
            subject='Test Email 1',
            sender='sender1@example.com',
            recipient='recipient@example.com',
            received_date=datetime.datetime.now(),
            message_id='test1@example.com',
            body_text='This is test email 1',
            status='pending'
        )
        
        Email.objects.create(
            subject='Test Email 2',
            sender='sender2@example.com',
            recipient='recipient@example.com',
            received_date=datetime.datetime.now(),
            message_id='test2@example.com',
            body_text='This is test email 2',
            status='approved'
        )
        
        # Create a client
        self.client = Client()
    
    def test_email_list_view_requires_login(self):
        """Test that the email list view requires login"""
        response = self.client.get(reverse('emails:email_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_email_list_view_with_login(self):
        """Test that the email list view works with login"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('emails:email_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emails/email_list.html')
        
        # Check that the emails are in the context
        self.assertEqual(len(response.context['page_obj']), 2)
    
    def test_email_list_view_with_status_filter(self):
        """Test that the email list view filters by status"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('emails:email_list') + '?status=pending')
        self.assertEqual(response.status_code, 200)
        
        # Check that only pending emails are in the context
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].status, 'pending')
    
    def test_email_list_view_with_search(self):
        """Test that the email list view searches correctly"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('emails:email_list') + '?search=sender1')
        self.assertEqual(response.status_code, 200)
        
        # Check that only matching emails are in the context
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].sender, 'sender1@example.com')


class EmailDetailViewTest(TestCase):
    """Test case for the email detail view"""
    
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com',
            role='agent'
        )
        
        # Create a test hotel and room
        self.hotel = Hotel.objects.create(
            juniper_hotel_name='Test Hotel',
            juniper_code='TEST01'
        )
        
        self.room = Room.objects.create(
            hotel=self.hotel,
            juniper_room_type='Standard Room',
            room_code='STD01'
        )
        
        # Create a test market
        self.market = Market.objects.create(
            name='All Markets',
            juniper_code='ALL'
        )
        
        # Create a test email
        self.email = Email.objects.create(
            subject='Test Email',
            sender='sender@example.com',
            recipient='recipient@example.com',
            received_date=datetime.datetime.now(),
            message_id='test@example.com',
            body_text='This is a test email with stop sale information.',
            status='pending'
        )
        
        # Create a test email row
        self.email_row = EmailRow.objects.create(
            email=self.email,
            hotel_name='Test Hotel',
            room_type='Standard Room',
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=5),
            sale_type='stop',
            status='pending',
            ai_extracted=True
        )
        # Add market to email_row
        self.email_row.markets.add(self.market)
        
        # Create a client
        self.client = Client()
    
    def test_email_detail_view_requires_login(self):
        """Test that the email detail view requires login"""
        response = self.client.get(reverse('emails:email_detail', args=[self.email.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_email_detail_view_with_login(self):
        """Test that the email detail view works with login"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('emails:email_detail', args=[self.email.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emails/email_detail.html')
        
        # Check that the email is in the context
        self.assertEqual(response.context['email'], self.email)
        
        # Check that the email row is in the context
        self.assertEqual(len(response.context['email'].rows.all()), 1)
        self.assertEqual(response.context['email'].rows.all()[0], self.email_row)
    
    def test_approve_row(self):
        """Test approving a row"""
        # First, set the juniper hotel and room
        self.email_row.juniper_hotel = self.hotel
        self.email_row.save()
        self.email_row.juniper_rooms.add(self.room)
        
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('emails:approve_row', args=[self.email_row.id]))
        
        # Check that we're redirected back to the email detail page
        self.assertRedirects(response, reverse('emails:email_detail', args=[self.email.id]))
        
        # Check that the row status is now approved
        self.email_row.refresh_from_db()
        self.assertEqual(self.email_row.status, 'approved')
        
        # Check that the processed_by is set
        self.assertEqual(self.email_row.processed_by, self.user)


class DashboardViewTest(TestCase):
    """Test case for the dashboard view"""
    
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com',
            role='agent'
        )
        
        # Create a client
        self.client = Client()
    
    def test_dashboard_view_requires_login(self):
        """Test that the dashboard view requires login"""
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_dashboard_view_with_login(self):
        """Test that the dashboard view works with login"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/dashboard.html')
        
        # Check that the stats are in the context
        self.assertIn('stats', response.context)
        self.assertIn('processed_emails', response.context['stats'])
        self.assertIn('pending_emails', response.context['stats'])
        self.assertIn('approved_rows', response.context['stats'])
        self.assertIn('manual_edits', response.context['stats'])


class UserViewsTest(TestCase):
    """Test case for the user views"""
    
    def setUp(self):
        # Create a test admin user
        self.admin_user = User.objects.create_user(
            username='adminuser',
            password='adminpassword',
            email='admin@example.com',
            role='admin'
        )
        
        # Create a test regular user
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='regularpassword',
            email='regular@example.com',
            role='agent'
        )
        
        # Create a client
        self.client = Client()
    
    def test_login_view(self):
        """Test the login view"""
        # Test GET request
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        
        # Test successful login
        response = self.client.post(reverse('users:login'), {
            'username': 'adminuser',
            'password': 'adminpassword'
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        
        # Test failed login - this should redirect back to login page with a message
        client2 = Client()
        response = client2.post(reverse('users:login'), {
            'username': 'adminuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Stay on login page with error message
    
    def test_logout_view(self):
        """Test the logout view"""
        self.client.login(username='adminuser', password='adminpassword')
        response = self.client.get(reverse('users:logout'))
        self.assertRedirects(response, reverse('users:login'))
    
    def test_user_list_view_requires_admin(self):
        """Test that the user list view requires admin privileges"""
        # Login as regular user
        self.client.login(username='regularuser', password='regularpassword')
        response = self.client.get(reverse('users:user_list'))
        self.assertRedirects(response, reverse('core:dashboard'))  # Redirect to dashboard with error
        
        # Login as admin user
        self.client.login(username='adminuser', password='adminpassword')
        response = self.client.get(reverse('users:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/user_list.html')


class HotelViewsTest(TestCase):
    """Test case for the hotel views"""
    
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com',
            role='agent'
        )
        
        # Create some test hotels
        self.hotel1 = Hotel.objects.create(
            juniper_hotel_name='Test Hotel 1',
            juniper_code='TEST01'
        )
        
        self.hotel2 = Hotel.objects.create(
            juniper_hotel_name='Test Hotel 2',
            juniper_code='TEST02'
        )
        
        # Create some test rooms
        Room.objects.create(
            hotel=self.hotel1,
            juniper_room_type='Standard Room',
            room_code='STD01'
        )
        
        Room.objects.create(
            hotel=self.hotel1,
            juniper_room_type='Deluxe Room',
            room_code='DLX01'
        )
        
        # Create a client
        self.client = Client()
    
    def test_hotel_list_view_requires_login(self):
        """Test that the hotel list view requires login"""
        response = self.client.get(reverse('hotels:hotel_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_hotel_list_view_with_login(self):
        """Test that the hotel list view works with login"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('hotels:hotel_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotels/hotel_list.html')
        
        # Check that the hotels are in the context
        self.assertEqual(len(response.context['hotels']), 2)
    
    def test_hotel_detail_view(self):
        """Test the hotel detail view"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('hotels:hotel_detail', args=[self.hotel1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotels/hotel_detail.html')
        
        # Check that the hotel is in the context
        self.assertEqual(response.context['hotel'], self.hotel1)
        
        # Check that the rooms are in the context
        self.assertEqual(len(response.context['rooms']), 2)
    
    def test_hotel_rooms_view(self):
        """Test the hotel rooms view"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('hotels:hotel_rooms', args=[self.hotel1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotels/hotel_rooms.html')
        
        # Check that the hotel is in the context
        self.assertEqual(response.context['hotel'], self.hotel1)
        
        # Check that the rooms are in the context
        self.assertEqual(len(response.context['rooms']), 2)
