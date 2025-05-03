from django.apps import AppConfig


class EmailsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'emails'
    
    def ready(self):
        print("*** EmailsConfig.ready() called ***")
        try:
            # Import signals module to register signal handlers
            import emails.signals
            print("Email signals imported successfully")
        except Exception as e:
            print(f"Error importing email signals: {e}")