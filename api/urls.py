from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    HomeView,
    SignupView,
    LoginView,
    MeView,
    ProfileMeView,
    PersonalInfoUpdateView,
    BankInfoUpdateView,
    BanksView,
    banks_list,
    ProfileSubmitView,
    OnePipeWebhookView,
)

app_name = 'api'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/signup/', SignupView.as_view(), name='signup'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('profile/me/', ProfileMeView.as_view(), name='profile_me'),
    path('profile/personal/', PersonalInfoUpdateView.as_view(), name='profile_personal'),
    path('profile/bank/', BankInfoUpdateView.as_view(), name='profile_bank'),
    path('profile/submit/', ProfileSubmitView.as_view(), name='profile_submit'),
    path('banks/', banks_list, name='banks'),
    path('webhooks/onepipe/', OnePipeWebhookView.as_view(), name='webhook_onepipe'),
]
