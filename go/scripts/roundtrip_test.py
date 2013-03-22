# -*- test-case-name: go.scripts.test.test_roundtrip_test -*-
import sys

from twisted.internet.defer import (maybeDeferred, inlineCallbacks,
                                    DeferredQueue)
from twisted.internet import reactor
from twisted.python import usage

from vumi.servicemaker import VumiOptions
from vumi.service import WorkerCreator
from vumi.worker import BaseWorker


class RoundTripOptions(VumiOptions):
    optParameters = [
        ["config", "c", None,
            "YAML config file to load for roundtrip test."],
    ]

    def postOptions(self):
        VumiOptions.postOptions(self)
        if not self['config']:
            raise usage.UsageError("Please provide the config parameter.")


class RoundTripTester(BaseWorker):

    WORKER_QUEUE = DeferredQueue()

    def setup_connectors(self):
        print 'setting up connectors'

    def setup_worker(self):
        print 'setup worker called'
        self.WORKER_QUEUE.put(self)


@inlineCallbacks
def main(options):
    worker_creator = WorkerCreator(options.vumi_options)
    worker_creator.create_worker_by_class(
        RoundTripTester, options)
    worker = yield RoundTripTester.WORKER_QUEUE.get()
    print worker
    reactor.stop()


if __name__ == '__main__':
    try:
        options = RoundTripOptions()
        options.parseOptions()
    except usage.UsageError, e:
        print '%s: %s' % (sys.argv[0], e)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    def _eb(f):
        f.printTraceback()

    def _main():
        maybeDeferred(main, options).addErrback(_eb)

    reactor.callLater(0, _main)
    reactor.run()
