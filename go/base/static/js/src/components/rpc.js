// go.components.rpc
// =================
// Components for rpc-ifying Backbone.

(function(exports) {
  var Extendable = go.components.structures.Extendable;

  var RpcMethod = Extendable.extend({
    constructor: function(model, method) {
      this.model = model;
      this.spec = model.methods[method];
    },

    params: function() {
      var model = this.model,
          underrides = {self: this.model};

      return this.spec.params.map(function(p) {
        return _.isFunction(p)
          ? p.call(model)
          : underrides[p]
         || model.get(p);
      });
    },

    parse: function(resp) {
      return this.spec.parse
        ? this.spec.parse(resp)
        : resp;
    },

    toJSON: function() {
      return {
        id: uuid.v4(),
        jsonrpc: '2.0',
        method: this.spec.method,
        params: this.params()
      };
    }
  });

  var isRpcError = function(resp) {
    // Accomodate both jsonrpc v1 and v2 responses
    return (_.isObject(resp.error))
        && (_.isNull(resp.result) || _.isUndefined(resp.result));
  };

  var sync = function(method, model, options) {
    var rpcMethod = new RpcMethod(model, method);

    options = _({
      contentType: 'application/json; charset=utf-8',
      type: 'POST',
      dataType: 'json',
      data: JSON.stringify(rpcMethod)
    }).extend(options || {});

    var success = options.success,
        error = options.error;

    options.success = function(resp, textStatus, jqXHR) {
      if (isRpcError(resp)) {
        if (error) { error(jqXHR, 'error', resp.error.message); }
      } else {
        if (success) { success(rpcMethod.parse(resp.result), textStatus, jqXHR); }
      }
    };

    return Backbone.sync(method, model, options);
  };

  _.extend(exports, {
    sync: sync,
    RpcMethod: RpcMethod,
    isRpcError: isRpcError
  });
})(go.components.rpc = {});
