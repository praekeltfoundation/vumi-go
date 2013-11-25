this["JST"] = this["JST"] || {};

this["JST"]["diamondash/widgets/graph/legend.jst"] = function(obj) {
obj || (obj = {});
var __t, __p = '', __e = _.escape, __j = Array.prototype.join;
function print() { __p += __j.call(arguments, '') }
with (obj) {
__p += '<div class="row">\n  ';
 self.model.get('metrics').each(function(m) { ;
__p += '\n    <div class="legend-item col-md-6" data-metric-id="' +
((__t = ( m.get('id') )) == null ? '' : __t) +
'">\n      <span class="swatch"></span>\n      <span class="title">' +
((__t = ( m.get('title') )) == null ? '' : __t) +
'</span>\n      <span class="value">' +
((__t = ( self.format(x ? m.valueAt(x) : m.lastValue()) )) == null ? '' : __t) +
'</span>\n    </div>\n  ';
 }); ;
__p += '\n</div>\n';

}
return __p
};

this["JST"]["diamondash/widgets/lvalue/lvalue.jst"] = function(obj) {
obj || (obj = {});
var __t, __p = '', __e = _.escape;
with (obj) {
__p += '<h1 class="last"></h1>\n<div class="' +
((__t = ( change )) == null ? '' : __t) +
' change">\n  <span class="diff">' +
((__t = ( diff )) == null ? '' : __t) +
'</span>\n  <span class="percentage">(' +
((__t = ( percentage )) == null ? '' : __t) +
')</span>\n</div>\n<div class="time">\n  <span class="from">from ' +
((__t = ( from )) == null ? '' : __t) +
'</span>\n  <span class="to">to ' +
((__t = ( to )) == null ? '' : __t) +
'<span>\n</div>\n';

}
return __p
};

this["JST"]["diamondash/client/jst/dashboard.jst"] = function(obj) {
obj || (obj = {});
var __t, __p = '', __e = _.escape, __j = Array.prototype.join;
function print() { __p += __j.call(arguments, '') }
with (obj) {
__p += '<div class="container">\n  <div class="row">\n    <div class="dashboard-body col-md-12">\n      ';
 dashboard.model.get('rows').each(function(row) { ;
__p += '\n      <div class="row">\n        ';
 row.get('widgets').each(function(widget) { ;
__p += '\n          <div\n           data-widget="' +
((__t = ( widget.id )) == null ? '' : __t) +
'"\n           class="' +
((__t = ( widget.get('type_name') )) == null ? '' : __t) +
' widget col-md-' +
((__t = ( widget.get('width') )) == null ? '' : __t) +
'">\n            <div class="widget-head"><h4>' +
((__t = ( widget.get('title') )) == null ? '' : __t) +
'</h4></div>\n            <div class="widget-body"></div>\n          </div>\n        ';
 }); ;
__p += '\n      </div>\n      ';
 }); ;
__p += '\n    </div>\n  </div>\n</div>\n';

}
return __p
};
window.diamondash = function() {
  function url() {
    var parts = _(arguments).toArray();
    parts.unshift(diamondash.config.get('url_prefix'));
    parts.unshift('/');
    return diamondash.utils.joinPaths.apply(this, parts);
  }

  return {
    url: url
  };
}.call(this);

diamondash.utils = function() {
  var re = {};
  re.leadingSlash = /^\/+/;
  re.trailingSlash = /\/+$/;

  function objectByName(name, that) {
    return _(name.split( '.' )).reduce(
      function(obj, propName) { return obj[propName]; },
      that || this);
  }

  function maybeByName(obj, that) {
    return _.isString(obj)
      ? objectByName(obj, that)
      : obj;
  }

  function functor(obj) {
    return !_.isFunction(obj)
      ? function() { return obj; }
      : obj;
  }

  function bindEvents(events, that) {
    that = that || this;

    _(events).each(function(fn, e) {
      var parts = e.split(' '),
          event = parts[0],
          entity = parts[1];

      if (entity) { that.listenTo(objectByName(entity, that), event, fn); }
      else { that.on(event, fn); }
    });
  }

  function snap(x, start, step) {
    var i = Math.round((x - start) / step);
    return start + (step * i);
  }

  function d3Map(selection, fn) {
    var values = [];

    selection.each(function(d, i) {
      values.push(fn.call(this, d, i));
    });

    return values;
  }

  function joinPaths() {
    var parts = _(arguments).compact();

    var result = _(parts)
      .chain()
      .map(function(p) {
        return p
          .replace(re.leadingSlash, '')
          .replace(re.trailingSlash, '');
      })
      .compact()
      .value()
      .join('/');

    var first = parts.shift();
    if (_(first).first() == '/') { result = '/' + result; }

    var last = parts.pop() || (first != '/' ? first : '');
    if (_(last).last() == '/') { result = result + '/'; }

    return result;
  }

  function basicAuth(username, password) {
    return 'Basic ' + Base64.encode(username + ':' + password);
  }

  return {
    functor: functor,
    objectByName: objectByName,
    maybeByName: maybeByName,
    bindEvents: bindEvents,
    snap: snap,
    d3Map: d3Map,
    joinPaths: joinPaths,
    basicAuth: basicAuth
  };
}.call(this);

