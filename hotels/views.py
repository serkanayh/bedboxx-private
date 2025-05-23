from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import Hotel, Room, Market, JuniperContractMarket, RoomTypeGroup, RoomTypeVariant
from .forms import HotelForm, RoomFormSet, ContractMarketFormSet
import csv
import io
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.urls import reverse

@login_required
def hotel_list(request):
    """
    View for displaying the list of hotels with filtering and pagination
    """
    # Get query parameters
    search = request.GET.get('search')
    
    # Base queryset
    hotels = Hotel.objects.all()
    
    # Apply filters
    if search:
        hotels = hotels.filter(
            Q(juniper_hotel_name__icontains=search) | 
            Q(juniper_code__icontains=search)
        )
    
    # Order by hotel name
    hotels = hotels.order_by('juniper_hotel_name')
    
    # Pagination
    paginator = Paginator(hotels, 20)  # Show 20 hotels per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'hotels': page_obj,
    }
    
    return render(request, 'hotels/hotel_list.html', context)

@login_required
def hotel_detail(request, hotel_id):
    """
    View for displaying the details of a specific hotel
    """
    hotel = get_object_or_404(Hotel, id=hotel_id)
    rooms = hotel.rooms.all().order_by('juniper_room_type')
    
    if request.method == 'POST':
        # Update hotel
        hotel.juniper_hotel_name = request.POST.get('juniper_hotel_name')
        hotel.juniper_code = request.POST.get('juniper_code')
        hotel.save()
        
        messages.success(request, 'Hotel updated successfully.')
        return redirect('hotels:hotel_detail', hotel_id=hotel.id)
    
    context = {
        'hotel': hotel,
        'rooms': rooms,
    }
    
    return render(request, 'hotels/hotel_detail.html', context)

@login_required
def hotel_rooms(request, hotel_id):
    """
    View for displaying the rooms of a specific hotel
    """
    hotel = get_object_or_404(Hotel, id=hotel_id)
    rooms = hotel.rooms.all().order_by('juniper_room_type')
    
    # Check if this is an API request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        room_data = []
        for room in rooms:
            room_data.append({
                'id': room.id,
                'juniper_room_type': room.juniper_room_type,
                'room_code': room.room_code,
            })
        return JsonResponse(room_data, safe=False)
    
    context = {
        'hotel': hotel,
        'rooms': rooms,
    }
    
    return render(request, 'hotels/hotel_rooms.html', context)

@login_required
def room_detail(request, room_id):
    """
    View for displaying the details of a specific room
    """
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        # Update room
        room.juniper_room_type = request.POST.get('juniper_room_type')
        room.room_code = request.POST.get('room_code')
        room.save()
        
        messages.success(request, 'Room updated successfully.')
        return redirect('hotels:room_detail', room_id=room.id)
    
    context = {
        'room': room,
    }
    
    return render(request, 'hotels/room_detail.html', context)

@login_required
def market_list(request):
    """
    View for displaying the list of markets
    """
    markets = Market.objects.all().order_by('juniper_market_name')
    
    context = {
        'markets': markets,
    }
    
    return render(request, 'hotels/market_list.html', context)

@login_required
def market_detail(request, market_id):
    """
    View for displaying the details of a specific market
    """
    market = get_object_or_404(Market, id=market_id)
    
    if request.method == 'POST':
        # Update market
        market.juniper_market_name = request.POST.get('juniper_market_name')
        market.mail_market_name = request.POST.get('mail_market_name')
        market.market_code = request.POST.get('market_code')
        market.save()
        
        messages.success(request, 'Market updated successfully.')
        return redirect('hotels:market_detail', market_id=market.id)
    
    context = {
        'market': market,
    }
    
    return render(request, 'hotels/market_detail.html', context)

