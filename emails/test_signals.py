from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging
from rest_framework.test import APIClient
from .models import Email, AIModel, Prompt
from users.models import User

logger = logging.getLogger(__name__)

# Manually connect the signal
def connect_signals():
    print("Manually connecting Email signals")
    post_save.connect(auto_analyze_email, sender=Email)
    
    # Verify connection
    print(f"Signal connected: {auto_analyze_email in post_save._live_receivers(Email)}")
    
@receiver(post_save, sender=Email)
def auto_analyze_email(sender, instance, created, **kwargs):
    """
    Signal to automatically analyze new emails when they are created
    """
    print(f"Signal triggered for email {instance.id} (created={created})")
    
    # Only analyze newly created emails that are in pending status and don't have rows yet
    if created and instance.status == 'pending' and not instance.rows.exists():
        logger.info(f"Auto-analyzing email: {instance.id} - {instance.subject}")
        print(f"Auto-analyzing email: {instance.id} - {instance.subject}")
        
        try:
            # Create a client for API calls and authenticate it
            client = APIClient()
            
            # Get a superuser for authentication (first superuser found)
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                logger.error("No superuser found for API authentication in auto_analyze_email signal")
                print("No superuser found for API authentication")
                return
                
            client.force_authenticate(user=superuser)
            
            # Get active AI model and prompt
            active_model = AIModel.objects.filter(active=True).first()
            active_prompt = Prompt.objects.filter(active=True).first()
            
            if active_model and active_prompt:
                print(f"Found active model: {active_model.name} and active prompt: {active_prompt.title}")
                
                # Prepare payload
                payload = {
                    'email_content': instance.body_text,
                    'email_subject': instance.subject,
                    'email_html': instance.body_html,
                    'email_id': instance.id,
                    'model_id': active_model.id,
                    'prompt_id': active_prompt.id,
                }
                
                # Call API endpoint for email analysis
                print(f"Calling API with payload for email {instance.id}")
                response = client.post('/api/parse-email-content/', payload, format='json')
                
                if response.status_code == 200:
                    print(f"Successfully auto-analyzed email {instance.id}")
                    logger.info(f"Successfully auto-analyzed email {instance.id}")
                    # The rows are created by the API endpoint
                else:
                    print(f"Failed to auto-analyze email {instance.id}. Response: {response.content}")
                    logger.error(f"Failed to auto-analyze email {instance.id}. Response: {response.content}")
            else:
                print(f"Auto-analysis skipped for email {instance.id} - No active AI model or prompt found")
                logger.warning(f"Auto-analysis skipped for email {instance.id} - No active AI model or prompt found")
                
        except Exception as e:
            print(f"Error during auto-analysis of email {instance.id}: {str(e)}")
            logger.error(f"Error during auto-analysis of email {instance.id}: {str(e)}")

# Connect signals
connect_signals() 