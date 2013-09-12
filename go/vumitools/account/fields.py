from vumi.persist.fields import Field

from go.vumitools.routing_table import RoutingTable


class RoutingTableField(Field):
    """Field that represents a routing table.

    This is just a JSON object wrapped in a RoutingTable helper class.
    """

    def custom_to_riak(self, value):
        return value._routing_table

    def custom_from_riak(self, raw_value):
        return RoutingTable(raw_value)

    def custom_validate(self, value):
        value.validate_all_entries()
