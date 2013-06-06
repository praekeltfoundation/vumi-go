// go.components.plumbing (endpoints)
// ==================================
// Components for endpoints attached to states in a state diagram (or 'plumbing
// view') in Go

(function(exports) {
  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection;

  // View for a single endpoint on a state in a state diagram.
  //
  // Options:
  // - state: The view to which this endpoint is to be attached
  var EndpointView = Backbone.View.extend({
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
  var EndpointViewCollection = SubviewCollection.extend({
    defaults: {type: EndpointView},
    opts: function() { return {state: this.view, collection: this}; }
  });

  _.extend(exports, {
    EndpointView: EndpointView,
    EndpointViewCollection: EndpointViewCollection
  });
})(go.components.plumbing);
