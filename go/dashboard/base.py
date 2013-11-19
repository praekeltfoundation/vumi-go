import json
from urlparse import urljoin

import requests
from django.conf import settings


def is_collection(obj):
    return (
        isinstance(obj, dict)
        or isinstance(obj, list)
        or isinstance(obj, set)
        or isinstance(obj, tuple))


def is_mutable_collection(obj):
    return (
        isinstance(obj, dict)
        or isinstance(obj, list)
        or isinstance(obj, set))


def collection_items(collection):
    if isinstance(collection, dict):
        items = collection.iteritems()
    else:
        items = enumerate(collection)
    return items


def visit_dicts(collection, fn):
    is_mutable = is_mutable_collection(collection)

    for key, value in collection_items(collection):
        if is_collection(value):
            visit_dicts(value, fn)

            if is_mutable and isinstance(value, dict):
                collection[key] = fn(value)


class DashboardSyncError(Exception):
    """
    Raised when we fail to sync the dashboard with diamondash.
    """


class DashboardParseError(Exception):
    """
    Raised when dashboard data cannot be parsed into a something that can be
    given to diamondash.
    """


class Dashboard(object):
    def __init__(self, name, title, widgets):
        self.name = name
        self.title = title
        self.widgets = widgets

    def _api_url(self):
        return urljoin(settings.DIAMONDASH_URL, 'dashboards')

    def _raw_serialize(self):
        return {
            'name': self.name,
            'title': self.title,
            'widgets': self.widgets.serialize()
        }

    def sync(self):
        """
        Ensures the dashboard exists on diamondash's side
        """
        response = requests.put(
            self._api_url(),
            data=json.dumps(self._raw_serialize()))

        try:
            response.raise_for_status()
        except Exception, e:
            DashboardSyncError("Dashboard sync failed: %s" % e)

        content = json.loads(response.content)

        if not content['success']:
            raise DashboardSyncError(
                "Dashboard sync failed: (%s) %s" %
                (response.code, content['message']))

        self.config = json.loads(content['data'])

    def serialize(self):
        return self.config


class DashboardLayout(object):
    def __init__(self, entities):
        self.entities = []

        for entity in entities:
            self.add_entity(entity)

    def handle_metric(self, target):
        handler_name = "handle_%s_metric" % target['metric_type']
        handler = getattr(self, handler_name, None)

        if handler is None:
            raise DashboardParseError(
                "No dashboard metric handler found for metric_type '%s'"
                % target['metric_type'])

        return handler(target)

    def parse_widget_metrics(self, widget):
        def traverse(collection, key):
            if 'metric_type' in collection:
                collection = self.handle_metric(collection)
            return collection

        visit_dicts(widget, traverse)

    def add_widget(self, widget):
        self.parse_widget_metrics(widget)
        self.entities.append(widget)

    def new_row(self):
        self.entities.append('new_row')

    def add_entity(self, entity):
        if entity == 'new_row':
            self.new_row()
        else:
            self.add_entity(entity)

    def serialize(self):
        return self.entities
