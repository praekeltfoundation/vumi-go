"""Go API action dispatcher for dialogue conversations."""

from twisted.internet.defer import inlineCallbacks, returnValue
from go.api.go_api.action_dispatcher import ConversationActionDispatcher


def definition(conv):
    # to avoid problems caused by circular dependency
    from go.apps.dialogue.definition import ConversationDefinition
    return ConversationDefinition(conv)


class DialogueActionDispatcher(ConversationActionDispatcher):
    def action_get_poll(self, user_api, conv):
        return {"poll": conv.config.get("poll", {})}

    @inlineCallbacks
    def action_save_poll(self, user_api, conv, poll):
        dfn = definition(conv)

        config = conv.config.copy()
        config["poll"] = poll

        dfn.update_config((yield user_api.get_user_account()), config)
        yield conv.save()

        returnValue({"saved": True})
