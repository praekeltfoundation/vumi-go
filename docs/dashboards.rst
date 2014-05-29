.. _dashboards:

Vumi Go Dashboards
==================

Vumi has growing support for dashboards. These dashboards are backed by
Graphite and Vumi applies some bucketing of metrics before publishing
to Graphite.

.. note::

    Graphite itself is not directly accessible for 3rd party applications.

Conversation Types supporting Dashboards
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The visualization of dashboards is currently only supported by the
Javascript sandbox conversation type.

The publishing of metrics to a dashboard is supported by the :ref:`http_api`
and the Javascript application conversation types.

Metrics can be shared between conversations if they share the same metrics
store value.

Dashboard Setup
~~~~~~~~~~~~~~~

Dashboards are set up by creating a Javascript application type and
ensuring there is a ``reports`` section that has a JSON dashboard
description.

The report defines:

1. The layout
2. The widgets
3. The metrics

Here is a sample reports.json file from
`go-events-firing-via-http <https://github.com/smn/go-events-firing-via-http>`_

.. code-block:: javascript

    {
      "layout": [
        {
          "type": "diamondash.widgets.lvalue.LValueWidget",
          "time_range": "1d",
          "name": "Last Ping Count",
          "target": {
            "metric_type": "account",
            "store": "default",
            "name": "total_pings",
            "aggregator": "max"
          }
        },
        "new_row",
        {
          "type": "diamondash.widgets.graph.GraphWidget",
          "name": "Ping Counts",
          "width": 6,
          "time_range": "1d",
          "bucket_size": "1h",
          "metrics": [
            {
              "name": "Pings",
              "target": {
                "metric_type": "account",
                "store": "default",
                "name": "total_pings",
                "aggregator": "max"
              }
            }
          ]
        }
      ]
    }

Once a ``reports`` section is created the Vumi Go UI will read the
definition and render the dashboard widgets for you in the Reports page.

Available Widgets
~~~~~~~~~~~~~~~~~

The following widgets are available:

LValueWidget
^^^^^^^^^^^^

Displays two values of a metrics, the current value and the value of the
metric a configurable time ago. The time difference between the two
values is determined by the ``time_range`` value.

.. code-block:: javascript

    {
      "type": "diamondash.widgets.lvalue.LValueWidget",
      "time_range": "1d",
      "name": "Last Ping Count",
      "target": {
        "metric_type": "account",
        "store": "default",
        "name": "total_pings",
        "aggregator": "max"
      }
    }

GraphWidget
^^^^^^^^^^^

Displays a line graph. Multiple metrics can be rendered on the same graph.

.. code-block:: javascript

    {
      "type": "diamondash.widgets.graph.GraphWidget",
      "name": "Ping Counts",
      "width": 6,
      "time_range": "1d",
      "bucket_size": "1h",
      "metrics": [
        {
          "name": "Pings",
          "target": {
            "metric_type": "account",
            "store": "default",
            "name": "total_pings",
            "aggregator": "max"
          }
        }
      ]
    }


HistogramWidget
^^^^^^^^^^^^^^^

Display a histogram of the metrics.

.. code-block:: javascript

    {
        "type": "diamondash.widgets.histogram.HistogramWidget",
        "name": "Total Pings (Histogram)",
        "target": {
          "metric_type": "account",
          "store": "default",
          "name": "total_pings",
          "aggregator": "max"
        },
        "time_range": "1h",
        "bucket_size": "5m",
        "width": 6
    }


PieWidget
^^^^^^^^^

Display a pie chart of metric values.

.. code-block:: javascript

    {
        "type": "diamondash.widgets.pie.PieWidget",
        "name": "Total Pings (Pie)",
        "time_range": "1d",
        "width": 6,
        "metrics": [
          {
            "target": {
              "metric_type": "account",
              "store": "default",
              "name": "total_pings",
              "aggregator": "max"
            }
          }
        ]
    }