diamondash.components = function() {
  return {
  };
}.call(this);

diamondash.components.structures = function() {
  var utils = diamondash.utils;

  function Extendable() {}
  Extendable.extend = Backbone.Model.extend;

  var Eventable = Extendable.extend(Backbone.Events);

  var ColorMaker = Extendable.extend({
    constructor: function(options) {
      options = _({}).defaults(options, this.defaults);
      this.colors = options.scale.domain(d3.range(0, options.n));
      this.i = 0;
    },

    defaults: {
      scale: d3.scale.category10(),
      n: 10
    },

    next: function() {
      return this.colors(this.i++);
    }
  });

  Registry = Eventable.extend({
    constructor: function(items) {
      this.items = {};
      
      _(items || {}).each(function(data, name) {
        this.add(name, data);
      }, this);
    },

    processAdd: function(name, data) {
      return data;
    },

    processGet: function(name, data) {
      return data;
    },

    add: function(name, data) {
      if (name in this.items) {
        throw new Error("'" + name + "' is already registered.");
      }

      data = this.processAdd(name, data);
      this.trigger('add', name, data);
      this.items[name] = data;
    },

    get: function(name) {
      return this.processGet(name, this.items[name]);
    },

    remove: function(name) {
      var data = this.items[name];
      this.trigger('remove', name, data);
      delete this.items[name];
      return data;
    }
  });

  var ViewSet = Extendable.extend.call(Backbone.ChildViewContainer, {
    keyOf: function(view) {
      return _(view).result('id');
    },

    ensureKey: function(obj) {
      return obj instanceof Backbone.View
        ? this.keyOf(obj)
        : obj;
    },

    get: function(key) {
      return this.findByCustom(key);
    },

    make: function(options) {
      return new Backbone.View(options);
    },

    ensure: function(obj) {
      return !(obj instanceof Backbone.View)
        ? this.make(obj)
        : obj;
    },

    add: function(obj, key) {
      var view = this.ensure(obj);
      if (typeof key == 'undefined') { key = this.keyOf(view); }
      return ViewSet.__super__.add.call(this, view, key);
    },

    remove: function(obj) {
      var view = this.get(this.ensureKey(obj));
      if (view) { ViewSet.__super__.remove.call(this, view); }
      return this;
    },

    each: function(fn, that) {
      that = that || this;

      for (var k in this._indexByCustom) {
        fn.call(that, this.get(k), k);
      }
    }
  });

  ViewSet.extend = Extendable.extend;

  var SubviewSet = ViewSet.extend({
    parentAlias: 'parent',

    constructor: function(options) {
      SubviewSet.__super__.constructor.call(this);

      this.parent = options[this.parentAlias];
      this[this.parentAlias] = this.parent;
    },

    selector: function(key) {
      return key;
    },

    render: function() {
      this.each(function(view, key) {
        view.setElement(this.parent.$(this.selector(key)), true);
      }, this);

      this.apply('render', arguments);
    }
  });

  return {
    Extendable: Extendable,
    Eventable: Eventable,
    Registry: Registry,
    ColorMaker: ColorMaker,
    ViewSet: ViewSet,
    SubviewSet: SubviewSet
  };
}.call(this);

