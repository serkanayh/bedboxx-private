from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from core.views import serve_pdf
from django.conf import settings
from django.conf.urls.static import static

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ai-performance/', views.ai_performance, name='ai_performance'),
    path('ai-models/', views.ai_model_list, name='ai_model_list'),
    path('ai-models/create/', views.ai_model_create, name='ai_model_create'),
    path('ai-models/<int:model_id>/', views.ai_model_detail, name='ai_model_detail'),
    path('ai-models/<int:model_id>/delete/', views.ai_model_delete, name='ai_model_delete'),
    path('prompts/', views.prompt_list, name='prompt_list'),
    path('prompts/create/', views.prompt_create, name='prompt_create'),
    path('prompts/<int:prompt_id>/', views.prompt_detail, name='prompt_detail'),
    path('prompts/<int:prompt_id>/delete/', views.prompt_delete, name='prompt_delete'),
    path('regex-rules/', views.regex_rule_list, name='regex_rule_list'),
    path('regex-rules/create/', views.regex_rule_create, name='regex_rule_create'),
    path('regex-rules/<int:rule_id>/', views.regex_rule_detail, name='regex_rule_detail'),
    path('regex-rules/<int:rule_id>/delete/', views.regex_rule_delete, name='regex_rule_delete'),
    path('regex-rules/bulk-action/', views.regex_rule_bulk_action, name='regex_rule_bulk_action'),
    path('email-filters/', views.email_filter_list, name='email_filter_list'),
    path('email-filters/create/', views.email_filter_create, name='email_filter_create'),
    path('email-filters/<int:filter_id>/', views.email_filter_detail, name='email_filter_detail'),
    path('email-filters/<int:filter_id>/delete/', views.email_filter_delete, name='email_filter_delete'),
    path('webhook-logs/', views.webhook_log_list, name='webhook_log_list'),
    path('user-logs/', views.user_log_list, name='user_log_list'),
    path('email-config/', views.email_config, name='email_config'),
    path('list-folders/', views.list_folders, name='list_folders'),
    path('ai-test/', views.ai_test, name='ai_test'),
    
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    
    # Include users URLs
    path('users/', include('users.urls')),
    path('pdf/<str:filename>/', serve_pdf, name='serve_pdf'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
