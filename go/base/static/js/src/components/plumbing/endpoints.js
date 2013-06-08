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
  var Endpoint = Backbone.View.extend({
    // Override to change what params are passed to jsPlumb
    plumbOptions: {},

    id: function() { return this.model.id; },

    initialize: function(options) {
      // the state view that this endpoint is part of
      this.state = options.state;

      // the collection of endpoint views that this endpoint is part of
      this.collection = options.collection;

      // Keep a reference to the actual jsPlumb endpoint
      this.plumbEndpoint = null;
    },

    _plumbOptions: function() {
      return _.defaults({
        uuid: _(this).result('id'),
        isSource: true,
        isTarget: true
      }, _(this).result('plumbOptions'));
    },

    destroy: function() {
      if (this.plumbEndpoint) {
        jsPlumb.deleteEndpoint(this.plumbEndpoint);
        this.plumbEndpoint = null;
      }

      return this;
    },

    render: function() {
      if (!this.plumbEndpoint) {
        this.plumbEndpoint = jsPlumb.addEndpoint(
          this.state.$el,
          this._plumbOptions());
      }

      return this;
    }
  });

  // A collection of endpoint views attached to a state view
  var EndpointCollection = SubviewCollection.extend({
    defaults: {type: Endpoint},
    opts: function() { return {state: this.view, collection: this}; }
  });

  // Derived components
  // ------------------

  // An endpoint view type which remains in the same position until it is
  // repositioned.
  var StaticEndpoint = Endpoint.extend({
    defaults: {side: 'left'},

    anchors: {
      left: function(t) { return [0, t, -1, 0]; },
      right: function(t) { return [1, t, 1, 0]; },
      top: function(t) { return [t, 0, 0, -1]; },
      bottom: function(t) { return [t, 1, 0, 1]; }
    },

    constructor: function(options) {
      Endpoint.prototype.constructor.call(this, options);
      _(options).defaults(_(this).result('defaults'));

      this.side = options.side;
      this.anchor = this.anchors[this.side];
      this.reposition(0.5);
    },

    // Move the endpoint along its side based on parameter t, where
    // 0 <= t <= 1.
    reposition: function(t) {
      this.plumbAnchor = this.anchor(t);
      return this;
    },

    render: function() {
      Endpoint.prototype.render.call(this);
      this.plumbEndpoint.setAnchor(this.plumbAnchor);
      return this;
    }
  });

  // Automatically aligns its endpoints to be evenly spaced on one side of the
  // state view.
  //
  // NOTE: Must be used with `StateEndpoint` types, or its derivatives
  var AligningEndpointCollection = EndpointCollection.extend({
    addDefaults: _.defaults(
      {render: false},
      EndpointCollection.prototype.addDefaults),

    defaults: {
      type: StaticEndpoint,
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
      EndpointCollection.prototype.render.call(this);
    }
  });

  _.extend(exports, {
    Endpoint: Endpoint,
    EndpointCollection: EndpointCollection,

    StaticEndpoint: StaticEndpoint,
    AligningEndpointCollection: AligningEndpointCollection
  });
})(go.components.plumbing);
