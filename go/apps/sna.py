class SNAUSSDOptOutHandler(object):

    def __init__(self, account_key=None, redis={},
                    poll_manager_prefix='vumigo.', riak={}):
        self.account_key = account_key
        self.pm_prefix = poll_manager_prefix
        self.pm = PollManager(self.get_redis(redis), self.pm_prefix)
        self.manager = TxRiakManager.from_config(riak)
        self.oo_store = OptOutStore(self.manager, self.account_key)
        self.contact_store = ContactStore(self.manager, self.account_key)

    def get_redis(self, config):
        return redis.Redis(**config)

    def teardown_handler(self):
        self.pm.stop()

    @inlineCallbacks
    def handle_message(self, message):
        addr = message['to_addr']
        if message.get('transport_type') != 'ussd':
            log.info("SNAUSSDOptOutHandler skipping non-ussd"
                     " message for %r" % (addr,))
            return
        contact = yield self.contact_store.contact_for_addr('ussd', addr)
        if contact:
            opted_out = contact.extra['opted_out']
            if opted_out is not None:
                if int(opted_out) > 1:
                    yield self.oo_store.new_opt_out('msisdn', addr,
                        message)
                else:
                    yield self.oo_store.delete_opt_out('msisdn', addr)