@login_required
def import_hotel_data(request):
    """
    View for importing hotel data from CSV
    """
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('hotels:hotel_list')
    
    if request.method == 'POST':
        if 'hotels_file' in request.FILES:
            # Process hotels CSV
            csv_file = request.FILES['hotels_file']
            
            # Check if it's a CSV file
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file.')
                return redirect('hotels:import_hotel_data')
            
            # Read CSV file
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                next(reader)  # Skip header row
                
                hotels_added = 0
                hotels_updated = 0
                
                for row in reader:
                    if len(row) >= 2:
                        juniper_hotel_name = row[0].strip()
                        juniper_code = row[1].strip()
                        
                        # Check if hotel already exists
                        hotel, created = Hotel.objects.update_or_create(
                            juniper_code=juniper_code,
                            defaults={'juniper_hotel_name': juniper_hotel_name}
                        )
                        
                        if created:
                            hotels_added += 1
                        else:
                            hotels_updated += 1
                
                messages.success(request, f'Successfully imported hotels: {hotels_added} added, {hotels_updated} updated.')
            
            except Exception as e:
                messages.error(request, f'Error importing hotels: {str(e)}')
        
        elif 'rooms_file' in request.FILES:
            # Process rooms CSV
            csv_file = request.FILES['rooms_file']
            
            # Check if it's a CSV file
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file.')
                return redirect('hotels:import_hotel_data')
            
            # Read CSV file
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                next(reader)  # Skip header row
                
                rooms_added = 0
                rooms_updated = 0
                errors = 0
                
                for row in reader:
                    if len(row) >= 3:
                        juniper_code = row[0].strip()
                        juniper_room_type = row[1].strip()
                        room_code = row[2].strip()
                        
                        # Find the hotel
                        try:
                            hotel = Hotel.objects.get(juniper_code=juniper_code)
                            
                            # Check if room already exists
                            room, created = Room.objects.update_or_create(
                                hotel=hotel,
                                room_code=room_code,
                                defaults={'juniper_room_type': juniper_room_type}
                            )
                            
                            if created:
                                rooms_added += 1
                            else:
                                rooms_updated += 1
                        
                        except Hotel.DoesNotExist:
                            errors += 1
                
                if errors > 0:
                    messages.warning(request, f'Imported rooms with {errors} errors (hotel not found).')
                
                messages.success(request, f'Successfully imported rooms: {rooms_added} added, {rooms_updated} updated.')
            
            except Exception as e:
                messages.error(request, f'Error importing rooms: {str(e)}')
        
        elif 'markets_file' in request.FILES:
            # Process markets CSV
            csv_file = request.FILES['markets_file']
            
            # Check if it's a CSV file
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file.')
                return redirect('hotels:import_hotel_data')
            
            # Read CSV file
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                next(reader)  # Skip header row
                
                markets_added = 0
                markets_updated = 0
                
                for row in reader:
                    if len(row) >= 3:
                        juniper_market_name = row[0].strip()
                        mail_market_name = row[1].strip()
                        market_code = row[2].strip()
                        
                        # Check if market already exists
                        market, created = Market.objects.update_or_create(
                            market_code=market_code,
                            defaults={
                                'juniper_market_name': juniper_market_name,
                                'mail_market_name': mail_market_name
                            }
                        )
                        
                        if created:
                            markets_added += 1
                        else:
                            markets_updated += 1
                
                messages.success(request, f'Successfully imported markets: {markets_added} added, {markets_updated} updated.')
            
            except Exception as e:
                messages.error(request, f'Error importing markets: {str(e)}')
    
    context = {}
    
    return render(request, 'hotels/import_hotel_data.html', context)

