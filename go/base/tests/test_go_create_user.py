from django.contrib.auth.models import User
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_create_user


class GoCreateUserCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = True

    def test_user_creation(self):
        self.setup_api()
        user_query = User.objects.filter(username='test@user.com')
        self.assertFalse(user_query.exists())
        command = go_create_user.Command()
        command.handle(**{
            'email-address': 'test@user.com',
            'password': '123',
            'name': 'Name',
            'surname': 'Surname',
        })

        self.assertTrue(user_query.exists())
        user = user_query.latest('pk')
        self.assertEqual(user.username, 'test@user.com')
        self.assertEqual(user.email, 'test@user.com')
        self.assertEqual(user.first_name, 'Name')
        self.assertEqual(user.last_name, 'Surname')
        profile = user.get_profile()
        riak_account = profile.get_user_account()
        self.assertEqual(riak_account.key, profile.user_account)
        self.assertEqual(riak_account.username, user.email)
