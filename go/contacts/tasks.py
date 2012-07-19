from celery.task import task

from django.conf import settings

from go.vumitools.api import VumiUserApi


@task(ignore_result=True)
def delete_group(account_key, group_key):
    # NOTE: There is a small chance that this can break when running in
    #       production if the load is high and the queues have backed up.
    #       What could happen is that while contacts are being removed from
    #       the group, new contacts could have been added before the group
    #       has been deleted. If this happens those contacts will have
    #       secondary indexes in Riak pointing to a non-existent Group.
    api = VumiUserApi.from_config(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    for contact in group.backlinks.contacts():
        contact.groups.remove(group)
        contact.save()
    group.delete()
