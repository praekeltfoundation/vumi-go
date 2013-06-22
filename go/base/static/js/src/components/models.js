// go.components.views
// ===================
// Generic, re-usable models for Go

(function(exports) {
  // Base model for syncing with our api.
  var Model = Backbone.RelationalModel.extend({
    rpc: new Backbone.Rpc({
      namespace: '',
      namespaceDelimiter: ''
    }),

    idAttribute: 'uuid',

    url: '/api/v1/go/api',

    // override to specify rpc methods
    methods: {},

    // override to specify the model relations
    relations: [],

    fetch: function(options) {
      options = options || {};

      if (options.reset) {
        // Backbone `sets()` the response attrs before calling the
        // `options.success` callback, which means there isn't an easy way to
        // first `clear()` the model before doing a `set()` with the response
        // attrs To only reset the model with the server's data if the operation
        // was successful, we are left with two options:
        //   1. Ignoring the first `set()` Backbone does, then doing a
        //   `clear()` followed by another `set()`
        //   2. Cache the current model attrs, do a `clear()`, then `fetch()`.
        //   If an error ocurred, we set the model attrs back to the old ones.
        //
        // At the time of writing, Backbone.rpc's `sync()` doesn't appear to do
        // anything with the `options.error` callback that the original
        // `Backbone.sync()` supports. This leaves us with option 1.

        var success = options.success;
        options.success = function(model, resp, options) {
          model.clear(options);
          model.set(model.parse(resp, options), options);
          if (success) { success(model, resp, options); }
        };
      }

      return Backbone.Model.prototype.fetch.call(this, options);
    },

    sync: function(method, model, options) {
      // Keep a reference to the model as one of the options so we can pass the
      // model as one of the rpc method params
      options.self = model;

      Backbone.sync.call(this, method, model, options);
    }
  });

  _.extend(exports, {
    Model: Model
  });
})(go.components.models = {});
