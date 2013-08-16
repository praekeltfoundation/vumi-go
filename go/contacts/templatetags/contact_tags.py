from django import template


register = template.Library()


@register.simple_tag
def size_of_group(contact_store, group):
    return contact_store.count_contacts_for_group(group)
