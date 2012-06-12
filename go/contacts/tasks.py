from celery.task import task

from django.conf import settings

from go.vumitools.api import VumiUserApi


@task(ignore_result=True)
def delete_group(account_key, group_key):
    api = VumiUserApi(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    for contact in group.backlinks.contacts():
        contact.groups.remove(group)
        contact.save()
    group.delete()
