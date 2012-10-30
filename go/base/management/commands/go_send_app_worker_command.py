from django.core.management.base import BaseCommand
from go.vumitools.api import SyncMessageSender, VumiApiCommand


class Command(BaseCommand):
    help = "Send a VumiApi command to an application worker"
    args = "<worker-name> <event-type> key1=value1 key2=value2"
    sender_class = SyncMessageSender
    # List of allowed commands
    allowed_commands = [
        'reconcile_cache',
    ]

    def handle(self, worker_name, command, *parameters, **config):
        self.sender = self.sender_class()
        if command not in self.allowed_commands:
            self.stderr.write('Unknown command %s' % (command,))

        args = []
        kwargs = {}
        for parameter in parameters:
            parameter = parameter.strip()
            if '=' in parameter:
                kwargs.update(dict((parameter.split('=', 1),)))
            else:
                args.append(parameter)

        cmd = VumiApiCommand.command(worker_name, command, *args, **kwargs)
        self.sender.send_command(cmd)
