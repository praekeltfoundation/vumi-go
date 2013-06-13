// go.test.helpers.rpc
// ===================

(function(exports) {
  var assertRequest = function(req, url, method, params) {
    assert.equal(req.url, url);
    assert.equal(req.data.method, '/' + method);
    assert.deepEqual(req.data.params, params || []);
  };

  var response = function(id, data) {
    return _({id: id, jsonrpc: '2.0', result: data}).extend(data);
  };

  var fakeServer = function(url) {
    var requests = [];

    var stub = sinon.stub($, 'ajax', function(options) {
      options.data = JSON.parse(options.data);
      requests.push(options);
    });

    return {
      requests: requests,

      assertRequest: function(method, params, i) {
        assertRequest(requests[i || 0], url, method, params);
      },

      restore: function() {
        stub.restore();
      },

      respondWith: function(data) {
        requests[0].success(response(requests[0].data.id, data));
      }
    };
  };

  _.extend(exports, {
    assertRequest: assertRequest,
    response: response,
    fakeServer: fakeServer
  });
})(go.testHelpers.rpc = {});
