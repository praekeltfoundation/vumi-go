from operator import attrgetter


def get_uniques(contact_store, contact_keys=None,
                    plucker=attrgetter('msisdn')):
    uniques = set()
    contacts_manager = contact_store.contacts
    contact_keys = contact_keys or contact_store.list_contacts()
    for bunch in contacts_manager.load_all_bunches(contact_keys):
        uniques.update([plucker(contact) for contact in bunch])
    return uniques


def get_messages_count(conversations):
    totals = {}
    for conv in conversations:
        totals.setdefault(conv.conversation_type, {})
        totals[conv.conversation_type].setdefault('sent', 0)
        totals[conv.conversation_type].setdefault('received', 0)
        totals[conv.conversation_type]['sent'] += conv.count_sent_messages()
        totals[conv.conversation_type]['received'] += conv.count_replies()
    return totals
