describe("go.apps.dialogue.states.send", function() {
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
      channel_types: [{
        name: 'sms',
        label: 'SMS'
      }, {
        name: 'ussd',
        label: 'USSD'
      }],
      states: [{
        uuid: 'foo',
        name: 'Foo',
        type: 'send',
        channel_type: 'sms',
        entry_endpoint: {uuid: 'endpoint-a'},
        exit_endpoint: {uuid: 'endpoint-b'},
        text: 'Hello over SMS'
      }]
    }, {silent: true})

    state = diagram.states.get('foo');
  });

  afterEach(function() {
    tearDown();
  });

  describe(".SendStateEditView", function() {
    beforeEach(function() {
      editMode = state.modes.edit;
      state.edit();
    });

    describe("when there are no channel types available", function() {
      it("should show that there are no channel types available", function() {
        diagram.model.set('channel_types', []);
        state.edit();

        assert.equal(
          editMode.$('.channel-type :selected').text(),
          'No channel types available');
      });

      it("should not try change the state's channel type", function() {
        diagram.model.set('channel_types', []);
        state.edit();

        assert.equal(
          state.model.get('channel_type').get('name'),
          'sms');

        editMode
          .$('.channel-type')
          .val('none')
          .change();

        assert.equal(
          state.model.get('channel_type').get('name'),
          'sms');
      });
    });

    describe("when the currently assigned channel type changes", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('channel_type').get('name'),
          'sms');

        editMode
          .$('.channel-type')
          .val('ussd')
          .change();

        assert.equal(
          state.model.get('channel_type').get('name'),
          'ussd');
      });
    });

    describe("when the current channel type is unassigned", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('channel_type').get('name'),
          'sms');

        editMode
          .$('.channel-type')
          .val('unassigned')
          .change();

        assert.isNull(state.model.get('channel_type'));
      });
    });

    describe("when the current text changes", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('text'),
          'Hello over SMS');

        editMode
          .$('.send-text')
          .text('Sulking Sandwich')
          .change();

        assert.equal(
          state.model.get('text'),
          'Sulking Sandwich');
      });
    });
  });

  describe(".SendStatePreviewView", function() {
    var previewMode;

    beforeEach(function() {
      previewMode = state.modes.preview;
      state.preview();
    });

    it("should show the currently assigned channel type", function() {
      state.preview();

      assert.equal(
        previewMode.$('.channel-type').text(),
        'SMS');
    });

    it("should show that no channel type is assigned if relevant", function() {
      state.model.unset('channel_type');
      state.preview();

      assert.equal(
        previewMode.$('.channel-type').text(),
        'No channel type assigned');
    });

    it("should show the current text", function() {
      state.preview();

      assert.equal(
        previewMode.$('.send-text').text(),
        'Hello over SMS');
    });
  });
});
