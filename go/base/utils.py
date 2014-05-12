"""Utilities for the Django parts of Vumi Go."""

import csv
import codecs
from StringIO import StringIO
from urlparse import urlparse, urlunparse

from django import forms
from django.http import Http404, HttpResponse
from django.conf import settings

from go.errors import UnknownConversationType, UnknownRouterType
from go.config import (
    get_conversation_pkg, get_router_pkg,
    obsolete_conversation_types, obsolete_router_types)
from go.base.amqp import connection
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


def sendfile(url, buffering=True, filename=None):
    response = HttpResponse()
    response['X-Accel-Redirect'] = url
    response['X-Accel-Buffering'] = 'yes' if buffering else 'no'

    if filename is not None:
        response['Content-Disposition'] = 'attachment; filename=%s' % (
            filename)

    if settings.DEBUG:
        response.write(url)

    return response


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


class UnicodeDictWriter(object):
    """
    Essentially a copy of the built-in csv.DictWriter with the following
    exceptions:

    1.  The writer used is ``go.base.utils.UnicodeCSVWriter`` instead of
        ``csv.writer``

    2.  The ``extrasaction`` keyword argument has been dropped.
        This class will always raise an exception if the keys in the dict
        do not match the known fieldnames.

    """

    def __init__(self, f, fieldnames, dialect=csv.excel, encoding='utf-8',
                 restval=u''):
        self.fieldnames = fieldnames
        self.restval = restval
        self.writer = UnicodeCSVWriter(f, dialect=dialect, encoding=encoding)

    def writeheader(self):
        header = dict(zip(self.fieldnames, self.fieldnames))
        self.writerow(header)

    def _dict_to_list(self, rowdict):
        wrong_fields = [k for k in rowdict if k not in self.fieldnames]
        if wrong_fields:
            raise ValueError("dict contains fields not in fieldnames: " +
                             ", ".join(wrong_fields))
        return [rowdict.get(key, self.restval) for key in self.fieldnames]

    def writerow(self, rowdict):
        return self.writer.writerow(self._dict_to_list(rowdict))

    def writerows(self, rowdicts):
        rows = []
        for rowdict in rowdicts:
            rows.append(self._dict_to_list(rowdict))
        return self.writer.writerows(rows)


def get_conversation_view_definition(conversation_type, conv=None):
    # Scoped import to avoid circular deps.
    from go.conversation.view_definition import ConversationViewDefinitionBase
    try:
        app_pkg = get_conversation_pkg(
            conversation_type, ['definition', 'view_definition'])
    except UnknownConversationType:
        # To handle obsolete conversations that are still viewable
        if conversation_type not in obsolete_conversation_types():
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
    try:
        router_pkg = get_router_pkg(
            router_type, ['definition', 'view_definition'])
    except UnknownRouterType:
        # To handle obsolete routers that are still viewable
        if router_type not in obsolete_router_types():
            raise
        from go.vumitools.router.definition import (
            RouterDefinitionBase)
        router_def = RouterDefinitionBase(router)
        router_def.router_type = router_type
        return RouterViewDefinitionBase(router_def)
    router_def = router_pkg.definition.RouterDefinition(router)
    if not hasattr(router_pkg, 'view_definition'):
        return RouterViewDefinitionBase(router_def)
    return router_pkg.view_definition.RouterViewDefinition(router_def)


def extract_auth_from_url(url):
    parse_result = urlparse(url)
    if parse_result.username:
        auth = (parse_result.username, parse_result.password)
        url = urlunparse(
            (parse_result.scheme,
             ('%s:%s' % (parse_result.hostname, parse_result.port)
              if parse_result.port
              else parse_result.hostname),
             parse_result.path,
             parse_result.params,
             parse_result.query,
             parse_result.fragment))
        return auth, url
    return None, url
