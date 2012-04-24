from django.core.management.base import BaseCommand, CommandError
from go.conversation.models import Conversation
from vumi.application.tagpool import TagpoolError
from optparse import make_option


class Command(BaseCommand):
    help = "Populate messaging tag pools"

    POOLS = [
        ("longcode", ["default%d" % i for i in range(10001, 10001 + 1000)]),
        ("xmpp", ["go-%s@vumi.org" % i for i in range(1,6)]),
        ]

    POOL_LOOKUP = dict(POOLS)

    option_list = BaseCommand.option_list + (
            make_option('--purge', dest='purge',
                            action='store_true', default=False,
                            help='Purge all existing tags before populating.'),
        )
    option_list += tuple([
        make_option('--%s' % pool, action='append_const', dest='pools',
                        const=pool,
                        help='Declare %s pool tags.' % pool)
        for pool, local_tags in POOLS
        ])

    def handle(self, *args, **options):
        pools = options['pools']
        vumiapi = Conversation.vumi_api()

        if options['purge']:
            for pool in pools:
                try:
                    print 'Purging pool %s ...' % (pool,)
                    vumiapi.purge_pool(pool)
                    print '  done.'
                except TagpoolError, e:
                    raise CommandError(e)

        for pool in pools:
            print "Declaring tags for %s .." % (pool,)
            local_tags = self.POOL_LOOKUP[pool]
            tags = [(pool, local_tag) for local_tag in local_tags]
            vumiapi.declare_tags(tags)
            print "  done."
