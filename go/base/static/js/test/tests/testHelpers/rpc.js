// go.testHelpers.rpc
// ==================

(function(exports) {
  var assertRequest = function(req, url, method, params) {
    assert.equal(req.url, url);
    assert.equal(req.data.method, '/' + method);
    assert.deepEqual(req.data.params, params || []);
  };

  var response = function(id, data) {
    return {id: id, jsonrpc: '2.0', result: data};
  };

  var fakeServer = function(url) {
    var requests = [];

    var stub = sinon.stub($, 'ajax', function(options) {
      options.data = JSON.parse(options.data);
      requests.push(options);
    });

    return {
      requests: requests,

      assertRequest: function(method, params) {
        assertRequest(requests.shift(), url, method, params);
      },

      restore: function() {
        stub.restore();
      },

      respondWith: function(data) {
        var req = requests.shift();

        // deep copy the data to ensure it can't be modified (which may cause
        // obscure test passes/failures)
        data = JSON.parse(JSON.stringify(data));
        req.success(response(req.data.id, data));
      }
    };
  };

  _.extend(exports, {
    assertRequest: assertRequest,
    response: response,
    fakeServer: fakeServer
  });
})(go.testHelpers.rpc = {});
