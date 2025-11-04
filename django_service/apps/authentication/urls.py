# apps/authentication/urls.py

from django.urls import path
from .views import RegisterView, APIKeyListCreateView, APIKeyRevokeView,ValidateTokenView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('internal/validate-token/', ValidateTokenView.as_view(), name='validate-token'),
    # --- APIKey CRUD endpoints ---
    path('apikeys/', APIKeyListCreateView.as_view(), name='apikey-list-create'),
    path('apikeys/<int:pk>/', APIKeyRevokeView.as_view(), name='apikey-revoke'),
]
