from django.apps import AppConfig
import sys
import os

class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organizations'

    def ready(self):
        # Prevent running during database migrations, tests, collectstatic, or shells
        is_manage_command = len(sys.argv) > 1 and sys.argv[1] in {
            'migrate', 'makemigrations', 'test', 'collectstatic', 'shell', 
            'createsuperuser', 'showmigrations', 'check'
        }
        
        if not is_manage_command:
            # Under runserver, only start in the main worker process (RUN_MAIN=true)
            is_runserver = 'runserver' in sys.argv
            if not is_runserver or os.environ.get('RUN_MAIN') == 'true':
                try:
                    from organizations.scheduler import BackupScheduler
                    scheduler = BackupScheduler()
                    scheduler.start()
                except Exception as e:
                    print(f"Failed to start backup scheduler: {str(e)}")

