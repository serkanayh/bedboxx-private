INSTALLED_APPS = [
    # ... existing apps ...
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'django_filters',
    'corsheaders',
    'django_celery_results',
    'django_celery_beat',
    # Local apps
    'emails.apps.EmailsConfig',  # Explicit AppConfig
    'core',
    'api', # Added api app
] 