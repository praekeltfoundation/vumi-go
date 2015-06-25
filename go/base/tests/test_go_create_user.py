from django.contrib.auth import get_user_model

from go.base.management.commands import go_create_user
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoCreateUserCommand(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.command = go_create_user.Command()

    def test_user_creation(self):
        user_model = get_user_model()
        user_query = user_model.objects.filter(email='test@user.com')
        self.assertFalse(user_query.exists())
        self.command.handle(**{
            'email-address': 'test@user.com',
            'password': '123',
            'name': 'Name',
            'surname': 'Surname',
        })

        self.assertTrue(user_query.exists())
        user = user_query.latest('pk')
        self.assertEqual(user.email, 'test@user.com')
        self.assertEqual(user.first_name, 'Name')
        self.assertEqual(user.last_name, 'Surname')
        profile = user.get_profile()
        riak_account = profile.get_user_account(
            self.vumi_helper.get_vumi_api())
        self.assertEqual(riak_account.key, profile.user_account)
        self.assertEqual(riak_account.username, user.email)
