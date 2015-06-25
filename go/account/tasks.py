from celery.task import task

from django.contrib.auth import get_user_model

from go.account.utils import send_user_account_summary
from go.base.utils import vumi_api, vumi_api_for_user


@task(ignore_result=True)
def update_account_details(user_id, first_name=None, last_name=None,
                           new_password=None, email_address=None, msisdn=None,
                           confirm_start_conversation=None,
                           email_summary=None):
    user = get_user_model().objects.get(pk=user_id)
    user_api = vumi_api_for_user(user)
    try:
        account = user_api.get_user_account()

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
    finally:
        user_api.cleanup()


@task(ignore_result=True)
def send_scheduled_account_summary(interval):
    users = get_user_model().objects.all()
    api = vumi_api()
    try:
        for user in users:
            user_account = vumi_api_for_user(user, api).get_user_account()
            if user_account.email_summary == interval:
                send_user_account_summary(user)
    finally:
        api.cleanup()
