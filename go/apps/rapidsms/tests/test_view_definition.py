from django import forms

from vumi.tests.helpers import VumiTestCase

from go.apps.rapidsms.view_definition import (
    EndpointsField, RapidSmsForm, EditRapidSmsView,
    ConversationViewDefinition)


class TestEndpointsField(VumiTestCase):
    def test_clean_none(self):
        f = EndpointsField()
        self.assertEqual(f.clean(None), [])

    def test_clean_empty_string(self):
        f = EndpointsField()
        self.assertEqual(f.clean(""), [])

    def test_clean_invalid_type(self):
        f = EndpointsField()
        self.assertRaises(forms.ValidationError, f.clean, 5)

    def test_clean_one_endpoint(self):
        f = EndpointsField()
        self.assertEqual(f.clean(u"foo"), [u"foo"])

    def test_clean_two_endpoints(self):
        f = EndpointsField()
        self.assertEqual(f.clean(u"foo, bar"), [u"foo", u"bar"])

    def test_clean_invalid_endpoint(self):
        f = EndpointsField()
        self.assertRaises(forms.ValidationError, f.clean, u"foo:bar")


class TestRapidSmsForm(VumiTestCase):
    def test_initial_from_config(self):
        initial = RapidSmsForm.initial_from_config({
            "rapidsms_url": "http://www.example.com/",
            "rapidsms_username": "rapid-user",
            "rapidsms_password": "rapid-pass",
            "rapidsms_auth_method": "basic",
            "rapidsms_http_method": "POST",
        })
        self.assertEqual(initial, {
            'rapidsms_url': 'http://www.example.com/',
            'rapidsms_username': 'rapid-user',
            'rapidsms_password': 'rapid-pass',
            'rapidsms_auth_method': 'basic',
            'rapidsms_http_method': 'POST',
            'allowed_endpoints': u'default',
            'auth_token': None,
        })

    def test_initial_from_config_with_endpoints(self):
        initial = RapidSmsForm.initial_from_config({
            'allowed_endpoints': ['default', 'extra']
        })
        self.assertEqual(initial, {
            'allowed_endpoints': u'default,extra',
            'auth_token': None,
        })

    def test_initial_from_config_with_auth_token(self):
        initial = RapidSmsForm.initial_from_config({
            'api_tokens': ["token-1"]
        })
        self.assertEqual(initial, {
            'allowed_endpoints': u'default',
            'auth_token': "token-1",
        })

    def test_to_config(self):
        form = RapidSmsForm({
            'rapidsms_url': 'http://www.example.com/',
            'rapidsms_username': 'rapid-user',
            'rapidsms_password': 'rapid-pass',
            'rapidsms_auth_method': 'basic',
            'rapidsms_http_method': 'POST',
            'allowed_endpoints': 'default, extra',
            'auth_token': u"token-1",
        })
        form.is_valid()
        self.assertEqual(form.errors, {})
        self.assertEqual(form.to_config(), {
            'rapidsms_url': u'http://www.example.com/',
            'rapidsms_username': u'rapid-user',
            'rapidsms_password': u'rapid-pass',
            'rapidsms_auth_method': u'basic',
            'rapidsms_http_method': u'POST',
            'allowed_endpoints': ['default', 'extra'],
            'api_tokens': [u'token-1'],
        })


class TestEditRapidSmsView(VumiTestCase):
    def test_edit_forms(self):
        view = EditRapidSmsView()
        self.assertEqual(view.edit_forms, (
            ('rapidsms', RapidSmsForm),
        ))


class TestConversationViewDefinition(VumiTestCase):
    def test_edit_view(self):
        view_def = ConversationViewDefinition(None)
        self.assertEqual(view_def.edit_view, EditRapidSmsView)
