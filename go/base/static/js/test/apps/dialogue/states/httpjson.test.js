describe("go.apps.dialogue.states.httpjson", function() {
 var dialogue = go.apps.dialogue;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  var diagram,
      state;

  beforeEach(function() {
    setUp();

    diagram = newDialogueDiagram();

    diagram.model.set({
      states: [{
        uuid: 'foo',
        name: 'Foo',
        type: 'httpjson',
        entry_endpoint: {uuid: 'endpoint-a'},
        exit_endpoint: {uuid: 'endpoint-b'},
        method: 'POST',
        url: 'www.foo.bar'
      }]
    }, {silent: true});

    state = diagram.states.get('foo');
  });

  afterEach(function() {
    tearDown();
  });

  describe(".HttpJsonStateEditView", function() {
    beforeEach(function() {
      editMode = state.modes.edit;
      state.edit();
    });

    describe("when the current method changes", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('method'),
          'POST');

        editMode
          .$('.httpjson-method')
          .val('GET')
          .change();

        assert.equal(
          state.model.get('method'),
          'GET');
      });
    });

    describe("when the current url changes", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('url'),
          'www.foo.bar');

        editMode
          .$('.httpjson-url')
          .val('www.bar.baz')
          .change();

        assert.equal(
          state.model.get('url'),
          'www.bar.baz');
      });
    });
  });

  describe(".HttpJsonStatePreviewView", function() {
    var previewMode;

    beforeEach(function() {
      previewMode = state.modes.preview;
      state.preview();
    });

    it("should show the currently assigned url", function() {
      state.preview();

      assert.equal(
        previewMode.$('.httpjson-url').text(),
        'www.foo.bar');
    });

    it("should show the currently assigned method", function() {
      state.preview();

      assert.equal(
        previewMode.$('.httpjson-method').text(),
        'POST');
    });

  });
});
