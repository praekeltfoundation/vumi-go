describe("go.components.rpc", function() {
  var rpc = go.components.rpc;

  var testHelpers = go.testHelpers,
      assertModelAttrs = testHelpers.assertModelAttrs,
      assertRequest = testHelpers.rpc.assertRequest,
      response = testHelpers.rpc.response,
      errorResponse = testHelpers.rpc.errorResponse;

  describe.only(".sync", function() {
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
      server = sinon.fakeServer.create();

      model = new ToyModel({
        foo: 'lerp',
        bar: 'larp'
      });
    });

    afterEach(function() {
      server.restore();
    });

    it("should make a request using the corresponding model method and params",
    function(done) {
      server.respondWith(function(req) {
        assertRequest(req, '/test', 'r', ['lerp', 'larp']);
        done();
      });

      rpc.sync('read', model);
      server.respond();
    });

    it("should allow the model instance to be used as a param", function(done) {
      var Model = Backbone.Model.extend({
        url: '/test',
        methods: {
          read: {method: 'r', params: ['self']}
        }
      });

      server.respondWith(function(req) {
        assertRequest(req, '/test', 'r', [{foo: 'lerp', bar: 'larp'}]);
        done();
      });

      rpc.sync('read', new Model({foo: 'lerp', bar: 'larp'}));
      server.respond();
    });

    it("should pass the rpc response's result the success callback",
    function(done) {
      server.respondWith(response({foo: 'lerp', bar: 'larp'}));

      var success = function(resp) {
        assert.deepEqual(resp, {foo: 'lerp', bar: 'larp'});
        done();
      };

      rpc.sync('read', model, {success: success});
      server.respond();
    });

    it("should pass an rpc error response to the error callback",
    function(done) {
      server.respondWith(errorResponse('aaah!'));

      var error = function(jqXHR, textStatus, errorThrown) {
        assert.equal(textStatus, 'error');
        assert.equal(errorThrown, 'aaah!');
        done();
      };

      rpc.sync('read', model, {error: error});
      server.respond();
    });

    describe("fetching", function() {
      it("should update the model using on the rpc response", function() {
        server.respondWith(response({foo: 'lerp', bar: 'larp'}));

        model.fetch();
        server.respond();

        assertModelAttrs(model, {foo: 'lerp', bar: 'larp'});
      });
    });
  });
});
