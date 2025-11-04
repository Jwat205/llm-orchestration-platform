from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # Sends visitors to the admin panel
    path('api/auth/', include('apps.authentication.urls')),  # Authentication/keys/JWT endpoints
    path('api/users/', include('apps.users.urls')),  # User management endpoints
    path('', include('django_prometheus.urls')),
]
