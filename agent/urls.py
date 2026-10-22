from django.urls import path
from agent.views import AgentPipelineView, AgentAuditView, AgentCategoriesView
from prospects.views import AgentChatView

urlpatterns = [
    path('pipeline/', AgentPipelineView.as_view(), name='agent-pipeline'),
    path('audit/', AgentAuditView.as_view(), name='agent-audit'),
    path('categories/', AgentCategoriesView.as_view(), name='agent-categories'),
    path('chat/', AgentChatView.as_view(), name='agent-chat'),
]
