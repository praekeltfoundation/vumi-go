from django.core.management.base import BaseCommand
from go.conversation.models import Conversation
from optparse import make_option


class Command(BaseCommand):
    help = "Populate messaging tag pools"

    POOLS = [
        ("ambient", ["default%d" % i for i in range(10001, 10001 + 1000)]),
        ("gtalk", ["go-%d" % i for i in range(1, 1 + 5)]),
        ]

    POOL_LOOKUP = dict(POOLS)

    option_list = BaseCommand.option_list + tuple([
        make_option('--%s' % pool, action='append_const', dest='pools',
                        const=pool,
                        help='Declare %s pool tags.' % pool)
        for pool, local_tags in POOLS
        ])

    def handle(self, *args, **options):
        pools = options['pools']
        vumiapi = Conversation.vumi_api()

        for pool in pools:
            print "Declaring tags for %s .." % (pool,)
            local_tags = self.POOL_LOOKUP[pool]
            tags = [(pool, local_tag) for local_tag in local_tags]
            vumiapi.declare_tags(tags)
            print "  done."
