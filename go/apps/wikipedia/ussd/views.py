from datetime import datetime

from django import forms
from django.contrib import messages

from go.conversation.base import ConversationViews, NewConversationView
from go.conversation.forms import ConversationForm


class WikipediaConversationForm(ConversationForm):
    send_from_tagpool = forms.CharField(required=True)
    send_from_tag = forms.CharField(required=True)

class NewWikipediaConversationView(NewConversationView):
    template_name = 'new'
    template_base = 'wikipedia'

    def post(self, request):
        form = self.make_conversation_form(request.user_api, request.POST)
        if not form.is_valid():
            return self.render_to_response({'form': form})

        copy_keys = [
            'subject',
            'message',
            'delivery_class',
            'delivery_tag_pool',
            ]
        conversation_data = dict((k, form.cleaned_data[k]) for k in copy_keys)
        conversation_data['metadata'] = {
            'send_from_tagpool': form.cleaned_data['send_from_tagpool'],
            'send_from_tag': form.cleaned_data['send_from_tag']
        }

        tag_info = form.cleaned_data['delivery_tag_pool'].partition(':')
        conversation_data['delivery_tag_pool'] = tag_info[0]
        if tag_info[2]:
            conversation_data['delivery_tag'] = tag_info[2]

        # Ignoring start time, because we don't actually do anything with it.
        conversation_data['start_timestamp'] = datetime.utcnow()

        conversation = request.user_api.new_conversation(
            self.conversation_type, **conversation_data)
        messages.info(request, '%s Created' % (self.conversation_display_name,))

        next_view = self.get_next_view(conversation)
        if self.edit_conversation_forms is not None:
            next_view = 'edit'
        return self.redirect_to(next_view, conversation_key=conversation.key)

class WikipediaUSSDConversationViews(ConversationViews):
    new_conversation_view = NewWikipediaConversationView
    conversation_type = u'wikipedia_ussd'
    conversation_display_name = u'Wikipedia USSD'
    conversation_initiator = u'server'
    edit_conversation_forms = None
    conversation_start_params = {'no_batch_tag': True}
    conversation_form = WikipediaConversationForm
