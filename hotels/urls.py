from django.urls import path
from . import views

app_name = 'hotels'

urlpatterns = [
    path('hotel-list/', views.hotel_list, name='hotel_list'),
    path('hotel/<int:hotel_id>/', views.hotel_detail, name='hotel_detail'),
    path('room-create/', views.room_create, name='room_create'),
    path('room-delete/<int:room_id>/', views.room_delete, name='room_delete'),
    path('import-data/', views.import_hotel_data, name='import_hotel_data'),
    
    # Yeni otel portal URL'leri
    path('hotel-portal/create/', views.hotel_portal_create, name='hotel_portal_create'),
    path('hotel-portal/edit/<int:hotel_id>/', views.hotel_portal_edit, name='hotel_portal_edit'),
]
