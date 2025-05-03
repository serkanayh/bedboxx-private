from django.urls import path
from . import views

app_name = 'hotels'

urlpatterns = [
    path('', views.hotel_list, name='hotel_list'),
    path('<int:hotel_id>/', views.hotel_detail, name='hotel_detail'),
    path('<int:hotel_id>/rooms/', views.hotel_rooms, name='hotel_rooms'),
    path('rooms/<int:room_id>/', views.room_detail, name='room_detail'),
    path('markets/', views.market_list, name='market_list'),
    path('markets/<int:market_id>/', views.market_detail, name='market_detail'),
    path('import/', views.import_hotel_data, name='import_hotel_data'),
    path('create/', views.hotel_create, name='hotel_create'),
    path('<int:hotel_id>/delete/', views.hotel_delete, name='hotel_delete'),
    path('rooms/create/', views.room_create, name='room_create'),
    path('rooms/<int:room_id>/delete/', views.room_delete, name='room_delete'),
]
