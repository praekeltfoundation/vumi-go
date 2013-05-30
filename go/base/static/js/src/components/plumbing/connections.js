// go.components.plumbing (connections)
// ====================================
// Components for connections between endpoints in a state diagram (or
// 'plumbing view') in Go

(function(exports) {
  // View for a connection between two endpoints in a state diagram.
  //
  // Options:
  // - source: The source endpoint view
  // - target: The target endpoint view
  var ConnectionView = Backbone.View.extend({
    plumbDefaults: {},

    initialize: function(options) {
      this.source = options.source;
      this.target = options.target;

      // Keep a reference the actual jsPlumb connection
      this.plumbConnection = null;
    },

    // Makes the plumb params passed to jsPlumb when creating the connection.
    // Override when extending `ConnectionView` to specialise what params
    // are passed to jsPlumb
    plumbParams: function() {
      return _.defaults(
        {source: this.source.plumbEndpoint, target: this.target.plumbEndpoint},
        this.plumbDefaults);
    },

    destroy: function() {
      if (this.plumbConnection) {
        jsPlumb.detach(this.plumbConnection);
        this.plumbConnection = null;
      }
      return this;
    },

    render: function() {
      if (!this.plumbConnection) {
        this.plumbConnection = jsPlumb.connect(this.plumbParams());
      }
      return this;
    }
  });

  _.extend(exports, {
    ConnectionView: ConnectionView
  });
})(go.components.plumbing);
