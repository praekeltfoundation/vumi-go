"""Utilities for the Django parts of Vumi Go."""

from django import forms
from django.http import Http404
from django.conf import settings

from go.vumitools.api import VumiUserApi


def conversation_or_404(user_api, key):
    conversation = user_api.conversation_store.get_conversation_by_key(key)
    if conversation is None:
        raise Http404("Conversation not found.")
    return user_api.wrap_conversation(conversation)


def vumi_api_for_user(user):
    """Return a Vumi API instance for the given user."""
    return VumiUserApi.from_config_sync(user.get_profile().user_account,
                                        settings.VUMI_API_CONFIG)


def padded_queryset(queryset, size=6, padding=None):
    nr_of_results = queryset.count()
    if nr_of_results >= size:
        return queryset[:size]

    filler = [padding] * (size - nr_of_results)
    results = list(queryset)
    results.extend(filler)
    return results


def make_read_only_formset(formset):
    for form in formset:
        make_read_only_form(form)
    return formset


def make_read_only_form(form):
    """turn all fields in a form readonly"""
    for field_name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget,
                (forms.RadioSelect, forms.CheckboxSelectMultiple)):
            widget.attrs.update({
                'disabled': 'disabled'
            })
        else:
            widget.attrs.update({
                'readonly': 'readonly'
            })
    return form


def page_range_window(page, padding):
    """
    Sometimes the page range is bigger than we're willing to display in the
    UI and if that's the case we want to switch to only showing +padding &
    -padding pages for the paginator.
    """
    current_page = page.number
    if page.paginator.num_pages < padding:
        return range(1, page.paginator.num_pages + 1)
    elif current_page - padding < 1:
        return range(1, (padding * 2))
    elif current_page + padding > page.paginator.num_pages:
        return range(page.paginator.num_pages - (padding * 2) + 2,
            page.paginator.num_pages + 1)
    else:
        return range(current_page - padding + 1, current_page + padding)
