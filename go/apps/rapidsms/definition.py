# -*- test-case-name: go.apps.rapidsms.tests.test_definition -*-
# -*- coding: utf-8 -*-

"""Conversation definition for RapidSMS."""

from go.vumitools.conversation.definition import ConversationDefinitionBase


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = u'rapidsms'
