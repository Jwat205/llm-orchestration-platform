from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from shared.schemas.internal import UserValidationRequest, UserValidationResponse, UsageLoggingRequest, RateLimitCheckRequest

@api_view(['POST'])
@permission_classes([AllowAny])  # Internal endpoint, secure at network or with tokens
def validate_token(request):
    # Validate JWT token here logic (simplified)
    token = request.data.get('token')
    if token == "valid_token_example":
        return Response(UserValidationResponse(valid=True, user_id=1, email="user@example.com", is_active=True).dict())
    return Response(UserValidationResponse(valid=False).dict(), status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_usage(request):
    # Log usage to DB or analytics (simplified)
    # Extract usage info here
    return Response({"status": "usage logged"})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_rate_limit(request):
    # Check rate limit for user or API key (simplified)
    return Response({"allowed": True})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_permissions(request):
    # Return user permission info (simplified)
    return Response({"permissions": ["read", "write"]})
