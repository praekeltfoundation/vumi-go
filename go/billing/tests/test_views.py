""" Tests for PDF billing statement generation """
from decimal import Decimal

import mock
from django.core.urlresolvers import reverse

from go.base.tests.helpers import DjangoVumiApiHelper, GoDjangoTestCase
from go.billing.models import Account

from .helpers import mk_statement, get_line_items


class TestStatementView(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user(superuser=False)

        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def mk_statement(self, **kw):
        return mk_statement(self.account, **kw)

    def get_statement(self, username, statement):
        client = self.vumi_helper.get_client(username=username)
        return client.get(reverse('billing:html_statement',
                                  kwargs={'statement_id': statement.id}))

    def check_statement_accessible_by(self, username, statement):
        response = self.get_statement(username, statement)
        self.assertEqual(response.status_code, 200)

    def check_statement_not_accessible_by(self, username, statement):
        response = self.get_statement(username, statement)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/html')

    @mock.patch('go.billing.settings.STATEMENT_CONTACT_DETAILS', {
        'tel': '27.11.123.4567',
        'website': 'www.example.com',
        'email': 'http://foo@example.com',
    })
    def test_statement_contact_details(self):
        statement = self.mk_statement()
        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertContains(response, '>www.example.com<')
        self.assertContains(response, '>27.11.123.4567<')
        self.assertContains(response, '>http://foo@example.com<')

    def test_statement_biller_title(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertContains(response, '>Pool 1 (USSD)<')

    def test_statement_biller_title_none_channel_type(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': None,
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertContains(response, '>Pool 1<')

    def test_statement_channel_title(self):
        statement = self.mk_statement(items=[{'channel': 'Tag 1.1'}])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertContains(response, '>Tag 1.1<')

    def test_statement_descriptions(self):
        statement = self.mk_statement(items=[
            {'description': 'Messages Received'},
            {'description': 'Messages Sent'}])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertContains(response, '>Messages Received<')
        self.assertContains(response, '>Messages Sent<')

    def test_statement_description_nones(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'description': None
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertNotContains(response, '>None<')

    @mock.patch('go.billing.settings.DOLLAR_DECIMAL_PLACES', 3)
    def test_statement_costs(self):
        statement = self.mk_statement(items=[{
            'credits': Decimal('200.0'),
            'unit_cost': Decimal('123.456'),
            'cost': Decimal('679.012'),
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertContains(response, '>200.00<')
        self.assertContains(response, '>1.234<')
        self.assertContains(response, '>6.790<')

    def test_statement_cost_nones(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'credits': None
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)
        self.assertNotContains(response, '>None<')

    def test_statement_billers(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Received',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 2',
            'channel_type': 'SMS',
            'channel': 'Tag 2.1',
            'description': 'Messages Received',
            'cost': Decimal('200.0'),
            'credits': Decimal('250.0'),
        }, {
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.2',
            'description': 'Messages Received',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 2',
            'channel_type': 'SMS',
            'channel': 'Tag 2.2',
            'description': 'Messages Received',
            'cost': Decimal('200.0'),
            'credits': Decimal('250.0'),
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertEqual(response.context['billers'], [{
            'name': u'Pool 1',
            'channel_type': u'USSD',
            'sections': [{
                'name': u'Tag 1.1',
                'items': list(
                    get_line_items(statement).filter(channel='Tag 1.1')),
                'totals': {
                    'cost': Decimal('150.0'),
                    'credits': Decimal('200.0'),
                }
            }, {
                'name': u'Tag 1.2',
                'items': list(
                    get_line_items(statement).filter(channel='Tag 1.2')),
                'totals': {
                    'cost': Decimal('150.0'),
                    'credits': Decimal('200.0'),
                }
            }]
        }, {
            'name': u'Pool 2',
            'channel_type': u'SMS',
            'sections': [{
                'name': u'Tag 2.1',
                'items': list(
                    get_line_items(statement).filter(channel='Tag 2.1')),
                'totals': {
                    'cost': Decimal('200.0'),
                    'credits': Decimal('250.0'),
                }
            }, {
                'name': u'Tag 2.2',
                'items': list(
                    get_line_items(statement).filter(channel='Tag 2.2')),
                'totals': {
                    'cost': Decimal('200.0 '),
                    'credits': Decimal('250.0'),
                }
            }],
        }])

    def test_statement_section_totals(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Received',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Sent',
            'cost': Decimal('150.0'),
            'credits': None,
        }, {
            'billed_by': 'Pool 1',
            'channel_type': 'SMS',
            'channel': 'Tag 1.2',
            'description': 'Messages Received',
            'cost': Decimal('200.0'),
            'credits': Decimal('250.0'),
        }, {
            'billed_by': 'Pool 1',
            'channel_type': 'SMS',
            'channel': 'Tag 1.2',
            'description': 'Messages Sent',
            'cost': Decimal('200.0'),
            'credits': None,
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        totals = [
            section['totals']
            for section in response.context['billers'][0]['sections']]

        self.assertEqual(totals, [{
            'cost': Decimal('300.0'),
            'credits': Decimal('200.0'),
        }, {
            'cost': Decimal('400.0'),
            'credits': Decimal('250.0'),
        }])

    def test_statement_section_totals_nones(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Received',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 2',
            'channel_type': 'SMS',
            'channel': 'Tag 2.1',
            'description': 'Messages Received',
            'cost': Decimal('200.0'),
            'credits': None,
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertEqual(response.context['totals'], {
            'cost': Decimal('350.0'),
            'credits': Decimal('200.0'),
        })

    def test_statement_grand_totals(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Received',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Sent',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 2',
            'channel_type': 'SMS',
            'channel': 'Tag 2.1',
            'description': 'Messages Received',
            'cost': Decimal('200.0'),
            'credits': Decimal('250.0'),
        }, {
            'billed_by': 'Pool 2',
            'channel_type': 'SMS',
            'channel': 'Tag 2.1',
            'description': 'Messages Sent',
            'cost': Decimal('200.0'),
            'credits': Decimal('250.0'),
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertEqual(response.context['totals'], {
            'cost': Decimal('700.0'),
            'credits': Decimal('900.0'),
        })

    def test_statement_grand_totals_nones(self):
        statement = self.mk_statement(items=[{
            'billed_by': 'Pool 1',
            'channel_type': 'USSD',
            'channel': 'Tag 1.1',
            'description': 'Messages Received',
            'cost': Decimal('150.0'),
            'credits': Decimal('200.0'),
        }, {
            'billed_by': 'Pool 2',
            'channel_type': 'SMS',
            'channel': 'Tag 2.1',
            'description': 'Messages Received',
            'cost': Decimal('200.0'),
            'credits': None,
        }])

        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)

        self.assertEqual(response.context['totals'], {
            'cost': Decimal('350.0'),
            'credits': Decimal('200.0'),
        })

    @mock.patch('go.billing.settings.SYSTEM_BILLER_NAME', 'Serenity')
    def test_statement_billers_system_at_end(self):
        statement = self.mk_statement(items=[
            {'billed_by': 'Z'},
            {'billed_by': 'Serenity'}
        ])
        user = self.user_helper.get_django_user()
        response = self.get_statement(user, statement)
        self.assertEqual(response.context['billers'][-1]['name'], 'Serenity')

    def test_statement_accessable_by_owner(self):
        statement = self.mk_statement()
        self.check_statement_accessible_by(
            self.user_helper.get_django_user(), statement)

    def test_statement_accessable_by_superuser(self):
        statement = self.mk_statement()
        self.vumi_helper.make_django_user(
            email='super@example.com', superuser=True)
        self.check_statement_accessible_by('super@example.com', statement)

    def test_statement_accessable_by_staff(self):
        statement = self.mk_statement()
        user_helper = self.vumi_helper.make_django_user(
            email='staff@example.com')
        user = user_helper.get_django_user()
        user.is_staff = True
        user.save()
        self.check_statement_accessible_by('staff@example.com', statement)

    def test_statement_hidden_when_not_accessible(self):
        statement = self.mk_statement()
        self.vumi_helper.make_django_user(
            email='other.user@example.com')
        self.check_statement_not_accessible_by(
            'other.user@example.com', statement)
