# -*- test-case-name: go.apps.jsbox.tests.test_optout -*-
# -*- coding: utf-8 -*-

"""Resource for accessing and modifying a contact's opt-out/opt-in
   status from the sandbox"""

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.sandbox import SandboxResource
from vumi import log


class OptoutResource(SandboxResource):
    pass
