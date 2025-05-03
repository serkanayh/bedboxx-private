from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Email API endpoints
    path('emails/', views.EmailListAPI.as_view(), name='email_list_api'),
    path('emails/<int:pk>/', views.EmailDetailAPI.as_view(), name='email_detail_api'),
    path('emails/<int:email_id>/rows/', views.EmailRowListAPI.as_view(), name='email_row_list_api'),
    path('email-rows/<int:pk>/', views.EmailRowDetailAPI.as_view(), name='email_row_detail_api'),
    path('email-rows/<int:row_id>/approve/', views.approve_row_api, name='approve_row_api'),
    path('email-rows/<int:row_id>/send-to-robot/', views.send_to_robot_api, name='send_to_robot_api'),
    
    # Hotel API endpoints
    path('hotels/', views.HotelListAPI.as_view(), name='hotel_list_api'),
    path('hotels/<int:pk>/', views.HotelDetailAPI.as_view(), name='hotel_detail_api'),
    path('hotels/<int:hotel_id>/rooms/', views.get_rooms_by_hotel, name='get_rooms_by_hotel'),
    path('rooms/<int:pk>/', views.RoomDetailAPI.as_view(), name='room_detail_api'),
    path('markets/', views.MarketListAPI.as_view(), name='market_list_api'),
    path('hotels/search/', views.search_hotels_api, name='search_hotels_api'),
    path('hotels/<int:hotel_id>/room_types/', views.get_hotel_room_types, name='get_hotel_room_types'),
    path('emails/rows/manual_mapping/', views.manual_mapping_api, name='manual_mapping_api'),
    
    # Webhook endpoint for RPA
    path('webhook/robot-callback/', views.robot_callback, name='robot_callback'),
    
    # Email processing endpoints
    path('process-email/', views.process_email, name='process_email'),
    path('parse-email-content/', views.parse_email_content, name='parse_email_content'),
]
