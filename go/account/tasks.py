from celery.task import task
from django.contrib.auth.models import User


@task(ignore_result=True)
def update_account_details(user_id, first_name=None, last_name=None,
    new_password=None, email_address=None, msisdn=None,
    confirm_start_conversation=None):
    user = User.objects.get(pk=user_id)
    profile = user.get_profile()
    account = profile.get_user_account()

    if new_password:
        user.set_password(new_password)
    user.first_name = first_name
    user.last_name = last_name
    user.email = email_address
    user.save()

    account.msisdn = unicode(msisdn)
    account.confirm_start_conversation = confirm_start_conversation
    account.save()
