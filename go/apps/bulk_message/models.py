from go.conversation.models import Conversation, MessageBatch


class BulkMessageConversation(Conversation):

    class Meta:
        proxy = True

    def start(self):
        """
        Send the start command to this conversations application worker.
        """
        tag = self.acquire_tag()
        batch_id = self.start_batch(tag)

        self.dispatch_command('start',
            batch_id=batch_id,
            conversation_type=self.conversation_type,
            conversation_id=self.pk,
            to_addresses=self.get_contacts_addresses(),
            msg_options={
                'transport_type': self.delivery_class,
                'from_addr': tag[1],
            })

        batch = MessageBatch.objects.create(batch_id=batch_id,
                                                message_batch=self)
        batch.save()
