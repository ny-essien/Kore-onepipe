from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    HomeView,
    ServicesView,
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
    RulesEngineCreateView,
    RulesEngineDetailView,
    RulesEngineDisableView,
    MandateCreateView,
    MandatesMeView,
    CancelMandateView,
)

app_name = 'api'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('services/', ServicesView.as_view(), name='services'),
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
    path('rules-engine/', RulesEngineCreateView.as_view(), name='rules_engine_create'),
    path('rules-engine/me/', RulesEngineDetailView.as_view(), name='rules_engine_detail'),
        path('rules-engine/me/disable/', RulesEngineDisableView.as_view(), name='rules_engine_disable'),
        path('mandates/create/', MandateCreateView.as_view(), name='mandate_create'),
        path('mandates/me/', MandatesMeView.as_view(), name='mandates_me'),
        path('mandates/cancel/', CancelMandateView.as_view(), name='mandate_cancel'),
]
