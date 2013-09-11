// go.testHelpers.rpc
// ==================

(function(exports) {
  var assertRequest = function(req, url, method, params) {
    var data = JSON.parse(req.requestBody);

    assert.equal(req.url, url);
    assert.equal(data.method, method);
    assert.deepEqual(data.params, params || []);
  };

  var response = function(data, id) {
    return JSON.stringify({
      id: id || null,
      jsonrpc: '2.0',
      result: data || {}
    });
  };

  var errorResponse = function(error, id, code) {
    return JSON.stringify({
      id: id || null,
      jsonrpc: '2.0',
      result: null,
      error: {code: code || 400, message: error || ''}
    });
  };

  _.extend(exports, {
    assertRequest: assertRequest,
    response: response,
    errorResponse: errorResponse
  });
})(go.testHelpers.rpc = {});
