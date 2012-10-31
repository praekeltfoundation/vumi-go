from django.core.management.base import BaseCommand, CommandError
from go.vumitools.api import SyncMessageSender, VumiApiCommand


class Command(BaseCommand):
    help = "Send a VumiApi command to an application worker"
    args = "<worker-name> <command> key1=value1 key2=value2"
    sender_class = SyncMessageSender

    def handle(self, worker_name, command, *parameters, **config):
        self.sender = self.sender_class()
        handler = getattr(self, 'handle_%s' % (command,), None)
        if handler is None:
            raise CommandError('Unknown command %s' % (command,))

        args = []
        kwargs = {}
        for parameter in parameters:
            parameter = parameter.strip()
            if '=' in parameter:
                kwargs.update(dict((parameter.split('=', 1),)))
            else:
                args.append(parameter)

        cmd = handler(worker_name, command, *args, **kwargs)
        self.sender.send_command(cmd)

    def handle_reconcile_cache(self, worker_name, command, account_key,
        conversation_key):
        return VumiApiCommand.command(worker_name, command,
            user_account_key=account_key, conversation_key=conversation_key)
