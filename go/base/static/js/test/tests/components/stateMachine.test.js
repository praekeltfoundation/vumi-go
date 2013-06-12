describe("go.components.stateMachine", function() {
  var stateMachine = go.components.stateMachine;

  afterEach(function() {
    Backbone.Relational.store.reset();
  });

  describe(".ConnectionModel", function() {
    var EndpointModel = stateMachine.EndpointModel,
        ConnectionModel = stateMachine.ConnectionModel;

    var ToyConnectionModel = ConnectionModel.extend({
      idAttribute: 'uuid'
    });

    it("should assign a unique id from its source and target", function() {
      var endpoint = new ToyConnectionModel({
        source: new EndpointModel({id: 'a'}),
        target: new EndpointModel({id: 'b'})
      });

      assert.equal(endpoint.id, 'a-b');
    });
  });
});
