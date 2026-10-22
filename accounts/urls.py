from django.urls import path
from .views import Register, Login, CurrentUser, Logout

urlpatterns = [
    path('register/', Register.as_view(), name='auth-register'),
    path('login/', Login.as_view(), name='auth-login'),
    path('me/', CurrentUser.as_view(), name='auth-me'),
    path('logout/', Logout.as_view(), name='auth-logout'),
]
