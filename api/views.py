from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from emails.models import Email, EmailRow, UserLog, AIModel, Prompt, EmailAttachment, EmailHotelMatch
from core.models import AIPerformanceMetric
from hotels.models import Hotel, Room, Market
from .serializers import (
    EmailSerializer, EmailRowSerializer, HotelSerializer, 
    RoomSerializer, MarketSerializer, EmailAttachmentSerializer
)
import json
import logging
from django.db.models import Q
from difflib import SequenceMatcher
from django.shortcuts import render

# Set up logger
logger = logging.getLogger(__name__)

# Try to import the AI analyzer
try:
    from core.ai_analyzer import ClaudeAnalyzer
    AI_ANALYZER_AVAILABLE = True
    logger.info("ClaudeAnalyzer successfully imported")
except ImportError as e:
    logger.error(f"Failed to import ClaudeAnalyzer: {e}")
    AI_ANALYZER_AVAILABLE = False


def detect_keywords(email_content, email_subject=''):
    """
    Basic keyword detection for extracting information from emails when AI analysis fails
    
    Args:
        email_content: The email body content
        email_subject: Optional email subject for additional context
        
    Returns:
        List of dictionaries with extracted data
    """
    # For basic demonstration purposes
    full_content = f"{email_subject}\n\n{email_content}"
    email_lower = full_content.lower()
    
    # Try to detect hotel names
    hotel_names = []
    if "hilton" in email_lower:
        hotel_names.append("Hilton Hotel")
    if "marriott" in email_lower:
        hotel_names.append("Marriott Hotel")
    if "plaza" in email_lower:
        hotel_names.append("Plaza Hotel")
    if "sheraton" in email_lower:
        hotel_names.append("Sheraton Hotel")
    if "ramada" in email_lower:
        hotel_names.append("Ramada Hotel")
    
    # If no hotel names detected, use a default
    if not hotel_names:
        hotel_names = ["Detected Hotel"]
    
    # Try to detect room types
    room_types = []
    if "standard" in email_lower:
        room_types.append("Standard Room")
    if "deluxe" in email_lower:
        room_types.append("Deluxe Room")
    if "suite" in email_lower:
        room_types.append("Suite")
    if "family" in email_lower:
        room_types.append("Family Room")
    
    # If no room types detected, use a default
    if not room_types:
        room_types = ["All Room Types"]
    
    # Try to detect markets
    markets = []
    if "uk" in email_lower or "united kingdom" in email_lower:
        markets.append("UK")
    if "de" in email_lower or "germany" in email_lower:
        markets.append("DE")
    if "nl" in email_lower or "netherlands" in email_lower:
        markets.append("NL")
    
    # If no markets detected, use a default
    if not markets:
        markets = ["ALL"]
    
    # Try to detect sale type
    sale_type = "stop"
    if "open" in email_lower or "release" in email_lower:
        sale_type = "open"
    
    # Try to detect dates - basic detection for demonstration
    import re
    from datetime import datetime, timedelta
    
    date_patterns = [
        r'(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{2,4})',  # DD/MM/YYYY or DD-MM-YYYY
        r'(\d{4})[\/\.\-](\d{1,2})[\/\.\-](\d{1,2})'     # YYYY/MM/DD or YYYY-MM-DD
    ]
    
    dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, full_content)
        for match in matches:
            try:
                if len(match[2]) == 2:  # DD/MM/YY format
                    year = int("20" + match[2])
                else:
                    year = int(match[2])
                
                if len(match[0]) == 4:  # YYYY/MM/DD format
                    date_obj = datetime(int(match[0]), int(match[1]), int(match[2]))
                else:  # DD/MM/YYYY format
                    date_obj = datetime(year, int(match[1]), int(match[0]))
                
                dates.append(date_obj.strftime('%Y-%m-%d'))
            except:
                continue
    
    # Use default dates if none detected
    if len(dates) < 2:
        today = datetime.now()
        start_date = today.strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
    else:
        # Sort the dates and use the first and last
        dates.sort()
        start_date = dates[0]
        end_date = dates[-1]
    
    # Create rows for each combination
    rows = []
    for hotel_name in hotel_names:
        for room_type in room_types:
            for market in markets:
                row = {
                    'hotel_name': hotel_name,
                    'room_type': room_type,
                    'market': market,
                    'start_date': start_date,
                    'end_date': end_date,
                    'sale_type': sale_type
                }
                rows.append(row)
    
    return rows


