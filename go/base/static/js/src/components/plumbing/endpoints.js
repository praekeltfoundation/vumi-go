// go.components.plumbing (endpoints)
// ==================================
// Components for endpoints attached to states in a state diagram (or 'plumbing
// view') in Go

(function(exports) {
  var utils = go.utils,
      functor = utils.functor;

  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection;

  var view = go.components.views,
      LabelView = view.LabelView;

  // Base components
  // ---------------

  // View for a single endpoint on a state in a state diagram.
  //
  // Options:
  // - state: The view to which this endpoint is to be attached
  var EndpointView = Backbone.View.extend({
    id: function() { return this.model.id; },
    className: 'endpoint',

    // Override to set whether the endpoint can source connections
    isSource: true,

    // Override to set whether the element can be the target of connections
    isTarget: true,

    // Override to change what params are passed to jsPlumb when configuring
    // the element as a connection source
    plumbSourceOptions: {anchor: 'Continuous', maxConnections: 1},

    // Override to change what params are passed to jsPlumb when configuring
    // the element as a connection target
    plumbTargetOptions: {anchor: 'Continuous'},

    // Override to enable labelling
    labelled: false,

    // Override to change the options used to initialise the label
    labelOptions: {my: 'right center', at: 'left center', text: ''},

    initialize: function(options) {
      // the state view that this endpoint is part of
      this.state = options.state;
      this.$state = this.state.$el;

      // the collection of endpoint views that this endpoint is part of
      this.collection = options.collection;

      if (this.isSource) {
        jsPlumb.makeSource(this.$el, _(this).result('plumbSourceOptions'));
      }

      if (this.isTarget) {
        jsPlumb.makeTarget(this.$el, _(this).result('plumbTargetOptions'));
      }

      if (this.labelled) {
        this.label = new LabelView(this._labelOptions());
      }
    },

    _labelOptions: function() {
      return _.defaults({of: this.$el}, _(this).result('labelOptions'));
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    render: function() {
      this.state.$el.append(this.$el);
      if (this.labelled) { this.label.render(); }
    }
  });

  // A collection of endpoint views attached to a state view
  var EndpointViewCollection = SubviewCollection.extend({
    type: EndpointView,
    viewOptions: function() { return {state: this.view, collection: this}; },

    remove: function(viewOrId, options) {
      var view = this.get(this.idOfView(viewOrId)),
          connections = this.view.diagram.connections,
          remove = function(c) { connections.remove(c, options); };

      connections.where({source: view}).forEach(remove);
      connections.where({target: view}).forEach(remove);

      return SubviewCollection.prototype.remove.call(this, view, options);
    }
  });

  // Derived components
  // ------------------

  var PositionableEndpointView = EndpointView.extend({
    side: 'left',

    offset: function() {
      return {
        left: this.$el.outerWidth() * -0.5,
        top: this.$el.outerHeight() * -0.5
      };
    },

    initialize: function(options) {
      EndpointView.prototype.initialize.call(this, options);

      this.side = options.side || this.side;
      this.offset = functor(options.offset || this.offset);
    },

    // Override to specialise how the endpoint is positioned
    position: function() { this.offset(); },

    render: function() {
      EndpointView.prototype.render.call(this);

      this.$el
        .css('position', 'absolute')
        .css(this.position());
    }
  });

  // An endpoint view type which resides on a side of the state, and
  // can be positioned along the side based on a parameter t.
  var ParametricEndpointView = PositionableEndpointView.extend({
    initialize: function(options) {
      PositionableEndpointView.prototype.initialize.call(this, options);
      this.positioner = this.positioners[this.side];
      this.t = 0.5;
    },

    positioners: {
      left: function(t) {
        var offset = this.offset();
        return {
          left: offset.left,
          top: offset.top + (t * this.$state.outerHeight())
        };
      },

      right: function(t) {
        var offset = this.offset();
        return {
          left: offset.left + this.$state.outerWidth(),
          top: offset.top + (t * this.$state.outerHeight())
        };
      },

      top: function(t) {
        var offset = this.offset();
        return {
          left: offset.left + (t * this.$state.outerWidth()),
          top: offset.top
        };
      },

      bottom: function(t) {
        var offset = this.offset();
        return {
          left: offset.left + (t * this.$state.outerWidth()),
          top: offset.top + this.$state.outerHeight()
        };
      }
    },

    // Move the endpoint along its side based on parameter t, where
    // 0 <= t <= 1.
    reposition: function(t) {
      this.t = t;
      return this;
    },

    position: function() { return this.positioner(this.t); }
  });

  // An endpoint view type which resides on a side of the state, and
  // and follows the vertical position of one of the state's child elements.
  var FollowingEndpointView = PositionableEndpointView.extend({
    initialize: function(options) {
      PositionableEndpointView.prototype.initialize.call(this, options);
      this.target = options.target;
      this.position = this.positioners[this.side];
    },

    positioners: {
      left: function() {
        var offset = this.offset();
        return {
          left: offset.left,
          top: offset.top + this.targetOffset()
        };
      },

      right: function() {
        var offset = this.offset();
        return {
          left: offset.left + this.$state.outerWidth(),
          top: offset.top + this.targetOffset()
        };
      }
    },

    targetOffset: function() {
      var $target = this.state.$(this.target);
      return $target.position().top + ($target.outerHeight() / 2);
    }
  });

  // Automatically aligns its endpoints to be evenly spaced on one side of the
  // state view.
  //
  // NOTE: Must be used with `ParametricEndpointView` types, or its derivatives
  var AligningEndpointCollection = EndpointViewCollection.extend({
    addDefaults: _.defaults(
      {render: false},
      EndpointViewCollection.prototype.addDefaults),

    type: ParametricEndpointView,

    margin: 0.005,  // margin spacing on each end of the state side

    viewOptions: function() {
      return {
        state: this.view,
        collection: this,
        side: this.side
      };
    },

    initialize: function(options) {
      EndpointViewCollection.prototype.initialize.call(this, options);

      this.side = options.side || this.side;
      this.margin = options.margin || this.margin;

      this.on('add', this.render, this);
      this.on('remove', this.render, this);
    },

    realign: function() {
      var size = this.size();
      if (!size) { return this; }

      var space = 1 - (this.margin * 2),
          incr = space / (size + 1),
          t = this.margin;

      this.each(function(e) { e.reposition(t += incr); });
      return this;
    },

    render: function() {
      this.realign();
      EndpointViewCollection.prototype.render.call(this);
    }
  });

  _.extend(exports, {
    EndpointView: EndpointView,
    EndpointViewCollection: EndpointViewCollection,

    PositionableEndpointView: PositionableEndpointView,
    ParametricEndpointView: ParametricEndpointView,
    FollowingEndpointView: FollowingEndpointView,
    AligningEndpointCollection: AligningEndpointCollection
  });
})(go.components.plumbing);
