import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class ChatMessage(models.Model):
    ROLE = [("user", "user"), ("assistant", "assistant"), ("tool", "tool")]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE)
    content = models.TextField(blank=True)
    tool_calls = models.JSONField(null=True, blank=True)
    artifacts = models.JSONField(null=True, blank=True)
    sources = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class TokenUsage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="token_usage")
    message = models.ForeignKey(ChatMessage, null=True, blank=True, on_delete=models.CASCADE)
    model = models.CharField(max_length=40)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
