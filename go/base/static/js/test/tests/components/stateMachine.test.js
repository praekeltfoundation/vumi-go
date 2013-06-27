describe("go.components.stateMachine", function() {
  var stateMachine = go.components.stateMachine;

  afterEach(function() {
    go.testHelpers.unregisterModels();
  });

  describe(".ConnectionModel", function() {
    var EndpointModel = stateMachine.EndpointModel,
        ConnectionModel = stateMachine.ConnectionModel;

    describe(".parse", function() {
      it("should set the uuid attr based on the source and target attrs",
      function() {
        var attrs = ConnectionModel.prototype.parse({
          source: {uuid: 'a'},
          target: {uuid: 'b'}
        });

        assert.equal(attrs.uuid, 'a-b');
      });
    });
  });
});
