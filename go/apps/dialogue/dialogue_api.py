"""Go API action dispatcher for dialogue conversations."""

from go.api.go_api.action_dispatcher import ConversationActionDispatcher


class DialogueActionDispatcher(ConversationActionDispatcher):
    def handle_get_poll(self, conv):
        pass

    def handle_save_poll(self, conv, poll):
        pass