@login_required
def hotel_create(request):
    """
    View for creating a new hotel
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to create hotels.')
        return redirect('hotels:hotel_list')
    
    if request.method == 'POST':
        juniper_hotel_name = request.POST.get('juniper_hotel_name')
        juniper_code = request.POST.get('juniper_code')
        
        if not juniper_hotel_name or not juniper_code:
            messages.error(request, 'Both hotel name and code are required.')
            return redirect('hotels:hotel_create')
        
        # Check if hotel code already exists
        if Hotel.objects.filter(juniper_code=juniper_code).exists():
            messages.error(request, f'Hotel with code {juniper_code} already exists.')
            return redirect('hotels:hotel_create')
        
        # Create hotel
        hotel = Hotel.objects.create(
            juniper_hotel_name=juniper_hotel_name,
            juniper_code=juniper_code
        )
        
        # Add "All Rooms" option
        Room.objects.create(
            hotel=hotel,
            juniper_room_type='All Rooms',
            room_code='ALL'
        )
        
        messages.success(request, f'Hotel "{juniper_hotel_name}" created successfully with "All Rooms" option.')
        return redirect('hotels:hotel_detail', hotel_id=hotel.id)
    
    context = {}
    return render(request, 'hotels/hotel_create.html', context)

@login_required
def hotel_delete(request, hotel_id):
    """
    View for deleting a hotel
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to delete hotels.')
        return redirect('hotels:hotel_list')
    
    hotel = get_object_or_404(Hotel, id=hotel_id)
    
    if request.method == 'POST':
        hotel_name = hotel.juniper_hotel_name
        hotel.delete()
        messages.success(request, f'Hotel "{hotel_name}" deleted successfully.')
        return redirect('hotels:hotel_list')
    
    context = {
        'hotel': hotel,
    }
    
    return render(request, 'hotels/hotel_delete.html', context)

