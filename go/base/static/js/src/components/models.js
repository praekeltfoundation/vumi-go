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
