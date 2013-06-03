// go.components.plumbing (connections)
// ====================================
// Components for connections between endpoints in a state diagram (or
// 'plumbing view') in Go

(function(exports) {
  var idOfConnection = function(sourceId, targetId) {
    return sourceId + '-' + targetId;
  };

  // View for a connection between two endpoints in a state diagram.
  //
  // Options:
  // - diagram: The diagram this connection is part of
  var ConnectionView = Backbone.View.extend({
    // Override to change what params are passed to jsPlumb
    plumbOptions: {},

    id: function() { return this.model.id; },

    initialize: function(options) {
      this.diagram = options.diagram;

      // get the source and target endpoint views from the diagram
      var endpoints = this.diagram.endpoints;
      this.source = endpoints.get(this.model.get('source').id),
      this.target = endpoints.get(this.model.get('target').id);

      // Keep a reference the actual jsPlumb connection
      this.plumbConnection = options.plumbConnection || null;
    },

    _plumbOptions: function() {
      return _.defaults({
        source: this.source.plumbEndpoint,
        target: this.target.plumbEndpoint
      }, _(this).result('plumbOptions'));
    },

    destroy: function() {
      var plumbConnection = this.plumbConnection;

      if (plumbConnection) {
        this.plumbConnection = null;
        jsPlumb.detach(plumbConnection);
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
    idOfConnection: idOfConnection,
    ConnectionView: ConnectionView
  });
})(go.components.plumbing);