diamondash.models = function() {
  var DiamondashConfigModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'auth',
      relatedModel: 'diamondash.models.AuthModel',
      includeInJSON: false
    }],

    defaults: {
      auth: {}
    }
  });

  var AuthModel = Backbone.RelationalModel.extend({
    defaults: {
      all: false
    },

    stringify: function() {
      return diamondash.utils.basicAuth(
        this.get('username'),
        this.get('password'));
    }
  });

  var Model = Backbone.RelationalModel.extend({
    sync: function(method, model, options) {
      options = options || {};

      if (options.auth || diamondash.config.get('auth').get('all')) {
        options.beforeSend = function(xhr) {
          xhr.setRequestHeader(
            'Authorization',
            diamondash.config.get('auth').stringify());
        };
      }

      return Backbone.sync.call(this, method, model, options);
    }
  });

  return {
    Model: Model,
    AuthModel: AuthModel,
    DiamondashConfigModel: DiamondashConfigModel
  };
}.call(this);

diamondash.widgets = function() {
  var structures = diamondash.components.structures;

  var WidgetViewRegistry = structures.Registry.extend({
    make: function(options) {
      var type;

      if (options.model) {
        type = this.get(options.model.get('type_name'));
      }

      type = type || diamondash.widgets.widget.WidgetView;
      return new type(options);
    }
  });

  var registry = {
    models: new structures.Registry(),
    views: new WidgetViewRegistry()
  };

  return {
    registry: registry,
    WidgetViewRegistry: WidgetViewRegistry
  };
}.call(this);

diamondash.widgets.widget = function() {
  var models = diamondash.models,
      widgets = diamondash.widgets;

  var WidgetModel = models.Model.extend({
    idAttribute: 'name',

    subModelTypes: {},
    subModelTypeAttribute: 'type_name',

    url: function() {
      return diamondash.url(
        'api/widgets',
        this.get('dashboard').get('name'),
        this.get('name'));
    },

    defaults: {
      width: 3
    }
  });

  var WidgetCollection = Backbone.Collection.extend({
    model: WidgetModel
  });

  var WidgetView = Backbone.View.extend({
    id: function() {
      return this.model.id;
    }
  });

  widgets.registry.models.add('widget', WidgetModel);
  widgets.registry.views.add('widget', WidgetView);

  widgets.registry.models.on('add', function(name, type) {
    var objName = 'diamondash.widgets.registry.models.items.' + name;

    // Modifying something on the prototype and changing internal properties
    // set by backbone-relational is not ideal, but is the only way to
    // dynamically add/remove sub-models without changing backbone-relational
    WidgetModel.prototype.subModelTypes[name] = objName;
    WidgetModel._subModels[name] = type;
  });

  widgets.registry.models.on('remove', function(name) {
    delete WidgetModel.prototype.subModelTypes[name];
    delete WidgetModel._subModels[name];
  });

  return {
    WidgetModel: WidgetModel,
    WidgetCollection: WidgetCollection,
    WidgetView: WidgetView
  };
}.call(this);

diamondash.widgets.dynamic = function() {
  var widgets = diamondash.widgets,
      widget = diamondash.widgets.widget,
      utils = diamondash.utils;

  var DynamicWidgetModel = widget.WidgetModel.extend({
    snapshotUrl: function() {
      return utils.joinPaths(_(this).result('url'), 'snapshot');
    },

    fetchSnapshot: function(options) {
      options = options || {};
      options.url = _(this).result('snapshotUrl');
      
      return this.fetch(options);
    }
  });

  widgets.registry.models.add('dynamic', DynamicWidgetModel);

  return {
    DynamicWidgetModel: DynamicWidgetModel
  };
}.call(this);

diamondash.widgets.chart = function() {
  return {
  };
}.call(this);

