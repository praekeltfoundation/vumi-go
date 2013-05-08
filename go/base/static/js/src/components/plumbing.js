// go.components.plumbing
// ======================
//
// Components for the plumbing views in Go

(function(exports) {
  // Thrown when errors occur whilst interacting with a plumbing component
  var PlumbError = go.errors.GoError.subtype('PlumbError');

  // Dispatches jsPlumb events to the subscribed views
  //
  // Options
  //   - plumb: jsPlumb instance
  //   - views: a list of initial views to add
  var PlumbEventDispatcher = exports.PlumbEventDispatcher = function(options) {
    var self = this;

    options = _.defaults(options || {}, {plumb: jsPlumb, views: []});
    this.plumb = options.plumb;

    this._views = {};
    options.views.map(this.subscribe);

    this.plumb.bind('jsPlumbConnection', function(e) {
      var source = e.sourceHost = self.get(e.source),
          target = e.targetHost = self.get(e.target);

      source.trigger('plumb:connect', e);
      target.trigger('plumb:connect', e);
    });
  };

  PlumbEventDispatcher.prototype = {
    // Get all views
    getAll: function() { return _.values(this._views); },

    // Get a view by a selector, element or jquery wrapped element
    get: function(el) {
      var view = this._views[go.utils.idOf(el)];

      if (!view) {
        throw new PlumbError(el + " not found for dispatcher"); }

      return view;
    },

    // Subscribe a view
    subscribe: function(view) {
      if (!(view instanceof Backbone.View)) {
        throw new PlumbError(view + " is not a Backbone view"); }
  
      this._views[go.utils.idOf(view)] = view;
      return this;
    },

    // Unsubscribe a view by a view, selector, element or jquery wrapped element
    unsubscribe: function(viewOrEl) {
      delete this._views[go.utils.idOf(viewOrEl)];
      return this;
    }
  };
})(go.components.plumbing = {});
