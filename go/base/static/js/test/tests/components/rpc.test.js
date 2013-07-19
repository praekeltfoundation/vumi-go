describe("go.components.rpc", function() {
  var rpc = go.components.rpc;

  var testHelpers = go.testHelpers,
      assertModelAttrs = testHelpers.assertModelAttrs,
      fakeServer = testHelpers.rpc.fakeServer;

  describe(".sync", function() {
    var ToyModel = Backbone.Model.extend({
      url: '/test',
      methods: {
        read: {method: 'r', params: ['foo', 'bar']}
      },

      sync: function() { return rpc.sync.apply(this, arguments); }
    });

    var server,
        model;

    beforeEach(function() {
      server = fakeServer('/test');

      model = new ToyModel({
        foo: 'lerp',
        bar: 'larp'
      });
    });

    afterEach(function() {
      server.restore();
    });

    it("should make a request using the corresponding model method and params",
    function() {
      rpc.sync('read', model);
      server.assertRequest('r', ['lerp', 'larp']);
    });

    it("should allow the model instance to be used as a param", function() {
      var Model = Backbone.Model.extend({
        url: '/test',
        methods: {
          read: {method: 'r', params: ['self']}
        }
      });

      rpc.sync('read', new Model({foo: 'lerp', bar: 'larp'}));
      server.assertRequest('r', [{foo: 'lerp', bar: 'larp'}]);
    });

    it("should pass the rpc response's result the success callback",
    function(done) {
      var success = function(resp) {
        assert.deepEqual(resp, {foo: 'lerp', bar: 'larp'});
        done();
      };

      rpc.sync('read', model, {success: success});
      server.respondWith({foo: 'lerp', bar: 'larp'});
    });

    it("should pass an rpc error response to the error callback",
    function(done) {
      var error = function(jqXHR, textStatus, errorThrown) {
        assert.equal(textStatus, 'error');
        assert.equal(errorThrown, 'aaah!');
        done();
      };

      rpc.sync('read', model, {error: error});
      server.rpcErrorWith('aaah!');
    });

    describe("fetching", function() {
      it("should update the model using on the rpc response", function() {
        model.fetch();
        server.respondWith({foo: 'lerp', bar: 'larp'});
        assertModelAttrs(model, {foo: 'lerp', bar: 'larp'});
      });
    });
  });
});