diamondash.widgets.chart.models = function() {
  var widgets = diamondash.widgets,
      dynamic = diamondash.widgets.dynamic,
      structures = diamondash.components.structures,
      utils = diamondash.utils;

  var ChartMetricModel = Backbone.RelationalModel.extend({
    defaults: {
      datapoints: []
    },

    bisect: d3
      .bisector(function(d) { return d.x; })
      .left,

    lastValue: function(x) {
      var datapoints = this.get('datapoints'),
          d = datapoints[datapoints.length - 1];

      return d && (typeof d.y !== 'undefined')
        ? d.y
        : null;
    },

    valueAt: function(x) {
      var datapoints = this.get('datapoints'),
          i = this.bisect(datapoints, x);
          d = datapoints[i];

      return d && (x === d.x)
        ? d.y
        : null;
    },

    xMin: function() {
      return d3.min(
        this.get('datapoints'),
        function(d) { return d.x; });
    },

    xMax: function() {
      return d3.max(
        this.get('datapoints'),
        function(d) { return d.x; });
    },

    domain: function() {
      return [this.xMin(), this.xMax()];
    },

    yMin: function() {
      return d3.min(
        this.get('datapoints'),
        function(d) { return d.y; });
    },

    yMax: function() {
      return d3.max(
        this.get('datapoints'),
        function(d) { return d.y; });
    },

    range: function() {
      return [this.yMin(), this.yMax()];
    }
  });

  var ChartMetricCollection = Backbone.Collection.extend({
    colorOptions: {
      n: 10,
      scale: d3.scale.category10()
    },

    initialize: function() {
      this.colors = new structures.ColorMaker(this.colorOptions);
      utils.bindEvents(this.bindings, this);
    },

    bindings: {
      'add': function(metric) {
        metric.set('color', this.colors.next());
      }
    }
  });

  var ChartModel = dynamic.DynamicWidgetModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'metrics',
      relatedModel: ChartMetricModel,
      collectionType: ChartMetricCollection
    }],

    defaults: {
      'metrics': []
    },

    xMin: function() {
      return d3.min(this.get('metrics').map(function(m) {
        return m.xMin();
      }));
    },

    xMax: function() {
      return d3.max(this.get('metrics').map(function(m) {
        return m.xMax();
      }));
    },

    domain: function() {
      return [this.xMin(), this.xMax()];
    },

    yMin: function() {
      return d3.min(this.get('metrics').map(function(m) {
        return m.yMin();
      }));
    },

    yMax: function() {
      return d3.max(this.get('metrics').map(function(m) {
        return m.yMax();
      }));
    },

    range: function() {
      return [this.yMin(), this.yMax()];
    }
  });

  widgets.registry.models.add('chart', ChartModel);

  return {
    ChartModel: ChartModel,
    ChartMetricModel: ChartMetricModel,
    ChartMetricCollection: ChartMetricCollection,
  };
}.call(this);

