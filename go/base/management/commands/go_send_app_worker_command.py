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

    def handle(self, worker_name, command, parameters, **config):
        self.sender = self.sender_class()
        if command not in self.allowed_commands:
            self.stderr.write('Unknown command %s' % (command,))

        command_parameters = dict([parameter.strip().split('=', 1)
                                    for parameter in parameters.split(' ')])

        cmd = VumiApiCommand.command(worker_name, command,
            **command_parameters)
        self.sender.send_command(cmd)
