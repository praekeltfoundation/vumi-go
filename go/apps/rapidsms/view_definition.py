# -*- test-case-name: go.apps.rapidsms.tests.test_view_definition -*-
# -*- coding: utf-8 -*-

"""Conversation views definition for RapidSMS."""

import re

from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class EndpointsField(forms.Field):
    def __init__(self, pattern="^[a-zA-Z0-9_.]*$", separator=",", *args, **kw):
        self._item_re = re.compile(pattern)
        self._separator = separator
        super(EndpointsField, self).__init__(*args, **kw)

    def clean(self, value):
        if not value:
            return []
        if not isinstance(value, basestring):
            raise forms.ValidationError(
                "EndpointsField value must be a string or None.")
        items = [part.strip() for part in value.split(self._separator)]
        for item in items:
            if not self._item_re.match(item):
                raise forms.ValidationError(
                    "EndpointsField item %r does not match pattern %r."
                    % (item, self._item_re.pattern))
        return items


class RapidSmsForm(forms.Form):
    """Configuration options the Vumi Go RapidSMS relay.

    These largely map one-to-one to the configuration options of the
    Vumi RapidSMS relay.
    """

    # RapidSMS options set in static config:
    #
    # allow_replies -> should be set to True
    # vumi_reply_timeout -> should be set to a sensible value

    # Dynamic RapidSMS options that are not user configurable:
    #
    # vumi_username -> conversation ID
    # vumi_password -> authentication token for conversation
    # vumi_auth_method -> "basic"

    # User-configurable RapidSMS options:

    rapidsms_url = forms.URLField(
        help_text="URL of the rapidsms http backend.",
        required=True)
    rapidsms_username = forms.CharField(
        help_text="Username to use for the `rapidsms_url`"
                  " (default: no authentication)",
        required=True)
    rapidsms_password = forms.CharField(
        help_text="Password to use for the `rapidsms_url`",
        required=True)
    rapidsms_auth_method = forms.ChoiceField(
        help_text="Authentication method to use with `rapidsms_url`."
                  " The 'basic' method is currently the only"
                  " available method.",
        choices=[('basic', 'basic')], initial='basic',
        required=True)
    rapidsms_http_method = forms.ChoiceField(
        help_text="HTTP request method to use for the `rapidsms_url`",
        choices=[('POST', 'POST'), ('GET', 'GET')], initial='POST',
        required=True)

    allowed_endpoints = EndpointsField(
        help_text="Comma-separated list of endpoints to allow.",
        initial="default",
    )

    # Authentication token:

    auth_token = forms.CharField(
        help_text='The access token for this RapidSMS conversation.',
        required=True)

    # Fields to copy directly to / from conversation config

    _COPIED_FIELDS = (
        "rapidsms_url", "rapidsms_username", "rapidsms_password",
        "rapidsms_auth_method", "rapidsms_http_method",
    )

    @classmethod
    def initial_from_config(cls, data):
        initial = {}
        for field in cls._COPIED_FIELDS:
            if field in data:
                initial[field] = data[field]
        allowed_endpoints = data.get('allowed_endpoints', ["default"])
        initial["allowed_endpoints"] = u",".join(allowed_endpoints)
        api_tokens = data.get('api_tokens', [])
        initial["auth_token"] = (
            api_tokens[0] if api_tokens else None)
        return initial

    def to_config(self):
        data = self.cleaned_data
        config = {}
        for field in self._COPIED_FIELDS:
            config[field] = data[field]
        config["allowed_endpoints"] = data["allowed_endpoints"]
        config["api_tokens"] = [data["auth_token"]]
        return config


class EditRapidSmsView(EditConversationView):
    edit_forms = (
        ('rapidsms', RapidSmsForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditRapidSmsView
