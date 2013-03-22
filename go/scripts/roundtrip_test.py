# -*- test-case-name: go.scripts.test.test_roundtrip_test -*-
import sys

from twisted.internet.defer import (maybeDeferred, inlineCallbacks,
                                    DeferredQueue, returnValue)
from twisted.internet import reactor
from twisted.python import usage
from twisted.python import log as twisted_log

from vumi.servicemaker import VumiOptions, overlay_configs, read_yaml_config
from vumi.service import WorkerCreator
from vumi.worker import BaseWorker
from vumi.config import ConfigText, ConfigDict
from vumi.utils import load_class_by_string


class RoundTripOptions(VumiOptions):
    optParameters = [
        ["config", "c", None,
            "YAML config file to load for roundtrip test."],
    ]

    def __init__(self):
        VumiOptions.__init__(self)
        self.set_options = {}

    def postOptions(self):
        VumiOptions.postOptions(self)
        if not self['config']:
            raise usage.UsageError("Please provide the config parameter.")
        self.worker_config = self.get_worker_config()

    def get_worker_config(self):
        config_file = self.opts.pop('config')

        # non-recursive overlay is safe because set_options
        # can only contain simple key-value pairs.
        return overlay_configs(
            read_yaml_config(config_file),
            self.set_options)


class RoundTripConfig(BaseWorker.CONFIG_CLASS):
    transport_name = ConfigText('The transport_name to use', required=True,
                                    static=True)
    test_class = ConfigText('The test class to run.', required=True,
                                static=True)
    test_class_config = ConfigDict('The config for the test_class',
                                    required=False, static=True, default={})


class RoundTripTester(BaseWorker):

    WORKER_QUEUE = DeferredQueue()
    CONFIG_CLASS = RoundTripConfig

    @inlineCallbacks
    def setup_connectors(self):
        config = self.get_static_config()
        connector = yield self.setup_ro_connector(config.transport_name)
        connector.set_outbound_handler(self.process_message)
        returnValue(connector)

    def process_message(self, message):
        self.tester.process_message(message)

    def setup_worker(self):
        config = self.get_static_config()
        test_class = load_class_by_string(config.test_class)
        self.tester = test_class(config.test_class_config)
        self.unpause_connectors()
        self.WORKER_QUEUE.put(self)


@inlineCallbacks
def main(options):
    worker_creator = WorkerCreator(options.vumi_options)
    worker_creator.create_worker_by_class(
        RoundTripTester, options.worker_config).startService()
    yield RoundTripTester.WORKER_QUEUE.get()


if __name__ == '__main__':

    twisted_log.startLogging(sys.stdout)

    try:
        options = RoundTripOptions()
        options.parseOptions()
    except usage.UsageError, e:
        print '%s: %s' % (sys.argv[0], e)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    def _eb(f):
        f.printTraceback()
        reactor.stop()

    def _main():
        maybeDeferred(main, options).addErrback(_eb)

    reactor.callLater(0, _main)
    reactor.run()
