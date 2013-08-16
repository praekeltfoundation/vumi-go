from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class StaticReplyForm(forms.Form):
    reply_text = forms.CharField()


class EditStaticReplyView(EditConversationView):
    edit_forms = (
        (None, StaticReplyForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditStaticReplyView
