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
    initialize: function(options) {
      this.state = options.state;

      // Keep a reference to the actual jsPlumb endpoint
      this.plumbEndpoint = null;

      this.on('connect', this.onConnect, this);
      this.on('disconnect', this.onDisconnect, this);
      this.model.on('change', this.render, this);
    },

    // Makes the plumb params passed to jsPlumb when creating the endpoint.
    // Override when extending `EndpointView` to specialise what params are
    // passed to jsPlumb
    plumbOptions: function() { return {}; },

    _plumbOptions: function() {
      return _.defaults({
        uuid: this.model.id,
        isSource: true,
        isTarget: true
      }, this.plumbOptions());
    },

    onConnect: function(source, target, plumbEvent) {
      if (this === source) { this.model.set('target', target.model); }
    },

    onDisconnect: function(source, target, plumbEvent) {
      if (this === source) { this.model.unset('target'); }
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
