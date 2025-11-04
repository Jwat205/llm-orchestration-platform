import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')  # or 'config.settings.production' for prod

application = get_wsgi_application()
