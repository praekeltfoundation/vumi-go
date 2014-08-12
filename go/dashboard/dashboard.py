from functools import wraps

from vumi.blinkenlights.metrics import Metric

from go.dashboard import client
from go.vumitools.metrics import (
    get_account_metric_prefix, get_conversation_metric_prefix)


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


def ensure_handler_fields(*fields):
    def decorator(fn):
        @wraps(fn)
        def wrapper(self, target):
            missing_fields = [f for f in fields if f not in target]
            if missing_fields:
                raise DashboardParseError(
                    "Dashboard layout handler '%s' is missing fields: %s" %
                    (fn.__name__, missing_fields))
            return fn(self, target)
        return wrapper
    return decorator


class DashboardError(Exception):
    """
    Raised when an error is encountered while building or usnig a dashboard.
    """


class DashboardSyncError(DashboardError):
    """
    Raised when we fail to sync the dashboard with diamondash.
    """


class DashboardParseError(DashboardError):
    """
    Raised when dashboard data cannot be parsed into something that can be
    given to diamondash.
    """


class Dashboard(object):
    def __init__(self, name, layout):
        self.diamondash_api = client.get_diamondash_api()
        self.name = name
        self.layout = layout
        self.config = None

    def _get_raw_config(self):
        return {
            'name': self.name,
            'widgets': self.layout.get_config()
        }

    def sync(self):
        """
        Ensures the dashboard exists on diamondash's side
        """
        try:
            raw_config = self._get_raw_config()
            self.config = self.diamondash_api.replace_dashboard(raw_config)
        except Exception as e:
            raise DashboardSyncError("Dashboard sync failed: %s" % e)

    def get_config(self):
        if self.config is None:
            raise DashboardError(
                "Could not retrieve dashboard config, "
                "dashboard has not yet been synced")

        return self.config


class DashboardLayout(object):
    def __init__(self, entities=None):
        self.entities = []

        for entity in (entities or []):
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
        def traverse(collection):
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
            self.add_widget(entity)

    def get_config(self):
        return self.entities


def get_metric_diamondash_target(prefix, metric_name, aggregator_name):
    return "%s%s.%s" % (prefix, metric_name, aggregator_name)


class ConversationReportsLayout(DashboardLayout):
    def __init__(self, conv, entities=None):
        self.conv = conv
        super(ConversationReportsLayout, self).__init__(entities)

    def aggregator_from_target(self, target):
        aggregator = target.get('aggregator')
        # FIXME: We don't always get the aggregator in the target. In order to
        #        handle this, we get the name of the (first) default aggregator
        #        from Metric if the aggregator is not specified.
        if aggregator is None:
            aggregator = Metric.DEFAULT_AGGREGATORS[0].name
        return aggregator

    @ensure_handler_fields('name')
    def handle_conversation_metric(self, target):
        prefix = get_conversation_metric_prefix(self.conv)
        return get_metric_diamondash_target(
            prefix, target['name'], self.aggregator_from_target(target))

    @ensure_handler_fields('store', 'name')
    def handle_account_metric(self, target):
        prefix = get_account_metric_prefix(
            self.conv.user_account.key, target['store'])
        return get_metric_diamondash_target(
            prefix, target['name'], self.aggregator_from_target(target))
