from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED

from celery.task import task

from django.conf import settings
from django.core.mail import EmailMessage

from go.vumitools.api import VumiUserApi
from go.base.models import UserProfile

from go.apps.surveys.view_definition import get_poll_config


@task(ignore_result=True)
def export_vxpolls_data(account_key, conversation_key, include_old_questions):
    """
    Export the data from a vxpoll and send it as a zipped attachment
    via email.
    """
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    user_profile = UserProfile.objects.get(user_account=account_key)
    conversation = api.get_wrapped_conversation(conversation_key)

    poll_id = 'poll-%s' % (conversation.key,)
    pm, poll_data = get_poll_config(poll_id)
    poll = pm.get(poll_id)
    csv_data = pm.export_user_data_as_csv(
        poll, include_old_questions=include_old_questions)
    email = EmailMessage(
        'Survey export for: %s' % (conversation.name,),
        'Please find the data for the survey %s attached.\n' % (
            conversation.name),
        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])

    zipio = StringIO()
    zf = ZipFile(zipio, "a", ZIP_DEFLATED)
    zf.writestr("survey-data-export.csv", csv_data)
    zf.close()

    email.attach('survey-data-export.zip', zipio.getvalue(),
                 'application/zip')
    email.send()
