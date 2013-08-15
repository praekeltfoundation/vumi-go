from optparse import make_option
from pprint import pformat

from django.core.management.base import CommandError

from go.base.command_utils import BaseGoAccountCommand, make_command_option


class Command(BaseGoAccountCommand):
    help = "Manage routers."

    option_list = BaseGoAccountCommand.option_list + (
        make_command_option(
            'list', help='List the active routers in this account.'),
        make_command_option('show', help='Display a router'),
        make_command_option(
            'show_config', help='Display the config for a router'),
        make_command_option('start', help='Start a router'),
        make_command_option('stop', help='Stop a router'),
        make_command_option('archive', help='Archive a router'),

        make_option('--router-key',
                    dest='router_key',
                    help='The router key'),
    )

    def get_router(self, options):
        if 'router_key' not in options:
            raise CommandError('Please specify a router key')
        router = self.user_api.get_router(options['router_key'])
        if router is None:
            raise CommandError('Router does not exist')
        return router

    def handle_command_list(self, *args, **options):
        routers = self.user_api.active_routers()
        routers.sort(key=lambda c: c.created_at)
        for i, c in enumerate(routers):
            self.stdout.write("%d. %s (type: %s, key: %s)\n"
                              % (i, c.name, c.router_type, c.key))

    def handle_command_show(self, *args, **options):
        router = self.get_router(options)
        self.stdout.write(pformat(router.get_data()))
        self.stdout.write("\n")

    def handle_command_show_config(self, *args, **options):
        router = self.get_router(options)
        self.stdout.write(pformat(router.config))
        self.stdout.write("\n")

    def handle_command_start(self, *apps, **options):
        router = self.get_router(options)
        if router.archived():
            raise CommandError('Archived routers cannot be started')
        if router.running() or router.stopping():
            raise CommandError('Router already running')

        self.stdout.write("Starting router...\n")
        rapi = self.user_api.get_router_api(router.router_type, router.key)
        rapi.start_router()
        self.stdout.write("Router started\n")

    def handle_command_stop(self, *apps, **options):
        router = self.get_router(options)
        if router.archived():
            raise CommandError('Archived routers cannot be stopped')
        if router.stopped():
            raise CommandError('Router already stopped')

        self.stdout.write("Stopping router...\n")
        rapi = self.user_api.get_router_api(router.router_type, router.key)
        rapi.stop_router()
        self.stdout.write("Router stopped\n")

    def handle_command_archive(self, *apps, **options):
        router = self.get_router(options)
        if router.archived():
            raise CommandError('Archived routers cannot be archived')
        if not router.stopped():
            raise CommandError('Only stopped routers can be archived')

        self.stdout.write("Archiving router...\n")
        rapi = self.user_api.get_router_api(router.router_type, router.key)
        rapi.archive_router()
        self.stdout.write("Router archived\n")
