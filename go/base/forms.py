from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from go.base.models import GoUser


class GoUserCreationForm(UserCreationForm):
    """
    A form that creates a user, with no privileges, from the given email and
    password.
    """

    def __init__(self, *args, **kargs):
        super(GoUserCreationForm, self).__init__(*args, **kargs)
        del self.fields['username']

    class Meta:
        model = GoUser
        fields = ("email",)


class GoUserChangeForm(UserChangeForm):
    """A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    password hash display field.
    """

    def __init__(self, *args, **kargs):
        super(GoUserChangeForm, self).__init__(*args, **kargs)
        del self.fields['username']

    class Meta:
        model = GoUser
