from django.urls import path
from . import views

app_name = 'emails'

urlpatterns = [
    path('', views.email_list, name='email_list'),
    path('<int:email_id>/', views.email_detail, name='email_detail'),
    path('<int:email_id>/process/', views.process_email_with_ai, name='process_email_with_ai'),
    path('<int:email_id>/reanalyze/', views.reanalyze_email, name='reanalyze_email'),
    path('<int:email_id>/confirm-attachment-analysis/', views.confirm_attachment_analysis, name='confirm_attachment_analysis'),
    path('attachment/<int:attachment_id>/', views.email_attachment_view, name='email_attachment_view'),
    path('row/<int:row_id>/approve/', views.approve_row, name='approve_row'),
    path('row/<int:row_id>/reject/', views.reject_row, name='reject_row'),
    path('row/<int:row_id>/send-to-robot/', views.send_to_robot, name='send_to_robot'),
    path('row/<int:row_id>/match-hotel/', views.match_hotel, name='match_hotel'),
    path('row/<int:row_id>/match-room/', views.match_room, name='match_room'),
    path('row/<int:row_id>/smart-match/', views.smart_match, name='smart_match'),
    path('row/<int:row_id>/manual-mapping/', views.manual_mapping, name='manual_mapping'),
    path('webhook/robot-callback/', views.webhook_robot_callback, name='webhook_robot_callback'),
    path('row/<int:row_id>/confirm-match/', views.confirm_match_ajax, name='confirm_match_ajax'),
    path('row/<int:row_id>/select-alternative/', views.select_alternative_ajax, name='select_alternative_ajax'),
    path('row/<int:row_id>/mark-not-found/', views.mark_not_found_ajax, name='mark_not_found_ajax'),
    path('row/<int:row_id>/create-alias/', views.create_alias_ajax, name='create_alias_ajax'),
    # Row ID'si olmadan sadece otel ID'sine göre odaları getiren endpoint
    path('get_rooms_by_hotel/<int:hotel_id>/', views.get_rooms_by_hotel_ajax, name='get_rooms_by_hotel_ajax'),
    # Row ID'si ile birlikte otel ID'sine göre odaları ve önerileri getiren endpoint
    path('get_rooms_by_hotel/<int:hotel_id>/<int:row_id>/', views.get_rooms_by_hotel_ajax, name='get_rooms_by_hotel_ajax_with_row'),
    
    # Bulk action endpoints
    path('bulk_action/approve/', views.email_bulk_approve, name='email_bulk_approve'),
    path('bulk_action/reject/', views.email_bulk_reject, name='email_bulk_reject'),
    path('bulk_action/delete/', views.email_bulk_delete, name='email_bulk_delete'),
]
