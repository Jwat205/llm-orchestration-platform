from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('me/', views.UserSelfView.as_view(), name='user-self'),
    path('list/', views.UserListView.as_view(), name='user-list'),         # (admin-only, for example)
    # Add more endpoints as needed
]
