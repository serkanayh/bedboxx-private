from django.urls import path
from . import views
from .bulk_actions import bulk_action

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
    path('row/<int:row_id>/reject-hotel-not-found/', views.reject_row_hotel_not_found, name='reject_row_hotel_not_found'),
    path('row/<int:row_id>/reject-room-not-found/', views.reject_row_room_not_found, name='reject_row_room_not_found'),
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
    # Manuel kural ekleme path'leri
    path('add-manual-rule/', views.add_manual_rule, name='add_manual_rule'),
    path('add-manual-rule/<int:email_id>/', views.add_manual_rule, name='add_manual_rule_to_email'),
    # Row ID'si olmadan sadece otel ID'sine göre odaları getiren endpoint
    path('get_rooms_by_hotel/<int:hotel_id>/', views.get_rooms_by_hotel, name='get_rooms_by_hotel'),
    path('get_contracts_by_hotel/<int:hotel_id>/', views.get_contracts_by_hotel, name='get_contracts_by_hotel'),
    # Row ID'si ile birlikte otel ID'sine göre odaları ve önerileri getiren endpoint
    path('get_rooms_by_hotel/<int:hotel_id>/<int:row_id>/', views.get_rooms_by_hotel_ajax, name='get_rooms_by_hotel_ajax_with_row'),
    
    # Bulk action endpoints
    path('bulk-action/', bulk_action, name='bulk_action'),
    path('bulk_action/approve/', views.email_bulk_approve, name='email_bulk_approve'),
    path('bulk_action/reject/', views.email_bulk_reject, name='email_bulk_reject'),
    path('bulk_action/reject-hotel-not-found/', views.email_bulk_reject_hotel_not_found, name='email_bulk_reject_hotel_not_found'),
    path('bulk_action/reject-room-not-found/', views.email_bulk_reject_room_not_found, name='email_bulk_reject_room_not_found'),
    path('bulk_action/delete/', views.email_bulk_delete, name='email_bulk_delete'),
    
    # Bulk actions for rows (rules)
    path('bulk_action_rows/<str:action>/', views.bulk_action_rows, name='bulk_action_rows'),
    
    # Single email approve/reject
    path('<int:email_id>/approve/', views.approve_email, name='approve_email'),
    path('<int:email_id>/reject/', views.reject_email, name='reject_email'),
    path('<int:email_id>/reject-hotel-not-found/', views.reject_email_hotel_not_found, name='reject_email_hotel_not_found'),
    path('<int:email_id>/reject-room-not-found/', views.reject_email_room_not_found, name='reject_email_room_not_found'),
    
    # Mark as processed in Juniper
    path('<int:email_id>/mark-juniper-manual/', views.mark_email_juniper_manual, name='mark_email_juniper_manual'),
    path('<int:email_id>/mark-juniper-robot/', views.mark_email_juniper_robot, name='mark_email_juniper_robot'),
    
    # AI suggestions
    path('apply_suggestion/<int:row_id>/', views.apply_suggestion, name='apply_suggestion'),
    
    # Real-time email notification API endpoint
    path('api/check-new-emails/', views.check_new_emails_api, name='check_new_emails_api'),
    
    # Attachment download
    path('attachment/<int:attachment_id>/download/', views.download_attachment, name='download_attachment'),
    
    # Robot JSON export endpoint
    path('export_rules_for_robot/<int:email_id>/', views.export_rules_for_robot, name='export_rules_for_robot'),
    
    path('email/<int:email_id>/analyze-attachments/', views.analyze_email_attachments, name='analyze_email_attachments'),
    path('attachment/<int:attachment_id>/content/', views.get_attachment_content, name='get_attachment_content'),
]
