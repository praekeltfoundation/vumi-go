"""Utilities for the Django parts of Vumi Go."""

import csv
import codecs
from StringIO import StringIO
from operator import itemgetter

from django import forms
from django.http import Http404
from django.conf import settings

from go.base.amqp import connection
from go.errors import UnknownConversationType, UnknownRouterType
from go.vumitools.api import VumiApi


def conversation_or_404(user_api, key):
    conversation = user_api.conversation_store.get_conversation_by_key(key)
    if conversation is None:
        raise Http404("Conversation not found.")
    return user_api.wrap_conversation(conversation)


def router_or_404(user_api, key):
    router = user_api.router_store.get_router_by_key(key)
    if router is None:
        raise Http404("Router not found.")
    return router


def vumi_api():
    """Return a Vumi API instance."""
    return VumiApi.from_config_sync(settings.VUMI_API_CONFIG, connection)


def vumi_api_for_user(user, api=None):
    """Return a Vumi API instance for the given user."""
    if api is None:
        api = vumi_api()
    return api.get_user_api(user.get_profile().user_account)


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


# Copied from http://docs.python.org/2/library/csv.html#examples
class UnicodeCSVWriter(object):
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# As explained at
# http://stackoverflow.com/questions/1143671/
# python-sorting-list-of-dictionaries-by-multiple-keys
def multikeysort(items, columns):
    comparers = [((itemgetter(col[1:].strip()), -1)
                    if col.startswith('-')
                    else (itemgetter(col.strip()), 1)) for col in columns]

    def comparer(left, right):
        for fn, mult in comparers:
            result = cmp(fn(left), fn(right))
            if result:
                return mult * result
        else:
            return 0
    return sorted(items, cmp=comparer)


def configured_conversation_types():
    return dict((a['namespace'], a['display_name'])
                for a in settings.VUMI_INSTALLED_APPS.itervalues())


def configured_router_types():
    return dict((a['namespace'], a['display_name'])
                for a in settings.VUMI_INSTALLED_ROUTERS.itervalues())


def get_conversation_pkg(conversation_type, fromlist):
    for module, data in settings.VUMI_INSTALLED_APPS.iteritems():
        if data['namespace'] == conversation_type:
            app_pkg = __import__(module,
                                 fromlist=fromlist)
            return app_pkg
    raise UnknownConversationType(
        "Can't find python package for conversation type: %r"
        % (conversation_type,))


def get_router_pkg(router_type, fromlist=()):
    for module, data in settings.VUMI_INSTALLED_ROUTERS.iteritems():
        if data['namespace'] == router_type:
            router_pkg = __import__(module,
                                 fromlist=fromlist)
            return router_pkg
    raise UnknownRouterType(
        "Can't find python package for router type: %r"
        % (router_type,))


def get_conversation_definition(conversation_type, conv=None):
    app_pkg = get_conversation_pkg(conversation_type, ['definition'])
    return app_pkg.definition.ConversationDefinition(conv)


def get_router_definition(router_type, router=None):
    router_pkg = get_router_pkg(router_type, ['definition'])
    return router_pkg.definition.RouterDefinition(router)


def get_conversation_view_definition(conversation_type, conv=None):
    # Scoped import to avoid circular deps.
    from go.conversation.view_definition import ConversationViewDefinitionBase
    try:
        app_pkg = get_conversation_pkg(
            conversation_type, ['definition', 'view_definition'])
    except UnknownConversationType:
        # To handle obsolete conversations that are still running.
        if conversation_type not in settings.VUMI_OBSOLETE_APPS:
            raise
        from go.vumitools.conversation.definition import (
            ConversationDefinitionBase)
        conv_def = ConversationDefinitionBase(conv)
        conv_def.conversation_type = conversation_type
        return ConversationViewDefinitionBase(conv_def)
    conv_def = app_pkg.definition.ConversationDefinition(conv)
    if not hasattr(app_pkg, 'view_definition'):
        return ConversationViewDefinitionBase(conv_def)
    return app_pkg.view_definition.ConversationViewDefinition(conv_def)


def get_router_view_definition(router_type, router=None):
    # Scoped import to avoid circular deps.
    from go.router.view_definition import RouterViewDefinitionBase
    router_pkg = get_router_pkg(router_type, ['definition', 'view_definition'])
    router_def = router_pkg.definition.RouterDefinition(router)
    if not hasattr(router_pkg, 'view_definition'):
        return RouterViewDefinitionBase(router_def)
    return router_pkg.view_definition.RouterViewDefinition(router_def)