@login_required
def room_create(request):
    """
    View for creating a new room
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to create rooms.')
        return redirect('hotels:hotel_list')
    
    hotels = Hotel.objects.all().order_by('juniper_hotel_name')
    
    if request.method == 'POST':
        hotel_id = request.POST.get('hotel')
        juniper_room_type = request.POST.get('juniper_room_type')
        room_code = request.POST.get('room_code')
        
        if not hotel_id or not juniper_room_type or not room_code:
            messages.error(request, 'All fields are required.')
            return redirect('hotels:room_create')
        
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            messages.error(request, 'Selected hotel does not exist.')
            return redirect('hotels:room_create')
        
        # Check if room code already exists for this hotel
        if Room.objects.filter(hotel=hotel, room_code=room_code).exists():
            messages.error(request, f'Room with code {room_code} already exists for this hotel.')
            return redirect('hotels:room_create')
        
        # Create room
        room = Room.objects.create(
            hotel=hotel,
            juniper_room_type=juniper_room_type,
            room_code=room_code
        )
        
        messages.success(request, f'Room "{juniper_room_type}" created successfully for {hotel.juniper_hotel_name}.')
        return redirect('hotels:hotel_rooms', hotel_id=hotel.id)
    
    context = {
        'hotels': hotels,
    }
    
    return render(request, 'hotels/room_create.html', context)

@login_required
def room_delete(request, room_id):
    """
    View for deleting a room
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to delete rooms.')
        return redirect('hotels:hotel_list')
    
    room = get_object_or_404(Room, id=room_id)
    hotel_id = room.hotel.id
    
    # Don't allow deleting "All Rooms"
    if room.juniper_room_type == 'All Rooms' and room.room_code == 'ALL':
        messages.error(request, 'Cannot delete the "All Rooms" option as it is required by the system.')
        return redirect('hotels:hotel_rooms', hotel_id=hotel_id)
    
    if request.method == 'POST':
        room_type = room.juniper_room_type
        room.delete()
        messages.success(request, f'Room "{room_type}" deleted successfully.')
        return redirect('hotels:hotel_rooms', hotel_id=hotel_id)
    
    context = {
        'room': room,
    }
    
    return render(request, 'hotels/room_delete.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def hotel_portal_create(request):
    """
    View for creating a new hotel with related data in a single form
    """
    if request.method == 'POST':
        hotel_form = HotelForm(request.POST)
        room_formset = RoomFormSet(request.POST, prefix='rooms')
        contract_formset = ContractMarketFormSet(request.POST, prefix='contracts')
        
        if hotel_form.is_valid() and room_formset.is_valid() and contract_formset.is_valid():
            try:
                with transaction.atomic():
                    # Save hotel
                    hotel = hotel_form.save()
                    
                    # Save rooms and create room type groups
                    rooms = room_formset.save(commit=False)
                    for room_form, room in zip(room_formset.forms, rooms):
                        if not room_form.cleaned_data.get('DELETE', False):
                            # Set hotel for each room
                            room.hotel = hotel
                            room.save()
                            
                            # Create or get room type group
                            group_name = room_form.cleaned_data.get('group_name')
                            if group_name:
                                group, created = RoomTypeGroup.objects.get_or_create(
                                    hotel=hotel,
                                    name=group_name
                                )
                                
                                # Create room type variant
                                RoomTypeVariant.objects.get_or_create(
                                    group=group,
                                    variant_room_name=room.juniper_room_type
                                )
                    
                    # Save contract-market relationships
                    for contract_form in contract_formset:
                        if contract_form.is_valid() and not contract_form.cleaned_data.get('DELETE', False):
                            contract_data = contract_form.cleaned_data
                            
                            # Create a contract for each selected market
                            for market in contract_data.get('markets', []):
                                JuniperContractMarket.objects.create(
                                    hotel=hotel,
                                    market=market,
                                    contract_name=contract_data.get('contract_name'),
                                    season=contract_data.get('season'),
                                    access=contract_data.get('access')
                                )
                    
                    messages.success(request, f"Otel {hotel.juniper_hotel_name} ve ilgili veriler başarıyla oluşturuldu.")
                    return redirect('admin:hotels_hotel_change', object_id=hotel.id)
            
            except Exception as e:
                messages.error(request, f"Hata oluştu: {str(e)}")
    else:
        hotel_form = HotelForm()
        room_formset = RoomFormSet(prefix='rooms')
        contract_formset = ContractMarketFormSet(prefix='contracts')
    
    return render(request, 'hotels/hotel_portal.html', {
        'hotel_form': hotel_form,
        'room_formset': room_formset,
        'contract_formset': contract_formset,
        'available_markets': Market.objects.all(),
        'title': 'Yeni Otel Ekle',
        'is_edit': False
    })

@login_required
@require_http_methods(["GET", "POST"])
def hotel_portal_edit(request, hotel_id):
    """
    View for editing an existing hotel with related data in a single form
    """
    hotel = get_object_or_404(Hotel, id=hotel_id)
    
    if request.method == 'POST':
        hotel_form = HotelForm(request.POST, instance=hotel)
        room_formset = RoomFormSet(request.POST, instance=hotel, prefix='rooms')
        
        # For contracts, we need custom handling since we're using a formset not directly tied to the hotel
        contract_formset = ContractMarketFormSet(request.POST, prefix='contracts')
        
        if hotel_form.is_valid() and room_formset.is_valid() and contract_formset.is_valid():
            try:
                with transaction.atomic():
                    # Save hotel
                    hotel = hotel_form.save()
                    
                    # Save rooms and create room type groups
                    rooms = room_formset.save(commit=False)
                    for room_form, room in zip(room_formset.forms, rooms):
                        if not room_form.cleaned_data.get('DELETE', False):
                            # Set hotel for each room
                            room.hotel = hotel
                            room.save()
                            
                            # Create or get room type group
                            group_name = room_form.cleaned_data.get('group_name')
                            if group_name:
                                group, created = RoomTypeGroup.objects.get_or_create(
                                    hotel=hotel,
                                    name=group_name
                                )
                                
                                # Create room type variant if it doesn't exist
                                RoomTypeVariant.objects.get_or_create(
                                    group=group,
                                    variant_room_name=room.juniper_room_type
                                )
                    
                    # Delete the forms marked for deletion
                    room_formset.save()
                    
                    # Handle contracts - first clear existing ones
                    if 'reset_contracts' in request.POST:
                        # If user checked "reset contracts" box, remove all existing contracts
                        JuniperContractMarket.objects.filter(hotel=hotel).delete()
                    
                    # Add new contracts from the formset
                    for contract_form in contract_formset:
                        if contract_form.is_valid() and not contract_form.cleaned_data.get('DELETE', False):
                            contract_data = contract_form.cleaned_data
                            
                            # Create a contract for each selected market
                            for market in contract_data.get('markets', []):
                                JuniperContractMarket.objects.get_or_create(
                                    hotel=hotel,
                                    market=market,
                                    contract_name=contract_data.get('contract_name'),
                                    season=contract_data.get('season'),
                                    defaults={'access': contract_data.get('access')}
                                )
                    
                    messages.success(request, f"Otel {hotel.juniper_hotel_name} ve ilgili veriler başarıyla güncellendi.")
                    return redirect('admin:hotels_hotel_change', object_id=hotel.id)
            
            except Exception as e:
                messages.error(request, f"Hata oluştu: {str(e)}")
    else:
        hotel_form = HotelForm(instance=hotel)
        
        # Her oda için grup bilgilerini içeren formset oluştur
        # Önce odaların grup bilgilerini toplayalım
        rooms_with_groups = []
        for room in hotel.rooms.all():
            # Bu oda için grup bilgisini ara
            room_group = None
            # İlgili RoomTypeVariant kaydı üzerinden grup bilgisini bulalım
            variant = RoomTypeVariant.objects.filter(variant_room_name=room.juniper_room_type, group__hotel=hotel).first()
            if variant:
                room_group = variant.group.name
            
            # Dikkat: group_name doğrudan modelde olmadığından initial data olarak eklemeliyiz
            rooms_with_groups.append({
                'group_name': room_group,
                'juniper_room_type': room.juniper_room_type,
                'room_code': room.room_code,
            })
        
        # Özel initial data ile formset oluştur
        room_formset = RoomFormSet(instance=hotel, prefix='rooms')
        
        # Her form için grup bilgilerini atayalım
        for i, form in enumerate(room_formset.forms):
            if i < len(rooms_with_groups) and rooms_with_groups[i]['group_name']:
                form.initial['group_name'] = rooms_with_groups[i]['group_name']
        
        # Pre-populate contract data
        existing_contracts = {}
        for contract in JuniperContractMarket.objects.filter(hotel=hotel).order_by('contract_name', 'season'):
            key = (contract.contract_name, contract.season)
            if key not in existing_contracts:
                existing_contracts[key] = {
                    'contract_name': contract.contract_name,
                    'season': contract.season,
                    'access': contract.access,
                    'markets': []
                }
            existing_contracts[key]['markets'].append(contract.market)
        
        # Initialize formset with existing contract data
        initial_contracts = []
        for contract_data in existing_contracts.values():
            initial_contracts.append({
                'contract_name': contract_data['contract_name'],
                'season': contract_data['season'],
                'access': contract_data['access'],
                'markets': [m.id for m in contract_data['markets']]
            })
        
        # If there are no contracts, provide empty forms
        if not initial_contracts:
            contract_formset = ContractMarketFormSet(prefix='contracts')
        else:
            contract_formset = ContractMarketFormSet(initial=initial_contracts, prefix='contracts')
    
    return render(request, 'hotels/hotel_portal.html', {
        'hotel_form': hotel_form,
        'room_formset': room_formset,
        'contract_formset': contract_formset,
        'available_markets': Market.objects.all(),
        'title': f'Otel Düzenle: {hotel.juniper_hotel_name}',
        'is_edit': True,
        'hotel': hotel
    })
