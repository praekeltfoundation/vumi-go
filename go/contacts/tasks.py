import os.path

from celery.task import task

from django.conf import settings

from go.vumitools.api import VumiUserApi
from go.contacts.utils import parse_contacts_csv_file


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

@task(ignore_result=True)
def import_csv_file(account_key, group_key, csv_path, field_names, has_header):
    print 'importing csv file'
    api = VumiUserApi.from_config(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)

    # open in Universal mode to allow us to read files with Windows,
    # MacOS9 & Unix line-endings
    full_path = os.path.join(settings.MEDIA_ROOT, csv_path)

    with open(full_path, 'rU') as csv_file:
        for csv_data in parse_contacts_csv_file(csv_file, field_names,
                                            has_header):
            [count, contact_dictionary] = csv_data

            # Make sure we set this group they're being uploaded in to
            groups = contact_dictionary.setdefault('groups', [])
            groups.append(group.key)

            contact_store.new_contact(**contact_dictionary)
    print 'done'
