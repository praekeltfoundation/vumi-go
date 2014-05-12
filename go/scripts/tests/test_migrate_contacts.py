from StringIO import StringIO
from uuid import uuid4

from twisted.internet.defer import inlineCallbacks, returnValue, gatherResults
from vumi.persist.model import ModelMigrationError
from vumi.tests.helpers import VumiTestCase

from go.scripts.migrate_contacts import ContactMigrationWorker
from go.vumitools.contact.old_models import ContactV1
from go.vumitools.tests.helpers import VumiApiHelper


class TestMigrateContacts(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())

    @inlineCallbacks
    def get_worker(self):
        vumigo_config = self.vumi_helper.mk_config({})
        worker_helper = self.vumi_helper.get_worker_helper()
        worker = yield worker_helper.get_worker(
            ContactMigrationWorker, vumigo_config)
        worker.stdout = StringIO()
        worker.stderr = StringIO()
        returnValue(worker)

    def make_contact(self, user_helper, **fields):
        return user_helper.user_api.contact_store.new_contact(**fields)

    def _get_old_contact_proxy(self, user_helper):
        riak_manager = user_helper.user_api.contact_store.manager
        return riak_manager.proxy(ContactV1)

    def make_old_contact(self, user_helper, **fields):
        contact_id = uuid4().get_hex()
        groups = fields.pop('groups', [])
        model_proxy = self._get_old_contact_proxy(user_helper)
        contact = model_proxy(
            contact_id, user_account=user_helper.account_key, **fields)
        for group in groups:
            contact.add_to_group(group)
        d = contact.save()
        d.addCallback(lambda _: contact)
        return d

    @inlineCallbacks
    def assert_contact_is_old(self, user_helper, contact_key):
        model_proxy = self._get_old_contact_proxy(user_helper)
        try:
            contact = yield model_proxy.load(contact_key)
        except ModelMigrationError:
            self.fail(
                "Failed to load contact %s as version 1." % (contact_key,))
        self.assertEqual(contact.VERSION, 1)

    @inlineCallbacks
    def assert_contact_is_new(self, user_helper, contact_key):
        model_proxy = self._get_old_contact_proxy(user_helper)
        try:
            yield model_proxy.load(contact_key)
        except ModelMigrationError:
            pass
        else:
            self.fail("Loaded contact %s as version 1, expected failure." %
                      (contact_key,))

    @inlineCallbacks
    def test_get_contact_keys(self):
        """
        .get_contact_keys() should return keys for all contacts belonging to
        the specified account.
        """
        worker = yield self.get_worker()
        user1 = yield self.vumi_helper.make_user(u"user1")
        contacts1 = yield gatherResults([
            self.make_contact(user1, msisdn=u"+%s" % i) for i in range(3)])
        user2 = yield self.vumi_helper.make_user(u"user2")
        contacts2 = yield gatherResults([
            self.make_contact(user2, msisdn=u"+%s" % i) for i in range(3)])

        contact_keys_1 = yield worker.get_contact_keys(user1.user_api)
        self.assertEqual(
            sorted(contact_keys_1), sorted([c.key for c in contacts1]))
        contact_keys_2 = yield worker.get_contact_keys(user2.user_api)
        self.assertEqual(
            sorted(contact_keys_2), sorted([c.key for c in contacts2]))

    @inlineCallbacks
    def test_migrate_contact(self):
        """
        .migrate_contact() should migrate the specified contact to the latest
        version.
        """
        worker = yield self.get_worker()
        user = yield self.vumi_helper.make_user(u"user")
        contact = yield self.make_old_contact(user, msisdn=u"+0")
        yield self.assert_contact_is_old(user, contact.key)
        yield worker.migrate_contact(user.user_api, contact.key)
        yield self.assert_contact_is_new(user, contact.key)

    @inlineCallbacks
    def test_migrate_contact_missing(self):
        """
        .migrate_contact() should log a message and continue if the specified
        contact does not exist.
        """
        worker = yield self.get_worker()
        user = yield self.vumi_helper.make_user(u"user")
        self.assertEqual(worker.stderr.getvalue(), "")
        yield worker.migrate_contact(user.user_api, "badcontact")
        self.assertEqual(
            worker.stderr.getvalue(),
            "Unable to load contact badcontact -- ignoring.\n")

    @inlineCallbacks
    def test_migrate_contact_already_migrated(self):
        """
        .migrate_contact() should log a message and continue if the specified
        contact does not need migration.
        """
        worker = yield self.get_worker()
        user = yield self.vumi_helper.make_user(u"user")
        self.assertEqual(worker.stdout.getvalue(), "")
        contact = yield self.make_contact(user, msisdn=u"+0")
        yield worker.migrate_contact(user.user_api, contact.key)
        self.assertEqual(
            worker.stdout.getvalue(),
            "Contact %s already migrated -- ignoring.\n" % (contact.key,))

    @inlineCallbacks
    def test_migrate_contacts_for_account(self):
        """
        .migrate_contacts_for_account() should migrate all contacts in the
        specified account.
        """
        worker = yield self.get_worker()
        user = yield self.vumi_helper.make_user(u"user")
        contacts = yield gatherResults([
            self.make_old_contact(user, msisdn=u"+%s" % i) for i in range(3)])
        for contact in contacts:
            yield self.assert_contact_is_old(user, contact.key)
        yield worker.migrate_contacts_for_account(user.account_key)
        for contact in contacts:
            yield self.assert_contact_is_new(user, contact.key)

    @inlineCallbacks
    def test_migrate_contacts_output(self):
        """
        .migrate_contacts_for_account() should emit appropriate progress
        messages.
        """
        worker = yield self.get_worker()
        user = yield self.vumi_helper.make_user(u"user")

        def generate_contact_keys(user_api):
            return ['contact%03s' % i for i in xrange(1000)]

        worker.get_contact_keys = generate_contact_keys
        worker.migrate_contact = lambda user_api, contact_key: (
            not contact_key.endswith('0'))
        yield worker.migrate_contacts_for_account(user.account_key)
        self.assertEqual(worker.stdout.getvalue(), ''.join([
            'Starting migration of 1000 contacts.\n',
            'Contacts migrated: 100 (90) / 1000\n',
            'Contacts migrated: 200 (180) / 1000\n',
            'Contacts migrated: 300 (270) / 1000\n',
            'Contacts migrated: 400 (360) / 1000\n',
            'Contacts migrated: 500 (450) / 1000\n',
            'Contacts migrated: 600 (540) / 1000\n',
            'Contacts migrated: 700 (630) / 1000\n',
            'Contacts migrated: 800 (720) / 1000\n',
            'Contacts migrated: 900 (810) / 1000\n',
            'Contacts migrated: 1000 (900) / 1000\n',
            'Finished processing 1000 contacts, 900 migrated.\n',
        ]))
