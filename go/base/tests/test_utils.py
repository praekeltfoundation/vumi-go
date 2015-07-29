# -*- coding: utf-8 -*-
"""Test for go.base.utils."""

import csv
from decimal import Decimal
from StringIO import StringIO
from unittest import TestCase

from go.base.tests.helpers import GoDjangoTestCase
import go.base.utils
from go.base.utils import (
    get_conversation_view_definition, get_router_view_definition,
    UnicodeDictWriter, sendfile, format_currency)
from go.errors import UnknownConversationType, UnknownRouterType


class TestConversationDefinitionHelpers(GoDjangoTestCase):

    def test_get_conversation_view_definition(self):
        view_def = get_conversation_view_definition('bulk_message')
        from go.apps.bulk_message.view_definition import (
            ConversationViewDefinition,)
        self.assertTrue(isinstance(view_def, ConversationViewDefinition))

    def test_get_conversation_view_definition_with_conv(self):
        dummy_conv = object()
        view_def = get_conversation_view_definition('bulk_message', dummy_conv)
        self.assertTrue(view_def._conv_def.conv is dummy_conv)

    def test_get_conversation_view_definition_unknown_conv_type(self):
        self.assertRaises(
            UnknownConversationType,
            get_conversation_view_definition, 'not_droids')

    def test_get_conversation_view_definition_obsolete_conv_type(self):
        self.monkey_patch(
            go.base.utils, 'obsolete_conversation_types',
            lambda: set(['old_conv']))
        view_def = get_conversation_view_definition('old_conv')
        self.assertEqual(view_def._conv_def.conversation_type, 'old_conv')


class TestRouterDefinitionHelpers(GoDjangoTestCase):

    def test_get_router_view_definition(self):
        view_def = get_router_view_definition('keyword')
        from go.routers.keyword.view_definition import (
            RouterViewDefinition,)
        self.assertTrue(isinstance(view_def, RouterViewDefinition))

    def test_get_router_view_definition_with_router(self):
        dummy_router = object()
        view_def = get_router_view_definition('keyword', dummy_router)
        self.assertTrue(view_def._router_def.router is dummy_router)

    def test_get_router_view_definition_unknown_conv_type(self):
        self.assertRaises(
            UnknownRouterType,
            get_router_view_definition, 'not_the_router_we_are_looking_for')

    def test_get_router_view_definition_obsolete_router_type(self):
        self.monkey_patch(
            go.base.utils, 'obsolete_router_types',
            lambda: set(['old_router']))
        view_def = get_router_view_definition('old_router')
        self.assertEqual(view_def._router_def.router_type, 'old_router')


class TestUnicodeDictWriter(TestCase):

    col1 = u'foo'
    col2 = u'bar'
    headers = [col1, col2]

    def test_writeheader(self):
        io = StringIO()
        writer = UnicodeDictWriter(io, self.headers)
        writer.writeheader()
        reader = csv.reader(StringIO(io.getvalue()))
        row = reader.next()
        self.assertEqual(
            [h.encode('utf-8') for h in self.headers],
            row)

    def test_writerow(self):
        io = StringIO()
        writer = UnicodeDictWriter(io, self.headers)
        writer.writeheader()
        writer.writerow({
            self.col1: u'føø',
            self.col2: u'bär',
        })
        reader = csv.reader(StringIO(io.getvalue()))
        reader.next()   # header
        row = reader.next()
        self.assertEqual(
            [u'føø'.encode('utf-8'), u'bär'.encode('utf-8')],
            row)

    def test_writerows(self):
        io = StringIO()
        writer = UnicodeDictWriter(io, self.headers)
        writer.writeheader()
        for i in range(2):
            writer.writerows([{
                self.col1: u'føø',
                self.col2: u'bär',
            }])
        reader = csv.reader(StringIO(io.getvalue()))
        reader.next()   # header
        rows = [row for row in reader]
        self.assertEqual(
            [
                [u'føø'.encode('utf-8'), u'bär'.encode('utf-8')],
                [u'føø'.encode('utf-8'), u'bär'.encode('utf-8')],
            ],
            rows)


class TestSendfile(GoDjangoTestCase):

    def test_sendfile(self):
        resp = sendfile('/foo')
        self.assertEqual(resp['X-Accel-Redirect'], '/foo')
        self.assertEqual(resp['X-Accel-Buffering'], 'yes')

    def test_sendfile_streaming(self):
        resp = sendfile('/foo', buffering=False)
        self.assertEqual(resp['X-Accel-Redirect'], '/foo')
        self.assertEqual(resp['X-Accel-Buffering'], 'no')

    def test_sendfile_debug(self):
        with self.settings(DEBUG=True):
            resp = sendfile('/foo')
            self.assertEqual(resp['X-Accel-Redirect'], '/foo')
            self.assertEqual(resp.content, '/foo')

        with self.settings(DEBUG=False):
            resp = sendfile('/foo')
            self.assertEqual(resp['X-Accel-Redirect'], '/foo')
            self.assertEqual(resp.content, '')


class TestFormatCurrency(GoDjangoTestCase):

    def test_decimal_places(self):
        self.assertEqual(format_currency(Decimal('0.1234'), places=2), '0.12')
        self.assertEqual(
            format_currency(Decimal('0.1234'), places=4), '0.1234')
        self.assertEqual(
            format_currency(Decimal('-0.1234'), places=2), '-0.12')
        self.assertEqual(
            format_currency(Decimal('-0.1234'), places=4), '-0.1234')
        self.assertEqual(format_currency(Decimal('0.1234'), places=0), '0')
        self.assertEqual(format_currency(Decimal('-1.1234'), places=0), '-1')

    def test_currency_symbol(self):
        self.assertEqual(format_currency(Decimal('0.1234'), curr='R'), 'R0.12')
        self.assertEqual(
            format_currency(Decimal('-0.1234'), curr='R'), '-R0.12')

    def test_seperator(self):
        self.assertEqual(
            format_currency(Decimal('123456'), sep=' '), '123 456.00')
        self.assertEqual(
            format_currency(Decimal('-123456'), sep=' '), '-123 456.00')

    def test_decimal_point(self):
        self.assertEqual(
            format_currency(Decimal('123456'), dp='*'), '123,456*00')
        self.assertEqual(
            format_currency(Decimal('-123456'), dp='*'), '-123,456*00')

    def test_positive_symbol(self):
        self.assertEqual(
            format_currency(Decimal('123'), pos='+'), '+123.00')

    def test_negative_symbol(self):
        self.assertEqual(
            format_currency(Decimal('-123'), neg='&'), '&123.00')

    def test_trailing_neg(self):
        self.assertEqual(
            format_currency(Decimal('-123'), trailneg='&'), '-123.00&')
