from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from .models import User
from emails.models import UserLog

def login_view(request):
    """
    View for user login
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Log the login
            UserLog.objects.create(
                user=user,
                action_type='login',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Update last login IP
            user.last_login_ip = request.META.get('REMOTE_ADDR')
            user.save(update_fields=['last_login_ip'])
            
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'users/login.html')

@login_required
def logout_view(request):
    """
    View for user logout
    """
    # Log the logout
    UserLog.objects.create(
        user=request.user,
        action_type='logout',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')

@login_required
def profile_view(request):
    """
    View for user profile
    """
    user = request.user
    
    if request.method == 'POST':
        # Update basic profile info
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        
        # Check if password is being changed
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password:
            if new_password == confirm_password:
                user.set_password(new_password)
                messages.success(request, 'Password updated successfully. Please log in again.')
                user.save()
                return redirect('users:login')
            else:
                messages.error(request, 'Passwords do not match.')
                return redirect('users:profile')
        
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('users:profile')
    
    # Get recent activity
    recent_activity = UserLog.objects.filter(user=user).order_by('-timestamp')[:10]
    
    context = {
        'user': user,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'users/profile.html', context)

@login_required
def user_list(request):
    """
    View for listing users (admin only)
    """
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('core:dashboard')
    
    # Get query parameters
    search = request.GET.get('search')
    role = request.GET.get('role')
    
    # Base queryset
    users = User.objects.all()
    
    # Apply filters
    if search:
        users = users.filter(
            Q(username__icontains=search) | 
            Q(first_name__icontains=search) | 
            Q(last_name__icontains=search) | 
            Q(email__icontains=search)
        )
    
    if role:
        users = users.filter(role=role)
    
    # Order by username
    users = users.order_by('username')
    
    # Pagination
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
    }
    
    return render(request, 'users/user_list.html', context)

@login_required
def user_detail(request, user_id):
    """
    View for user details (admin only)
    """
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('core:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    # Get recent activity
    recent_activity = UserLog.objects.filter(user=user).order_by('-timestamp')[:20]
    
    context = {
        'user_obj': user,  # Use user_obj to avoid conflict with request.user
        'recent_activity': recent_activity,
    }
    
    return render(request, 'users/user_detail.html', context)

@login_required
def create_user(request):
    """
    View for creating a new user (admin only)
    """
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')
        is_active = 'is_active' in request.POST
        is_staff = 'is_staff' in request.POST
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('users:create_user')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        user.role = role
        user.is_active = is_active
        user.is_staff = is_staff
        user.save()
        
        # Log the action
        UserLog.objects.create(
            user=request.user,
            action_type='create_user',
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f'Created user {username} with role {role}'
        )
        
        messages.success(request, f'User {username} created successfully.')
        return redirect('users:user_list')
    
    context = {}
    
    return render(request, 'users/create_user.html', context)

@login_required
def edit_user(request, user_id):
    """
    View for editing a user (admin only)
    """
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('core:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Update user info
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.role = request.POST.get('role')
        user.is_active = 'is_active' in request.POST
        user.is_staff = 'is_staff' in request.POST
        
        # Check if password is being changed
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        user.save()
        
        # Log the action
        UserLog.objects.create(
            user=request.user,
            action_type='edit_user',
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f'Edited user {user.username}'
        )
        
        messages.success(request, f'User {user.username} updated successfully.')
        return redirect('users:user_list')
    
    context = {
        'user_obj': user,  # Use user_obj to avoid conflict with request.user
    }
    
    return render(request, 'users/edit_user.html', context)

@login_required
def toggle_user_active(request, user_id):
    """
    View for toggling user active status (admin only)
    """
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('core:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    # Don't allow deactivating yourself
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('users:user_list')
    
    # Toggle active status
    user.is_active = not user.is_active
    user.save()
    
    # Log the action
    action = 'activated' if user.is_active else 'deactivated'
    UserLog.objects.create(
        user=request.user,
        action_type='toggle_user_active',
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f'{action} user {user.username}'
    )
    
    messages.success(request, f'User {user.username} {action} successfully.')
    return redirect('users:user_list')
