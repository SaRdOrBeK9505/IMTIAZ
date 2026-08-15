from django.urls import path
from .views import (
    ChatView,
    ChatStreamView,
    SessionBootstrapView,
    ActionConfirmView,
    ActionRejectView,
    SessionListView,
    SessionDetailView,
    AIActionLogListView,
)

urlpatterns = [
    path('chat/',                          ChatView.as_view(),         name='ai-chat'),
    path('chat/stream/',                   ChatStreamView.as_view(),   name='ai-chat-stream'),
    path('sessions/bootstrap/',            SessionBootstrapView.as_view(), name='ai-session-bootstrap'),
    path('actions/<uuid:action_id>/confirm/', ActionConfirmView.as_view(), name='ai-action-confirm'),
    path('actions/<uuid:action_id>/reject/',  ActionRejectView.as_view(),  name='ai-action-reject'),
    path('sessions/',                      SessionListView.as_view(),  name='ai-sessions'),
    path('sessions/<uuid:pk>/',            SessionDetailView.as_view(), name='ai-session-detail'),
    path('logs/',                          AIActionLogListView.as_view(), name='ai-logs'),
]