class EmailListAPI(generics.ListAPIView):
    """
    API endpoint for listing emails
    """
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Get query parameters
        status = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        sort_order = self.request.query_params.get('sort', 'asc')  # Default to ascending (oldest first)
        
        # Base queryset
        queryset = Email.objects.all()
        
        # Apply filters
        if status:
            queryset = queryset.filter(status=status)
        
        if search:
            queryset = queryset.filter(subject__icontains=search)
        
        # Order by received date based on sort parameter
        if sort_order == 'desc':
            return queryset.order_by('-received_date')  # Newest first
        else:
            return queryset.order_by('received_date')   # Oldest first


class EmailDetailAPI(generics.RetrieveDestroyAPIView):
    """
    API endpoint for retrieving and deleting email details
    """
    queryset = Email.objects.all()
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]


class EmailRowListAPI(generics.ListAPIView):
    """
    API endpoint for listing email rows
    """
    serializer_class = EmailRowSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        email_id = self.kwargs['email_id']
        return EmailRow.objects.filter(email_id=email_id).order_by('id')


class EmailRowDetailAPI(generics.RetrieveAPIView):
    """
    API endpoint for retrieving email row details
    """
    queryset = EmailRow.objects.all()
    serializer_class = EmailRowSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def approve_row_api(request, row_id):
    """
    API endpoint for approving a row
    """
    row = get_object_or_404(EmailRow, id=row_id)
    
    # Only allow approving pending rows
    if row.status != 'pending':
        return Response(
            {'error': 'Only pending rows can be approved.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if hotel and room are matched
    if not row.juniper_hotel or not row.juniper_room:
        return Response(
            {'error': 'Cannot approve row without hotel and room matches.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update row status
    row.status = 'approved'
    row.processed_by = request.user
    row.processed_at = timezone.now()
    row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='approve_row',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Check if all rows are processed and update email status if needed
    if not row.email.rows.filter(status='pending').exists():
        row.email.status = 'approved'
        row.email.processed_by = request.user
        row.email.save()
    
    return Response({'status': 'success'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_to_robot_api(request, row_id):
    """
    API endpoint for sending a row to the RPA robot
    """
    row = get_object_or_404(EmailRow, id=row_id)
    
    # Only allow sending approved rows
    if row.status != 'approved':
        return Response(
            {'error': 'Only approved rows can be sent to the robot.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update row status
    row.status = 'sent_to_robot'
    row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='send_to_robot',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # TODO: Implement actual webhook call to RPA system
    # This would be implemented in a separate function or using a task queue
    
    return Response({'status': 'success'}, status=status.HTTP_200_OK)


class HotelListAPI(generics.ListAPIView):
    """
    API endpoint for listing hotels
    """
    serializer_class = HotelSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Get query parameters
        search = self.request.query_params.get('search')
        
        # Base queryset
        queryset = Hotel.objects.all()
        
        # Apply search filter if provided
        if search:
            queryset = queryset.filter(
                Q(juniper_hotel_name__icontains=search) |
                Q(juniper_code__icontains=search)
            )
        
        # Order by hotel name
        return queryset.order_by('juniper_hotel_name')


class HotelDetailAPI(generics.RetrieveAPIView):
    """
    API endpoint for retrieving hotel details
    """
    queryset = Hotel.objects.all()
    serializer_class = HotelSerializer
    permission_classes = [permissions.IsAuthenticated]


class RoomListAPI(generics.ListAPIView):
    """
    API endpoint for listing rooms
    """
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        hotel_id = self.kwargs['hotel_id']
        return Room.objects.filter(hotel_id=hotel_id).order_by('juniper_room_type')


class RoomDetailAPI(generics.RetrieveAPIView):
    """
    API endpoint for retrieving room details
    """
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]


class MarketListAPI(generics.ListAPIView):
    """
    API endpoint for listing markets
    """
    queryset = Market.objects.all().order_by('name')
    serializer_class = MarketSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def robot_callback(request):
    """
    API endpoint for RPA robot callback
    """
    try:
        data = json.loads(request.body)
        row_id = data.get('row_id')
        success = data.get('success', False)
        message = data.get('message', '')
        
        row = get_object_or_404(EmailRow, id=row_id)
        
        if success:
            row.status = 'robot_processed'
        else:
            row.status = 'error'
        
        row.save()
        
        # Log the action
        UserLog.objects.create(
            user=request.user,
            action_type='robot_callback',
            email=row.email,
            email_row=row,
            ip_address=request.META.get('REMOTE_ADDR'),
            details=message
        )
        
        return Response({'status': 'success'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def process_email(request):
    """
    API endpoint for processing a new email
    """
    try:
        data = json.loads(request.body)
        
        # Create new email
        email = Email.objects.create(
            subject=data.get('subject', ''),
            sender=data.get('sender', ''),
            recipient=data.get('recipient', ''),
            received_date=data.get('received_date', timezone.now()),
            message_id=data.get('message_id', ''),
            body_text=data.get('body_text', ''),
            body_html=data.get('body_html', ''),
            status='pending',
            has_attachments=bool(data.get('attachments', []))
        )
        
        # Process attachments if any
        attachments = data.get('attachments', [])
        for attachment in attachments:
            email.attachments.create(
                filename=attachment.get('filename', ''),
                content_type=attachment.get('content_type', ''),
                file=attachment.get('file', ''),
                size=attachment.get('size', 0)
            )
        
        # Process extracted rows if any
        rows = data.get('rows', [])
        for row in rows:
            email_row = EmailRow.objects.create(
                email=email,
                hotel_name=row.get('hotel_name', ''),
                room_type=row.get('room_type', ''),
                market=row.get('market', ''),
                start_date=row.get('start_date', timezone.now().date()),
                end_date=row.get('end_date', timezone.now().date()),
                sale_type=row.get('sale_type', 'stop'),
                status='pending',
                ai_extracted=True
            )
            
            # Try to match hotel and room
            hotel_name = row.get('hotel_name', '')
            room_type = row.get('room_type', '')
            
            # Simple exact match for now
            try:
                hotel = Hotel.objects.get(juniper_hotel_name__iexact=hotel_name)
                email_row.juniper_hotel = hotel
                
                try:
                    room = Room.objects.get(hotel=hotel, juniper_room_type__iexact=room_type)
                    email_row.juniper_room = room
                except Room.DoesNotExist:
                    pass
                
                email_row.save()
            
            except Hotel.DoesNotExist:
                pass
        
        return Response(
            {'status': 'success', 'email_id': email.id},
            status=status.HTTP_201_CREATED
        )
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def parse_email_content(request, *args, **kwargs):
    """
    API view to parse email content (body) using the unified ClaudeAnalyzer
    """
    if request.method == 'POST':
        data = request.data
        email_id = data.get('email_id')
        model_id = data.get('model_id')
        prompt_id = data.get('prompt_id')

        result = {
            'success': False, 'data': {'rows': [], 'raw_ai_response': None, 'error': None}, 
            'message': 'Processing failed', 'used_fallback': False
        }

        # Check if email already has rows (from body or attachment analysis)
        if email_id:
            try:
                email = Email.objects.get(pk=email_id)
                if email.rows.exists():
                    logger.info(f"Email ID {email_id} already has rows. Skipping body re-analysis via API.")
                    result.update({'success': True, 'message': 'Email already analyzed'})
                    return Response(result)
            except Email.DoesNotExist:
                logger.warning(f"Email ID {email_id} not found when checking for previous analysis.")

        # --- Use ClaudeAnalyzer for Body Analysis --- 
        try:
            active_model = AIModel.objects.filter(pk=model_id, active=True).first() if model_id else AIModel.objects.filter(active=True).first()
            # Use specific prompt if provided, otherwise analyzer uses its default (Unified)
            active_prompt_content = Prompt.objects.get(pk=prompt_id).content if prompt_id else None
            
            # Get email data from the model
            email_obj = Email.objects.get(pk=email_id)
            email_subject = email_obj.subject
            email_content = email_obj.body_text
            email_html = email_obj.body_html
            email_sender = email_obj.sender  # Get the sender email address
            
            if not active_model or not active_model.api_key:
                raise ValueError("Active AI model with API key not found.")
                
            analyzer = ClaudeAnalyzer(api_key=active_model.api_key, prompt=active_prompt_content)
            if not analyzer.claude_client:
                 raise ConnectionError("Failed to initialize Claude client.")
                 
            # Clean the email body (preferring HTML) - pass the sender email
            cleaned_body = analyzer.smart_clean_email_body(email_html, email_content, sender=email_sender)
            
            if not cleaned_body:
                 raise ValueError("Email body content is empty after cleaning.")
                 
            # Analyze the cleaned body content
            analysis_result = analyzer.analyze_content(cleaned_body, context_subject=email_subject)
            
            # Update result dict with analysis outcome
            result['data']['rows'] = analysis_result.get('rows', [])
            result['data']['raw_ai_response'] = analysis_result.get('raw_ai_response')
            result['data']['error'] = analysis_result.get('error')

            if analysis_result.get('error'):
                 result['success'] = False
                 result['message'] = f"AI analysis failed: {analysis_result['error']}"
                 # Return 400 to signal handler to check attachments
                 return Response(result, status=status.HTTP_400_BAD_REQUEST)
            elif not analysis_result.get('rows'):
                 result['success'] = False # Indicate no rows found
                 result['message'] = "AI analysis successful but found no rows in the email body."
                 # Return 400 to signal handler to check attachments
                 return Response(result, status=status.HTTP_400_BAD_REQUEST)
            else:
                 result['success'] = True
                 result['message'] = f"AI analysis successful, found {len(analysis_result['rows'])} rows in body."
                 # Return 200 OK as body analysis succeeded
                 return Response(result, status=status.HTTP_200_OK)
                 
        except (AIModel.DoesNotExist, Prompt.DoesNotExist, ValueError, ConnectionError) as e:
            logger.warning(f"Pre-analysis check failed for email ID {email_id}: {str(e)}")
            result['success'] = False
            result['message'] = f"Configuration error: {str(e)}"
            result['data']['error'] = str(e)
            # Return 400 to signal handler to check attachments
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Unexpected error in parse_email_content API for email ID {email_id}: {str(e)}", exc_info=True)
            result['success'] = False
            result['message'] = f'Unexpected error: {str(e)}'
            result['data']['error'] = str(e)
            # Return 500 for unexpected server errors
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    # Should not be reached if method is POST
    return Response({'error': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_rooms_by_hotel(request, hotel_id):
    """
    API endpoint to get rooms by hotel ID
    """
    try:
        hotel = Hotel.objects.get(pk=hotel_id)
        rooms = Room.objects.filter(hotel=hotel).order_by('juniper_room_type')
        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data)
    except Hotel.DoesNotExist:
        return Response(
            {'error': 'Hotel not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_hotels_api(request):
    """
    API endpoint for searching hotels with fuzzy matching for a specific email row
    """
    email_row_id = request.query_params.get('email_row')
    search_term = request.query_params.get('search', '')
    
    logger.info(f"Search hotels API called with email_row={email_row_id}, search={search_term}")
    
    if not email_row_id:
        logger.warning("Email row ID is required but not provided")
        return Response(
            {'error': 'Email row ID is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        email_row = EmailRow.objects.get(id=email_row_id)
        hotel_name = email_row.hotel_name
        
        logger.info(f"Found email row with hotel_name: {hotel_name}")
        
        # Get all hotels
        hotels = Hotel.objects.all()  # Removed is_active filter as it might not exist
        logger.info(f"Found {hotels.count()} hotels")
        
        # If search term is provided, filter hotels by it
        if search_term:
            hotels = hotels.filter(
                Q(juniper_hotel_name__icontains=search_term) |
                Q(juniper_code__icontains=search_term)
            )
            logger.info(f"Filtered to {hotels.count()} hotels matching search term: {search_term}")
        
        # Prepare response data with similarity scores
        result_hotels = []
        
        for hotel in hotels:
            # Calculate similarity between email row hotel name and juniper hotel name
            similarity = SequenceMatcher(None, hotel_name.lower(), hotel.juniper_hotel_name.lower()).ratio()
            
            # Word overlap score calculation - match individual words
            email_words = set(word.lower() for word in hotel_name.split() if len(word) > 2)
            juniper_words = set(word.lower() for word in hotel.juniper_hotel_name.split() if len(word) > 2)
            
            word_matches = 0
            for email_word in email_words:
                for juniper_word in juniper_words:
                    if SequenceMatcher(None, email_word, juniper_word).ratio() > 0.8:
                        word_matches += 1
                        break
            
            # Calculate word overlap score
            word_overlap_score = word_matches / len(email_words) if email_words else 0
            
            # Use the better of the two scores
            match_score = max(similarity, word_overlap_score)
            
            # Include all hotels for testing
            result_hotels.append({
                'id': hotel.id,
                'name': hotel.juniper_hotel_name,
                'code': hotel.juniper_code,
                'match_score': match_score
            })
        
        # Sort hotels by match score descending
        result_hotels.sort(key=lambda x: x['match_score'], reverse=True)
        
        logger.info(f"Returning {len(result_hotels)} hotels with scores")
        return Response({'hotels': result_hotels}, status=status.HTTP_200_OK)
    
    except EmailRow.DoesNotExist:
        logger.warning(f"Email row with ID {email_row_id} not found")
        return Response(
            {'error': f'Email row with ID {email_row_id} not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in search_hotels_api: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_hotel_room_types(request, hotel_id):
    """
    API endpoint for getting room types for a specific hotel
    """
    logger.info(f"Get hotel room types API called with hotel_id={hotel_id}")
    
    try:
        hotel = Hotel.objects.get(id=hotel_id)
        logger.info(f"Found hotel: {hotel.juniper_hotel_name}")
        
        # Print all field names for debugging
        logger.info(f"Hotel model fields: {[f.name for f in hotel._meta.fields]}")
        
        # Try with is_active filter first
        try:
            logger.info("Attempting to filter rooms with is_active=True")
            rooms = Room.objects.filter(hotel=hotel, is_active=True)
            logger.info(f"Found {rooms.count()} active rooms for hotel")
        except Exception as e:
            # Log specific exception
            logger.warning(f"Could not filter with is_active: {str(e)}")
            logger.info("Falling back to all rooms without is_active filter")
            rooms = Room.objects.filter(hotel=hotel)
            logger.info(f"Found {rooms.count()} rooms for hotel")
        
        # Print sample room data if available
        if rooms.exists():
            sample_room = rooms.first()
            logger.info(f"Sample room data: {[f.name for f in sample_room._meta.fields]}")
            logger.info(f"Sample room values: {sample_room.juniper_room_type}")
        else:
            logger.warning(f"No rooms found for hotel {hotel_id} ({hotel.juniper_hotel_name})")
        
        room_types = []
        for room in rooms:
            room_types.append({
                'id': room.id,
                'name': room.juniper_room_type
            })
        
        logger.info(f"Returning {len(room_types)} room types")
        return Response({'room_types': room_types}, status=status.HTTP_200_OK)
    
    except Hotel.DoesNotExist:
        logger.warning(f"Hotel with ID {hotel_id} not found")
        return Response(
            {'error': f'Hotel with ID {hotel_id} not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in get_hotel_room_types: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def manual_mapping_api(request):
    """
    API endpoint for manually mapping email row to juniper entities
    """
    try:
        data = request.data
        row_id = data.get('row_id')
        hotel_id = data.get('hotel_id')
        room_types = data.get('room_types', [])
        
        if not row_id or not hotel_id:
            return Response(
                {'error': 'Row ID and Hotel ID are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the email row
        row = get_object_or_404(EmailRow, id=row_id)
        
        # If hotel_id is 'not_found', clear the juniper_hotel and juniper_room
        if hotel_id == 'not_found':
            row.juniper_hotel = None
            row.juniper_room = None
            row.save()
            
            # Log the action
            UserLog.objects.create(
                user=request.user,
                action_type='manual_mapping',
                email=row.email,
                email_row=row,
                ip_address=request.META.get('REMOTE_ADDR'),
                details='Manually cleared hotel mapping'
            )
            
            return Response({'success': True}, status=status.HTTP_200_OK)
        
        # Get the hotel
        hotel = get_object_or_404(Hotel, id=hotel_id)
        
        # Update the row with hotel
        row.juniper_hotel = hotel
        
        # Handle room types
        if room_types:
            if 'all' in room_types:
                # Get the first room type for this hotel
                room = Room.objects.filter(hotel=hotel).first()
                if room:
                    row.juniper_room = room
            else:
                # Get the first selected room type
                room = get_object_or_404(Room, id=room_types[0])
                row.juniper_room = room
        else:
            row.juniper_room = None
        
        row.save()
        
        # Log the action
        UserLog.objects.create(
            user=request.user,
            action_type='manual_mapping',
            email=row.email,
            email_row=row,
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f'Manually mapped to hotel: {hotel.juniper_hotel_name}'
        )
        
        return Response({'success': True}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def get_email_status(request, email_id):
    """Get or update the status of an email by ID"""
    try:
        email = Email.objects.get(id=email_id)
        
        # GET request: Return current status
        if request.method == 'GET':
            # Get the proper status display from model property
            status_display = email.status_display
            
            # Log more details for debugging purposes
            logger.debug(f"Email {email_id} status API response: status={email.status}, status_display={status_display}")
            
            return Response({
                'status': email.status,
                'status_display': status_display
            })
        
        # POST request: Update status
        elif request.method == 'POST':
            # Get new status from request data
            try:
                data = json.loads(request.body)
                new_status = data.get('status')
                
                if not new_status:
                    return Response({'error': 'Status is required'}, status=400)
                
                # Validate status value
                valid_statuses = [status[0] for status in Email.STATUS_CHOICES]
                if new_status not in valid_statuses:
                    return Response({'error': f'Invalid status. Valid values are: {", ".join(valid_statuses)}'}, status=400)
                
                # Update email status
                email.status = new_status
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type='update_status',
                    email=email,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details=f"Updated email status to {new_status}"
                )
                
                # Get the proper status display from model property
                status_display = email.status_display
                
                logger.debug(f"Email {email_id} status updated: status={new_status}, status_display={status_display}")
                
                return Response({
                    'success': True,
                    'status': email.status,
                    'status_display': status_display
                })
                
            except json.JSONDecodeError:
                return Response({'error': 'Invalid JSON'}, status=400)
    
    except Email.DoesNotExist:
        return Response({'error': 'Email not found'}, status=404)
