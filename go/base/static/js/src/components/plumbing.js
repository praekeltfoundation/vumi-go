// go.components.plumbing
// ======================
//
// Components for the plumbing views in Go

(function(exports) {
  // Dispatches jsPlumb events to the views associated to the events. 
  //
  // Options
  //   - plumb: jsPlumb instance
  exports.PlumbEventDispatcher = function(options) {
    var self = this;
    options = _.defaults(options || {}, {plumb: jsPlumb});
    this.plumb = options.plumb;

    this.hosts = new PlumbHostInterface(this);
    this.plumb.bind('jsPlumbConnection', function(e) {
      var source = e.sourceView = self.hosts.get(e.source)
        , target = e.targetView = self.hosts.get(e.target);

      source.trigger('plumb:connect', e);
      target.trigger('plumb:connect', e);
    });
  };

  // Interface for PlumbEventDispatcher for manipulating hosts
  // (hosts == elements that host connectable plumb endpoints)
  var PlumbHostInterface = function(dispatcher) {
    this.dispatcher = dispatcher;
    this._hosts = {};
  };

  PlumbHostInterface.prototype = {
    // Get all hosts
    all: function() { return _.values(this._hosts); },

    // Get a host by a selector, element or jquery wrapped element
    get: function(el) {
      var id = $(el).attr('id');
      return id
        ? this._hosts[id]
        : null;
    },

    // Add a view as a new host
    add: function(view) {
      this._hosts[view.$el.attr('id')] = view;
      return view;
    }
  };
})(go.components.plumbing = {});
