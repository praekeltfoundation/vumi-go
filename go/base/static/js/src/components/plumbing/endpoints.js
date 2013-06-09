// go.components.plumbing (endpoints)
// ==================================
// Components for endpoints attached to states in a state diagram (or 'plumbing
// view') in Go

(function(exports) {
  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection;

  // Base components
  // ---------------

  // View for a single endpoint on a state in a state diagram.
  //
  // Options:
  // - state: The view to which this endpoint is to be attached
  var EndpointView = Backbone.View.extend({
    id: function() { return this.model.id; },
    className: 'endpoint',
    width: 14,
    height: 14,

    // Override to set whether not the endpoint can source connections
    isSource: true,

    // Override to set whether the element can be the target of connections
    isTarget: true,

    // Override to change what params are passed to jsPlumb when configuring
    // the element as a connection source
    plumbSourceOptions: {anchor: 'Continuous', maxConnections: 1},

    // Override to change what params are passed to jsPlumb when configuring
    // the element as a connection target
    plumbTargetOptions: {anchor: 'Continuous'},

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
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    render: function() {
      this.$el
        .height(this.height)
        .width(this.width);

      this.state.$el.append(this.$el);
    }
  });

  // A collection of endpoint views attached to a state view
  var EndpointViewCollection = SubviewCollection.extend({
    defaults: {type: EndpointView},
    opts: function() { return {state: this.view, collection: this}; }
  });

  // Derived components
  // ------------------

  // An endpoint view type which resides on a side of the state, and
  // can be positioned along the side based on a parameter t.
  var ParametricEndpointView = EndpointView.extend({
    defaults: function() {
      return {
        side: 'left',
        offset: {
          left: this.width * -0.5,
          top: this.height * -0.5
        }
      };
    },

    initialize: function(options) {
      EndpointView.prototype.initialize.call(this, options);
      _(options).defaults(_(this).result('defaults'));

      this.side = options.side;
      this.offset = options.offset;
      this.positioner = this.positioners[this.side];

      this.reposition(0.5);
    },

    positioners: {
      left: function(t) {
        return {
          left: this.offset.left,
          top: this.offset.top + (t * this.$state.height())
        };
      },

      right: function(t) {
        return {
          left: this.offset.left + this.$state.width(),
          top: this.offset.top + (t * this.$state.height())
        };
      },

      top: function(t) {
        return {
          left: this.offset.left + (t * this.$state.width()),
          top: this.offset.top
        };
      },

      bottom: function(t) {
        return {
          left: this.offset.left + (t * this.$state.width()),
          top: this.offset.top + this.$state.height()
        };
      }
    },

    // Move the endpoint along its side based on parameter t, where
    // 0 <= t <= 1.
    reposition: function(t) {
      this.position = this.positioner(t);
      return this;
    },

    render: function() {
      this.$el
        .css({position: 'absolute'})
        .offset(this.position);

      return EndpointView.prototype.render.call(this);
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

    defaults: {
      type: ParametricEndpointView,
      side: 'left',  // the side of the state the collection is drawn on
      margin: 0.005  // margin spacing on each end of the state side
    },

    opts: function() {
      return {
        state: this.view,
        collection: this,
        side: this.side
      };
    },

    initialize: function(options) {
      this.side = options.side;
      this.margin = options.margin;

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

    ParametricEndpointView: ParametricEndpointView,
    AligningEndpointCollection: AligningEndpointCollection
  });
})(go.components.plumbing);
