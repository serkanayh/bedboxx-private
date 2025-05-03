import os
import django
import logging

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

from emails.models import Email
from emails.signals import auto_analyze_email
from django.db.models.signals import post_save

# Configure logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if the signal is connected
connected_receivers = post_save._live_receivers(Email)
print(f"Signal connected receivers: {connected_receivers}")
print(f"Is auto_analyze_email connected: {auto_analyze_email in connected_receivers}")

# Get count of active models and prompts
from emails.models import AIModel, Prompt
active_models = AIModel.objects.filter(active=True).count()
active_prompts = Prompt.objects.filter(active=True).count()

print(f"Active AI Models: {active_models}")
print(f"Active Prompts: {active_prompts}")

print("Signal test completed.") 