diamondash.widgets.chart.views = function() {
  var structures = diamondash.components.structures,
      utils = diamondash.utils,
      widgets = diamondash.widgets,
      widget = diamondash.widgets.widget;

  var components = {};

  // Replicates the way d3 generates axis time markers
  components.marker = function(target) {
    target.append('line')
      .attr('class', 'tick')
      .attr('y2', 6)
      .attr('x2', 0);

    target.append('text')
      .attr('text-anchor', "middle")
      .attr('dy', ".71em")
      .attr('y', 9)
      .attr('x', 0)
      .attr('fill-opacity', 0);

    return target;
  };

  var ChartDimensions = structures.Extendable.extend({
    height: 0,
    width: 0,

    margin: {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    },

    constructor: function(options) {
      this.set(options);
    },

    set: function(options) {
      options = options || {};

      if ('height' in options) { this.height = options.height; }
      if ('width' in options) { this.width = options.width; }

      if (options.margin) {
        this.margin = _({}).defaults(options.margin, this.margin);
      }

      this.innerWidth = this.width - this.margin.left - this.margin.right;
      this.innerHeight = this.height - this.margin.top - this.margin.bottom;
    }
  });

  var ChartAxisView = structures.Eventable.extend({
    height: 24,
    orient: 'bottom',

    // An approximation to estimate a well-fitting tick count
    markerWidth: 128,

    constructor: function(options) {
      this.chart = options.chart;
      this.scale = options.scale;

      if ('format' in options) { this.format = options.format; }
      if ('orient' in options) { this.orient = options.orient; }
      if ('height' in options) { this.height = options.height; }

      if ('tickCount' in options) { this.tickCount = options.tickCount; }
      if ('tickValues' in options) { this.tickValues = options.tickValues; }

      this.axis = d3.svg.axis()
        .scale(this.scale)
        .orient(this.orient)
        .tickFormat(this.format)
        .ticks(_(this).result('tickCount'));

      this.line = this.chart.canvas.append("g")
        .attr('class', 'axis')
        .call(this.axis);
    },

    _translation: function() {
      var p;

      if (this.orient == 'top') {
        return "translate(0, " + this.height + ")";
      }
      else if (this.orient == 'left') {
        return "translate(" + this.height + ", 0)";
      }
      else if (this.orient == 'right') {
        p = this.chart.dimensions.width - this.height;
        return "translate(" + p + ", 0)";
      }

      p = this.chart.dimensions.height - this.height;
      return "translate(0, " + p + ")";
    },

    format: function() {
      var format = d3.time.format.utc("%d-%m %H:%M");
      return function(t) { return format(new Date(t)); };
    }(),

    tickCount: function() {
      var width = this.chart.dimensions.width;
      var count = Math.floor(width / this.markerWidth);

      return Math.max(0, count);
    },

    tickValues: function(start, end, step) {
      var n = (end - start) / step;
      var m = _(this).result('tickCount');
      var i = 1;

      while (Math.floor(n / i) > m) { i++; }

      var values = d3.range(start, end, step * i);
      values.push(end);

      return values;
    },

    render: function(start, end, step) {
      this.line.attr('transform', this._translation());
      this.axis.tickValues(this.tickValues(start, end, step));
      this.line.call(this.axis);
      return this;
    }
  });

  var ChartView = widget.WidgetView.extend({
    className: 'chart',

    initialize: function(options) {
      options = options || {};
      this.dimensions = new ChartDimensions(options.dimensions);

      this.svg = d3.select(this.el).append('svg');
      this.canvas = this.svg.append('g');

      var self = this;
      this.overlay = this.canvas.append('rect')
        .attr('class', 'event-overlay')
        .attr('fill-opacity', 0)
        .on('mousemove', function() { self.trigger('mousemove', this); })
        .on('mouseout', function() { self.trigger('mouseout', this); });
    },

    render: function() {
      this.svg
        .attr('width', this.dimensions.width)
        .attr('height', this.dimensions.height);

      this.canvas
        .attr('transform', 'translate('
          + this.dimensions.margin.left
          + ','
          + this.dimensions.margin.top + ')');

      this.overlay
        .attr('width', this.dimensions.width)
        .attr('height', this.dimensions.height);

      return this;
    }
  });

  widgets.registry.views.add('chart', ChartView);

  return {
    components: components,
    ChartAxisView: ChartAxisView,
    ChartView: ChartView,
    ChartDimensions: ChartDimensions
  };
}.call(this);

diamondash.widgets.graph = function() {
  return {
  };
}.call(this);

diamondash.widgets.graph.models = function() {
  var widgets = diamondash.widgets,
      chart = diamondash.widgets.chart;

  var GraphModel = chart.models.ChartModel.extend({
    defaults: _({
      dotted: false,
      smooth: false
    }).defaults(chart.models.ChartModel.prototype.defaults)
  });

  widgets.registry.models.add('graph', GraphModel);

  return {
    GraphModel: GraphModel
  };
}.call(this);

