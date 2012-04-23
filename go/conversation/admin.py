from django.contrib import admin
from go.conversation.models import Conversation, MessageBatch

admin.site.register(Conversation)
admin.site.register(MessageBatch)
