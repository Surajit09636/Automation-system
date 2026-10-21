from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProspectViewSet,
    OpportunityFindingViewSet,
    OutreachDraftViewSet,
    ServiceProfileViewSet,
    PipelineRunView,
    DashboardStatsView,
    AgentChatView,
)

router = DefaultRouter()
router.register(r'prospects', ProspectViewSet, basename='prospect')
router.register(r'findings', OpportunityFindingViewSet, basename='finding')
router.register(r'drafts', OutreachDraftViewSet, basename='draft')
router.register(r'service-profile', ServiceProfileViewSet, basename='service-profile')

urlpatterns = [
    path('', include(router.urls)),
    path('pipeline/run/', PipelineRunView.as_view(), name='pipeline-run'),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('agent/chat/', AgentChatView.as_view(), name='agent-chat'),
]