diamondash.widgets.graph.views = function() {
  var widgets = diamondash.widgets,
      utils = diamondash.utils,
      structures = diamondash.components.structures,
      chart = diamondash.widgets.chart;

  var GraphLegendView = Backbone.View.extend({
    className: 'legend',

    jst: JST['diamondash/widgets/graph/legend.jst'],

    initialize: function(options) {
      this.graph = options.graph;
      this.model = this.graph.model;
      utils.bindEvents(this.bindings, this);
    },

    format: d3.format(",f"),

    render: function(x) {
      this.$el.html(this.jst({
        self: this,
        x: x
      }));

      var metrics = this.model.get('metrics');
      this.$('.legend-item').each(function() {
        var $el = $(this),
            id = $el.attr('data-metric-id');

        $el
          .find('.swatch')
          .css('background-color', metrics.get(id).get('color'));
      });

      return this;
    },

    bindings: {
      'hover graph': function(position) {
        this.$el.addClass('hover');
        return this.render(position.x);
      },

      'unhover graph': function() {
        this.$el.removeClass('hover');
        return this.render();
      }
    }
  });

  var GraphHoverMarker = structures.Eventable.extend({
    collisionDistance: 60,

    constructor: function(options) {
      this.graph = options.graph;

      if ('collisionsDistance' in options) {
        this.collisionDistance = options.collisionDistance;
      }

      utils.bindEvents(this.bindings, this);
    },

    collision: function(position, tick) {
      var d = Math.abs(position.svg.x - this.graph.fx(tick));
      return d < this.collisionDistance;
    },

    show: function(position) {
      var marker = this.graph.axis.line
        .selectAll('.hover-marker')
        .data([null]);

      marker.enter().append('g')
        .attr('class', 'hover-marker')
        .call(chart.views.components.marker)
        .transition()
          .select('text')
          .attr('fill-opacity', 1);

      marker
        .attr('transform', "translate(" + position.svg.x + ", 0)")
        .select('text').text(this.graph.axis.format(position.x));

      var self = this;
      this.graph.axis.line
        .selectAll('g')
        .style('fill-opacity', function(tick) {
          return self.collision(position, tick)
            ? 0
            : 1;
        });

      return this;
    },

    hide: function() {
      this.graph.canvas
        .selectAll('.hover-marker')
        .remove();

      this.graph.axis.line
        .selectAll('g')
        .style('fill-opacity', 1);

      return this;
    },

    bindings: {
      'hover graph': function(position) {
        this.show(position);
      },

      'unhover graph': function() {
        this.hide();
      }
    }
  });

  var GraphDots = structures.Eventable.extend({
    size: 3,
    hoverSize: 4,

    constructor: function(options) {
      this.graph = options.graph;
      if ('size' in options) { this.size = options.size; }
      if ('hoverSize' in options) { this.hoverSize = options.hoverSize; }
      utils.bindEvents(this.bindings, this);
    },

    render: function() {
      var metricDots = this.graph.canvas
        .selectAll('.metric-dots')
        .data(this.graph.model.get('metrics').models);

      metricDots.enter().append('g')
        .attr('class', 'metric-dots')
        .attr('data-metric-id', function(d) { return d.get('id'); })
        .style('fill', function(d) { return d.get('color'); });

      metricDots.exit().remove();

      var dot = metricDots
        .selectAll('.dot')
        .data(function(d) { return d.get('datapoints'); });

      dot.enter().append('circle')
        .attr('class', 'dot')
        .attr('r', this.size);

      dot.exit().remove();

      dot
        .attr('cx', this.graph.fx.accessor)
        .attr('cy', this.graph.fy.accessor);

      return this;
    },

    bindings: {
      'hover graph': function(position) {
        var data = this.graph.model
          .get('metrics')
          .map(function(metric) {
            return {
              metric: metric,
              y: metric.valueAt(position.x)
            };
          })
          .filter(function(d) {
            return d.y !== null;
          });

        var dot = this.graph.canvas
          .selectAll('.hover-dot')
          .data(data);

        dot.enter().append('circle')
          .attr('class', 'hover-dot')
          .attr('r', 0)
          .style('stroke', function(d) {
            return d.metric.get('color');
          })
          .transition()
            .attr('r', this.hoverSize);

        dot.attr('cx', position.svg.x)
           .attr('cy', this.graph.fy.accessor);
      },

      'unhover graph': function() {
        this.graph.canvas
          .selectAll('.hover-dot')
          .remove();
      }
    }
  });

  var GraphLines = structures.Eventable.extend({
    constructor: function(options) {
      this.graph = options.graph;

      this.line = d3.svg.line()
        .x(this.graph.fx.accessor)
        .y(this.graph.fy.accessor);
    },

    render: function() {
      this.line.interpolate(this.graph.model.get('smooth')
        ? 'monotone'
        : 'linear');

      var line = this.graph.canvas
        .selectAll('.metric-line')
        .data(this.graph.model.get('metrics').models);

      line.enter().append('path')
        .attr('class', 'metric-line')
        .attr('data-metric-id', function(d) { return d.get('id'); })
        .style('stroke', function(d) { return d.get('color'); });

      var self = this;
      line.attr('d', function(d) {
        return self.line(d.get('datapoints'));
      });

      return this;
    }
  });

  var GraphView = chart.views.ChartView.extend({
    height: 214,
    axisHeight: 24,

    margin: {
      top: 4,
      right: 4,
      left: 4,
      bottom: 0
    },

    id: function() {
      return this.model.id;
    },

    initialize: function() {
      GraphView.__super__.initialize.call(this, {
        dimensions: new chart.views.ChartDimensions({
          height: this.height,
          margin: this.margin
        })
      });

      var fx = d3.time.scale();
      fx.accessor = function(d) { return fx(d.x); };
      this.fx = fx;

      var fy = d3.scale.linear();
      fy.accessor = function(d) { return fy(d.y); };
      this.fy = fy;

      this.lines = new GraphLines({graph: this});

      this.axis = new chart.views.ChartAxisView({
        chart: this,
        scale: this.fx,
        height: this.axisHeight
      });

      this.hoverMarker = new GraphHoverMarker({graph: this});
      this.legend = new GraphLegendView({graph: this});
      this.dots = new GraphDots({graph: this});

      utils.bindEvents(this.bindings, this);
    },

    resetScales: function() {
      var maxY = this.dimensions.innerHeight - this.axisHeight;
      this.fy.range([maxY, 0]);
      this.fx.range([0, this.dimensions.innerWidth]);
    },

    render: function() {
      this.dimensions.set({width: this.$el.width()});
      GraphView.__super__.render.call(this);
      this.resetScales();

      var domain = this.model.domain();
      this.fx.domain(domain);
      this.fy.domain(this.model.range());

      this.lines.render();

      if (this.model.get('dotted')) {
        this.dots.render();
      }

      var step = this.model.get('bucket_size');
      this.axis.render(domain[0], domain[1], step);

      this.legend.render();

      this.$el
        .append($(this.svg.node()))
        .append(this.legend.$el);

      return this;
    },

    positionOf: function(coords) {
      var position = {svg: {}};

      position.svg.x = coords.x;
      position.svg.y = coords.y;

      // convert the svg x value to the corresponding time value, then snap
      // it to the closest timestep
      position.x = utils.snap(
        this.fx.invert(position.svg.x),
        this.model.xMin(),
        this.model.get('bucket_size'));

      // shift the svg x value to correspond to the snapped time value
      position.svg.x = this.fx(position.x);

      return position;
    },

    bindings: {
      'mousemove': function(target) {
        var mouse = d3.mouse(target);

        this.trigger('hover', this.positionOf({
          x: mouse[0],
          y: mouse[1]
        }));
      },

      'mouseout': function() {
        this.trigger('unhover');
      },

      'sync model': function() {
        this.render();
      }
    }
  });

  widgets.registry.views.add('graph', GraphView);

  return {
    GraphLines: GraphLines,
    GraphDots: GraphDots,
    GraphLegendView: GraphLegendView,
    GraphHoverMarker: GraphHoverMarker,

    GraphView: GraphView
  };
}.call(this);

