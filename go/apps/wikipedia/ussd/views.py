from go.conversation.base import ConversationViews
from go.apps.sequential_send.views import UsedTagConversationForm

class WikipediaUSSDConversationViews(ConversationViews):
    conversation_type = u'wikipedia_ussd'
    conversation_display_name = u'Wikipedia USSD'
    conversation_initiator = u'server'
    edit_conversation_forms = None
    conversation_start_params = {'no_batch_tag': True}
    conversation_form = UsedTagConversationForm
