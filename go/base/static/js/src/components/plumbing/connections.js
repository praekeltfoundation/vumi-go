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
    initialize: function(options) {
      this.source = options.source;
      this.target = options.target;

      // Keep a reference the actual jsPlumb connection
      this.plumbConnection = null;
      this.on('plumb:connect', this.onPlumbConnect, this);
      this.on('plumb:disconnect', this.onPlumbDisconnect, this);
    },

    // Override when extending `ConnectionView` to specialise what params
    // are passed to jsPlumb
    plumbOptions: function() { return {}; },

    _plumbOptions: function() {
      return _.defaults({
        source: this.source.plumbEndpoint,
        target: this.target.plumbEndpoint
      }, this.plumbOptions());
    },

    onPlumbConnect: function(e) {
      this.plumbConnection = e.connection;
      this.source.trigger('connect', this);
      this.target.trigger('connect', this);
    },

    onPlumbDisconnect: function() {
      this.destroy();
      this.source.trigger('disconnect', this);
      this.target.trigger('disconnect', this);
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
        this.plumbConnection = jsPlumb.connect(this._plumbOptions());
      }
      return this;
    }
  });

  _.extend(exports, {
    ConnectionView: ConnectionView
  });
})(go.components.plumbing);