diamondash.widgets.lvalue = function() {
  var widgets = diamondash.widgets,
      dynamic = diamondash.widgets.dynamic,
      widget = diamondash.widgets.widget;

  var LValueModel = dynamic.DynamicWidgetModel.extend({
    valueIsBad: function(v) {
      return v !== 0 && !v;
    },

    validate: function(attrs, options) {
      if (this.valueIsBad(attrs.last)) {
        return "LValueModel has bad 'last' attr: " + attrs.last;
      }

      if (this.valueIsBad(attrs.prev)) {
        return "LValueModel has bad 'prev' attr: " + attrs.prev;
      }

      if (this.valueIsBad(attrs.from)) {
        return "LValueModel has bad 'from' attr: " + attrs.from;
      }

      if (this.valueIsBad(attrs.to)) {
        return "LValueModel has bad 'to' attr: " + attrs.to;
      }
    }
  });

  var LastValueView = Backbone.View.extend({
    fadeDuration: 200,

    initialize: function(options) {
      this.widget = options.widget;
    },

    format: {
      short: d3.format(".2s"),
      long: d3.format(",f")
    },

    blink: function(fn) {
      var self = this;

      this.$el.fadeOut(this.fadeDuration, function() {
        fn.call(self);
        self.$el.fadeIn(self.fadeDuration);
      });
    },

    render: function(longMode) {
      this.blink(function() {
        if (longMode) {
          this.$el
            .addClass('long')
            .removeClass('short')
            .text(this.format.long(this.model.get('last')));
        } else {
          this.$el
            .addClass('short')
            .removeClass('long')
            .text(this.format.short(this.model.get('last')));
        }
      });
    }
  });

  var LValueView = widget.WidgetView.extend({
    jst: JST['diamondash/widgets/lvalue/lvalue.jst'],
   
    initialize: function(options) {
      this.listenTo(this.model, 'change', this.render);

      this.last = new LastValueView({
        widget: this,
        model: this.model
      });

      this.mouseIsOver = false;
    },

    format: {
      diff: d3.format("+.3s"),
      percentage: d3.format(".2%"),

      _time: d3.time.format.utc("%d-%m-%Y %H:%M"),
      time: function(t) { return this._time(new Date(t)); },
    },

    render: function() {
      if (this.model.isValid()) {
        var last = this.model.get('last');
        var prev = this.model.get('prev');
        var diff = last - prev;

        var change;
        if (diff > 0) { change = 'good'; }
        else if (diff < 0) { change = 'bad'; }
        else { change = 'no'; }

        this.$el.html(this.jst({
          from: this.format.time(this.model.get('from')),
          to: this.format.time(this.model.get('to')),
          diff: this.format.diff(diff),
          change: change,
          percentage: this.format.percentage(diff / (prev || 1))
        }));

        this.last
          .setElement(this.$('.last'))
          .render(this.mouseIsOver);
      }

      return this;
    },

    events: {
      'mouseenter': function() {
        this.mouseIsOver = true;
        this.last.render(true);
      },

      'mouseleave': function() {
        this.mouseIsOver = false;
        this.last.render(false);
      }
    }
  });

  widgets.registry.models.add('lvalue', LValueModel);
  widgets.registry.views.add('lvalue', LValueView);

  return {
    LValueModel: LValueModel,
    LastValueView: LastValueView,
    LValueView: LValueView 
  };
}.call(this);

