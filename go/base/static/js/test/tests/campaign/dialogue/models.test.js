describe("go.campaign.dialogue.models", function() {
  var models = go.campaign.dialogue.models;

  afterEach(function() {
    go.testHelpers.unregisterModels();
  });

  describe(".DialogueStateModel", function() {
    var DialogueStateModel = models.DialogueStateModel;

    it("should assign a new uuid if the model is new", function() {
      var state = new DialogueStateModel();
      assert(state.has('uuid'));
      assert(state.id);
    });

    it("should use the model's existing uuid if the model isn't new",
    function() {
      var state = new DialogueStateModel({uuid: 'state-1'});
      assert.equal(state.get('uuid'), 'state-1');
      assert.equal(state.id, 'state-1');
    });
  });
});
