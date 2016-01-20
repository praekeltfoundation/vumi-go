from go.vumitools.conversation.definition import ConversationDefinitionBase

from go.apps.dialogue.dialogue_api import DialogueActionDispatcher
from go.apps.dialogue.utils import configured_endpoints
from go.apps.jsbox.definition import SendJsboxAction


class SendDialogueAction(SendJsboxAction):
    action_display_name = 'Send Dialogue'
    action_display_verb = 'Send dialogue now'
    action_schedule_verb = 'Schedule dialogue send'

    def perform_scheduled_action(self, action_data):
        # We're importing here to avoid top level django imports in the
        # definition.
        # TODO: Find a better solution.
        from go.scheduler.models import Task
        task = Task.objects.create(
            account_id=self._conv.user_api.user_account_key,
            label='Dialogue Message Send',
            task_type=Task.TYPE_CONVERSATION_ACTION,
            task_data={
                'conversation_key': self._conv.key,
                'action_name': 'send_jsbox',
                'action_kwargs': {},
            },
            scheduled_for=action_data['scheduled_datetime'])
        task.save()


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'dialogue'

    actions = (
        SendDialogueAction,
    )

    api_dispatcher_cls = DialogueActionDispatcher

    def configured_endpoints(self, config):
        return configured_endpoints(config)
