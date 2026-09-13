# apps/authentication/views.py
import logging
from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from .permissions import IsEmailVerified, IsAdminUser
from .serializers import RegisterSerializer, APIKeySerializer
from .models import APIKey
from .throttling import check_rate_limit, user_rate_limit_key
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

logger = logging.getLogger(__name__)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(request, email=email, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            })
        return Response({"error": "Invalid credentials"}, status=401)

class EmailVerificationView(APIView):
    permission_classes = [IsEmailVerified]

    def get(self, request):
        # Only verified users can access
        return Response({"status": "email verified!"})

class AdminOnlyView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Only admins
        return Response({"status": "admin stuff"})
    
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # If you want to return just email/id, do this:
            data = {"id": user.id, "email": user.email}
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIKeyListCreateView(generics.ListCreateAPIView):
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user).select_related('user')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class APIKeyRevokeView(generics.DestroyAPIView):
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)
    
from rest_framework_simplejwt.authentication import JWTAuthentication

class ValidateTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        jwt_auth = JWTAuthentication()
        try:
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            user = user.__class__.objects.prefetch_related('user_permissions', 'groups__permissions').get(pk=user.pk)

            codenames = {perm.codename for perm in user.user_permissions.all()}
            for group in user.groups.all():
                codenames.update(perm.codename for perm in group.permissions.all())
            if user.is_staff or user.is_superuser:
                codenames.add("admin")

            return Response({
                "valid": True,
                "user_id": user.id,
                "email": user.email,
                "permissions": sorted(codenames),
                "is_active": user.is_active,

            })
        except Exception:
            return Response({"valid": False}, status=401)


class CheckRateLimitView(APIView):
    """
    Internal endpoint called by the FastAPI service before running
    inference. Shares the same Redis-backed fixed-window counter as
    UserRateThrottle so a user's limit is consistent across both services.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from .throttling import UserRateThrottle

        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"allowed": False, "error": "user_id is required"}, status=400)

        throttle = UserRateThrottle()
        allowed = check_rate_limit(
            user_rate_limit_key(user_id), throttle.num_requests, throttle.duration
        )
        return Response({"allowed": allowed})


class LogUsageView(APIView):
    """
    Internal endpoint the FastAPI service calls after each inference to
    record usage. No dedicated usage-tracking model exists yet, so this
    logs the event; wire it to a real model/table before relying on it
    for billing.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info("llm_usage", extra={"usage": request.data})
        return Response({"logged": True})