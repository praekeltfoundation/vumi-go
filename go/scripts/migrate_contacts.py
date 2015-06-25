import sys
from twisted.python import usage
from twisted.internet import reactor
from twisted.internet.defer import (
    maybeDeferred, DeferredQueue, inlineCallbacks, returnValue)
from vumi.service import Worker, WorkerCreator
from vumi.servicemaker import VumiOptions
import yaml

from go.vumitools.api import VumiApi


class ScriptError(Exception):
    """
    An error to be caught and displayed nicely by a script handler.
    """


class ContactMigrationOptions(VumiOptions):
    optParameters = [
        ["user-account-key", None, None,
         "User account to migrate contacts for."],
        ["vumigo-config", None, None,
         "File containing persistence configuration."],
    ]

    def postOptions(self):
        VumiOptions.postOptions(self)
        if not self['vumigo-config']:
            raise usage.UsageError(
                "Please provide the vumigo-config parameter.")
        if not self['user-account-key']:
            raise usage.UsageError(
                "Please provide the user-account-key parameter.")

    def get_vumigo_config(self):
        with file(self['vumigo-config'], 'r') as stream:
            return yaml.safe_load(stream)


class ContactMigrationWorker(Worker):

    WORKER_QUEUE = DeferredQueue()

    stdout = sys.stdout
    stderr = sys.stderr

    def get_contact_keys(self, user_api):
        return user_api.contact_store.list_contacts()

    @inlineCallbacks
    def migrate_contact(self, user_api, contact_key):
        contact = yield user_api.contact_store.contacts.load(contact_key)
        if contact is None:
            self.emit(
                "Unable to load contact %s -- ignoring." % (contact_key,),
                stderr=True)
        elif not contact.was_migrated:
            self.emit(
                "Contact %s already migrated -- ignoring." % (contact_key,))
        else:
            yield contact.save()
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def migrate_contacts_for_account(self, user_account_key):
        user_api = self.vumi_api.get_user_api(user_account_key)
        contact_keys = yield self.get_contact_keys(user_api)
        contact_count = len(contact_keys)
        migrated_count = 0
        self.emit("Starting migration of %s contacts." % (contact_count,))
        for i, contact_key in enumerate(contact_keys):
            migrated = yield self.migrate_contact(user_api, contact_key)
            if migrated:
                migrated_count += 1
            if (i + 1) % 100 == 0:
                self.emit("Contacts migrated: %s (%s) / %s" % (
                    i + 1, migrated_count, contact_count))
        self.emit("Finished processing %s contacts, %s migrated." % (
            contact_count, migrated_count))

    @inlineCallbacks
    def startWorker(self):
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        self.WORKER_QUEUE.put(self)

    @inlineCallbacks
    def stopWorker(self):
        yield self.vumi_api.cleanup()

    def emit(self, obj, stderr=False):
        msg = '%s\n' % (obj,)
        if stderr:
            self.stderr.write(msg)
        else:
            self.stdout.write(msg)


@inlineCallbacks
def main(options):
    worker_creator = WorkerCreator(options.vumi_options)
    service = worker_creator.create_worker_by_class(
        ContactMigrationWorker, options.get_vumigo_config())
    service.startService()

    worker = yield ContactMigrationWorker.WORKER_QUEUE.get()
    yield worker.migrate_contacts_for_account(options['user-account-key'])
    reactor.stop()


if __name__ == '__main__':
    try:
        options = ContactMigrationOptions()
        options.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    def _eb(f):
        f.printTraceback()

    def _main():
        maybeDeferred(main, options).addErrback(_eb)

    reactor.callLater(0, _main)
    reactor.run()
