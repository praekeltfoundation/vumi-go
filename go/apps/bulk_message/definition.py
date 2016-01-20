from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class BulkSendAction(ConversationAction):
    action_name = 'bulk_send'
    action_display_name = 'Write and send bulk message'
    action_display_verb = 'Send message now'
    action_schedule_verb = 'Schedule'

    needs_confirmation = True

    needs_group = True
    needs_running = True

    def check_disabled(self):
        if self._conv.has_channel_supporting_generic_sends():
            return None
        return ("This action needs channels capable of sending"
                " messages attached to this conversation.")

    def perform_action(self, action_data):
        return self.send_command(
            'bulk_send', batch_id=self._conv.batch.key,
            msg_options={}, content=action_data['message'],
            delivery_class=action_data['delivery_class'],
            dedupe=action_data['dedupe'])

    def perform_scheduled_action(self, action_data):
        # We're importing here to avoid top level django imports in the
        # definition.
        # TODO: Find a better solution.
        from go.scheduler.models import Task
        task = Task.objects.create(
            account_id=self._conv.user_api.user_account_key,
            label='Bulk Message Send',
            task_type=Task.TYPE_CONVERSATION_ACTION,
            task_data={
                'conversation_key': self._conv.key,
                'action_name': 'bulk_send',
                'action_kwargs': {
                    'message': action_data['message'],
                    'delivery_class': action_data['delivery_class'],
                    'dedupe': action_data['dedupe'],
                },
            },
            scheduled_for=action_data['scheduled_datetime'])
        task.save()


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'bulk_message'

    actions = (BulkSendAction,)
