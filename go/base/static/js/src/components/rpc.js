// go.components.rpc
// =================
// Components for rpc-ifying Backbone.

(function(exports) {
  var rpcData = function(method, model) {
    var spec = _(model).result('methods')[method],
        underrides = {self: model};

    return JSON.stringify({
      id: uuid.v4(),
      jsonrpc: '2.0',
      method: spec.method,
      params: spec.params.map(function(p) {
        return _.isFunction(p)
          ? p.call(model)
          : underrides[p]
          || model.get(p);
      })
    });
  };

  var ajaxOptions = function(method, model) {
    return {
      contentType: 'application/json; charset=utf-8',
      type: 'POST',
      dataType: 'json',
      data: rpcData(method, model)
    };
  };

  var isRpcError = function(resp) {
    // Accomodate both jsonrpc v1 and v2 responses
    return (_.isObject(resp.error))
        && (_.isNull(resp.result) || _.isUndefined(resp.result));
  };

  var sync = function(method, model, options) {
    options = _({}).extend(
      ajaxOptions(method, model, options),
      options || {});

    var success = options.success,
        error = options.error;

    options.success = function(resp, textStatus, jqXHR) {
      if (isRpcError(resp)) {
        if (error) { error(jqXHR, 'error', resp.error.message); }
      } else {
        if (success) { success(resp.result, textStatus, jqXHR); }
      }
    };

    return Backbone.sync(method, model, options);
  };

  _.extend(exports, {
    sync: sync,
    isRpcError: isRpcError
  });
})(go.components.rpc = {});