diamondash.dashboard = function() {
  var structures = diamondash.components.structures,
      models = diamondash.models,
      widgets = diamondash.widgets,
      widget = diamondash.widgets.widget,
      dynamic = diamondash.widgets.dynamic;

  var DashboardRowModel = models.Model.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'widgets',
      relatedModel: 'diamondash.widgets.widget.WidgetModel',
      includeInJSON: ['name']
    }]
  });

  var DashboardModel = models.Model.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'widgets',
      relatedModel: 'diamondash.widgets.widget.WidgetModel',
      reverseRelation: {
        key: 'dashboard',
        includeInJSON: false
      }
    }, {
      type: Backbone.HasMany,
      key: 'rows',
      relatedModel: DashboardRowModel,
      includeInJSON: ['widgets']
    }],

    defaults: {
      widgets: [],
      rows: [],
      poll_interval: 10000
    },

    initialize: function() {
      this.pollHandle = null;
    },

    fetchSnapshots: function(options) {
      this.get('widgets').each(function(m) {
        if (m instanceof dynamic.DynamicWidgetModel) {
          m.fetchSnapshot(options);
        }
      });
    },

    poll: function(options) {
      if (this.pollHandle === null) {
        this.fetchSnapshots(options);

        var self = this;
        this.pollHandle = setInterval(
          function() { self.fetchSnapshots(); },
          this.get('poll_interval'));
      }

      return this;
    },

    stopPolling: function() {
      if (this.pollHandle !== null) {
        clearInterval(this.pollHandle);
        this.pollHandle = null;
      }

      return this;
    }
  });

  var DashboardWidgetViews = structures.SubviewSet.extend({
    parentAlias: 'dashboard',

    selector: function(key) {
      return '[data-widget=' + key + '] .widget-body';
    },

    make: function(options) {
      return widgets.registry.views.make(options);
    }
  });

  var DashboardView = Backbone.View.extend({
    jst: JST['diamondash/client/jst/dashboard.jst'],

    initialize: function() {
      this.widgets = new DashboardWidgetViews({dashboard: this});

      this.model.get('widgets').each(function(w) {
        this.widgets.add({model: w});
      }, this);
    },

    render: function() {
      this.$el.html(this.jst({dashboard: this}));
      this.widgets.render();
      return this;
    }
  });

  return {
    DashboardView: DashboardView,
    DashboardWidgetViews: DashboardWidgetViews,

    DashboardModel: DashboardModel,
    DashboardRowModel: DashboardRowModel
  };
}.call(this);

(function() {
  diamondash.config = new diamondash.models.DiamondashConfigModel();
}).call(this);
