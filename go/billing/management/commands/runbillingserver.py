import sys

from twisted.python import log
from twisted.internet import reactor

from django.core.management.base import BaseCommand, CommandError

from go.billing import api


class Command(BaseCommand):

    args = "<port>"
    help = "Starts the Billing server on the given port (default: 9090)"

    def handle(self, *args, **options):
        port = 9090
        if len(args) > 0:
            try:
                port = int(args[0])
            except ValueError:
                raise CommandError("%s is not a valid port number.\n" %
                                  (args[0],))

        def connection_established(connection_pool):
            from twisted.web.server import Site
            reactor.listenTCP(port, Site(api.root))
            reactor.callWhenRunning(
                lambda _: _.stdout.write(
                    "Billing server is running at "
                    "http://127.0.0.1:%s/\n" % port), self)

        def connection_error(err):
            self.stderr.write(err)

        log.startLogging(sys.stdout)
        d = api.start_connection_pool()
        d.addCallbacks(connection_established, connection_error)
        reactor.run()
