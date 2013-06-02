// go.components.plumbing (endpoints)
// ==================================
// Components for endpoints attached to states in a state diagram (or 'plumbing
// view') in Go

(function(exports) {
  // View for a single endpoint on a state in a state diagram.
  //
  // Options:
  // - state: The view to which this endpoint is to be attached
  var EndpointView = Backbone.View.extend({
    // Override to change what params are passed to jsPlumb
    plumbOptions: {},

    id: function() { return this.model.id; },

    initialize: function(options) {
      this.state = options.state;

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

  _.extend(exports, {
    EndpointView: EndpointView
  });
})(go.components.plumbing);
