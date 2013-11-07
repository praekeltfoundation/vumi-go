from celery.task import task

from django.contrib.auth import get_user_model

from go.account.utils import send_user_account_summary


@task(ignore_result=True)
def update_account_details(user_id, first_name=None, last_name=None,
                           new_password=None, email_address=None, msisdn=None,
                           confirm_start_conversation=None,
                           email_summary=None):
    user = get_user_model().objects.get(pk=user_id)
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
    account.email_summary = email_summary
    account.save()


@task(ignore_result=True)
def send_scheduled_account_summary(interval):
    users = get_user_model().objects.all()
    for user in users:
        user_account = user.get_profile().get_user_account()
        if user_account.email_summary == interval:
            send_user_account_summary(user)
