"""Go API action dispatcher for dialogue conversations."""

from go.api.go_api.action_dispatcher import ConversationActionDispatcher


class DialogueActionDispatcher(ConversationActionDispatcher):
    def action_get_poll(self, user_api, conv):
        return {"poll": conv.config.get("poll", {})}

    def action_save_poll(self, user_api, conv, poll):
        conv.config["poll"] = poll
        d = conv.save()
        d.addCallback(lambda r: {"saved": True})
        return d
