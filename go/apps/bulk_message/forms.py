from go.conversation.forms import ConversationForm


class BulkSendConversationForm(ConversationForm):
    """Same as the ConversationForm with the only difference being that
    this only only allows for delivery classes that allow for server
    initiated conversations."""

    def __init__(self, *args, **kw):
        kw['tagpool_filter'] = self._server_initiated
        super(BulkSendConversationForm, self).__init__(*args, **kw)

    @staticmethod
    def _server_initiated(pool, metadata):
        return metadata.get('server_initiated', False)
