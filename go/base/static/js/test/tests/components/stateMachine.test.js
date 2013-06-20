describe("go.components.stateMachine", function() {
  var stateMachine = go.components.stateMachine;

  afterEach(function() {
    Backbone.Relational.store.reset();
  });

  describe(".ConnectionModel", function() {
    var EndpointModel = stateMachine.EndpointModel,
        ConnectionModel = stateMachine.ConnectionModel;

    it("should assign a unique id from its source and target", function() {
      var endpoint = new ConnectionModel({
        source: new EndpointModel({uuid: 'a'}),
        target: new EndpointModel({uuid: 'b'})
      });

      assert.equal(endpoint.id, 'a-b');
    });
  });
});
