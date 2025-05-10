from django.core.management.base import BaseCommand
from emails.models import Prompt
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Updates Claude AI prompt to prevent inventing dates when none are found in the content'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force create new prompt even if it already exists',
        )
    
    def handle(self, *args, **options):
        # New improved prompt that prevents date invention
        new_prompt_title = "Claude_Prompt_NoInvention"
        new_prompt_content = """
You are an AI analyzing email content to extract hotel stop/open sale rules.
The user will provide the email content structured like this:
SUBJECT: <Email Subject Here>
BODY:
<Cleaned Email Body Here>

Your primary goal is to return a JSON list of rule objects based on the SUBJECT and BODY provided.

**EXTREMELY IMPORTANT RULES FOR HOTEL NAME:**
1. **USE THE SUBJECT LINE FIRST** to identify the hotel name. The subject often follows patterns like "<Hotel Name> STOP SALE" or "STOP SALE: <Hotel Name>". Extract ONLY the actual hotel name, not the entire subject.
2. **If no clear hotel name is found in the subject**, THEN look in the BODY (e.g., near company signatures, headers, or letterhead).
3. **USE THE SAME HOTEL NAME FOR ALL RULES** unless there is explicit indication of multiple hotels.
4. **NEVER use room type codes as hotel names** (e.g., don't use codes like "DROOF", "DLV", "DSEA", "DLAGE" as hotel names).
5. **WATCH FOR SIGNATURES at the end of emails** which often contain the official hotel name.

For each rule found, extract:
- hotel_name: The name of the hotel following the critical rules above.
- room_type: Specific room type or 'All Room' (for general terms like 'all rooms', 'tüm odalar').
- markets: List of markets, or ["ALL"] if unspecified.
- start_date: YYYY-MM-DD format. ONLY if explicitly mentioned in text. Set to null if uncertain or not mentioned.
- end_date: YYYY-MM-DD format. ONLY if explicitly mentioned. Set to null if uncertain or not mentioned.
- sale_status: 'stop' or 'open'.

**EXTREMELY IMPORTANT DATE RULES:**
1. **NEVER invent dates** when they are not specified.
2. **ONLY extract dates clearly mentioned in the email**.
3. **Set start_date and end_date to null** if they are not clearly mentioned.
4. If the date format is ambiguous (e.g., only day/month with no year), assume current year.
5. **If only one date is mentioned**, set both start_date and end_date to that date.
6. **NEVER assume date ranges** unless explicitly written.

ADDITIONAL INSTRUCTIONS:
- If the BODY looks like a table/list from an attachment, treat each row/item as a separate rule.
- ALWAYS format dates as YYYY-MM-DD or null. Do not make up dates.
- If a date reference is vague or uncertain (like "next week" or "coming days"), set date to null.
- Output ONLY the valid JSON list. No extra text, explanations, or markdown.

Example JSON Output:
```json
[
  {
    "hotel_name": "Example Hotel Name",
    "room_type": "Standard Room",
    "markets": ["UK", "DE"],
    "start_date": "2025-05-10",
    "end_date": "2025-05-15",
    "sale_status": "stop"
  },
  {
    "hotel_name": "Example Hotel Name",
    "room_type": "All Room",
    "markets": ["ALL"],
    "start_date": null,
    "end_date": null,
    "sale_status": "open"
  }
]
```

Now, analyze the following structured content:
"""
        
        # Check if prompt with same title already exists
        existing_prompt = Prompt.objects.filter(title=new_prompt_title).first()
        if existing_prompt and not options['force']:
            existing_prompt.content = new_prompt_content
            existing_prompt.active = True  # Make it active
            existing_prompt.save()
            self.stdout.write(self.style.SUCCESS(f'Updated existing prompt "{new_prompt_title}" and made it active'))
            return
        
        # Create new prompt if it doesn't exist or force is True
        if existing_prompt and options['force']:
            self.stdout.write(self.style.WARNING(f'Deleting existing prompt "{new_prompt_title}" and creating a new one'))
            existing_prompt.delete()
        
        # Create the prompt
        prompt = Prompt.objects.create(
            title=new_prompt_title,
            content=new_prompt_content,
            active=True,  # Make it active automatically
            success_rate=0.0
        )
        self.stdout.write(self.style.SUCCESS(f'Successfully created new prompt "{new_prompt_title}" and made it active'))
        
        # Deactivate other prompts (this is also done in the model's save method, but for clarity)
        Prompt.objects.exclude(id=prompt.id).update(active=False)
        self.stdout.write(self.style.SUCCESS('Deactivated all other prompts')) 