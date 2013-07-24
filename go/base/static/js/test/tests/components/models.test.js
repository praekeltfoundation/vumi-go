describe("go.components.models", function() {
  var models = go.components.models;

  var testHelpers = go.testHelpers,
      assertModelAttrs = testHelpers.assertModelAttrs,
      response = testHelpers.rpc.response;

  describe(".Model", function() {
    var Model = models.Model;

    var ToyModel = Model.extend({
      methods: {
        read: {param: 'thing', params: ['self']}
      },

      relations: [{
        type: Backbone.HasMany,
        key: 'submodels',
        relatedModel: Model
      }]
    });

    var server,
        model;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      model = new ToyModel({
        uuid: 'jimmy',
        a: 'red',
        b: 'blue',
        c: 'green',
        submodels: [
          {uuid: 'one', spoon: 'yes'},
          {uuid: 'two', spoon: 'pen'}]
      });
    });

    afterEach(function() {
      server.restore();
      Backbone.Relational.store.unregister(model);
    });

    describe(".fetch", function() {
      describe("when `reset` is `true`", function() {
        it("should reset to the server's state if the fetch was successful",
        function() {
          server.respondWith(response({
            uuid: 'jimmy',
            a: 'blue',
            b: 'green',
            submodels: [{uuid: 'two', spoon: 'ham'}]
          }));

          model.fetch({reset: true});
          server.respond();

          assertModelAttrs(model, {
            uuid: 'jimmy',
            a: 'blue',
            b: 'green',
            submodels: [{uuid: 'two', spoon: 'ham'}]
          });
        });

        it("shouldn't change if the fetch was unsuccessful", function() {
          server.respondWith([400, {}, 'Error!']);

          model.fetch({reset: true});
          server.respond();

          assertModelAttrs(model, {
            uuid: 'jimmy',
            a: 'red',
            b: 'blue',
            c: 'green',
            submodels: [
              {uuid: 'one', spoon: 'yes'},
              {uuid: 'two', spoon: 'pen'}]
          });
        });
      });
    });
  });
});

