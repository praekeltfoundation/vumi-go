// go.apps.dialogue.states.end
// ===========================
// Structures for end states (states which display something to the user and
// end the session)

(function(exports) {
  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView,
      TextEditView = states.partials.TextEditView,
      maxChars = states.maxChars;

  var EndStateEditView = DialogueStateEditView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_end_edit',
        partials: {text: new TextEditView({mode: this})}
      };
    }
  });

  var EndStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_end_preview'
      };
    }
  });

  var EndStateView = DialogueStateView.extend({
    maxChars: maxChars,

    typeName: 'end',

    editModeType: EndStateEditView,
    previewModeType: EndStatePreviewView,

    endpointSchema: [{attr: 'entry_endpoint', type: EntryEndpointView}],

    events: _({
      'change .text': 'onTextChange'
    }).defaults(DialogueStateEditView.prototype.events),

    onTextChange: function(e) {
      this.model.set('text', $(e.target).val(), {silent: true});
      this.render();
    },

    calcChars: function() {
      return this.model.get('text').length;
    },

    charsLeft: function() {
      return this.maxChars - this.calcChars();
    },

    tooManyChars: function() {
      return (this.charsLeft() < 0) ? 'text-danger' : '';
    }
  });

  _(exports).extend({
    EndStateView: EndStateView,

    EndStateEditView: EndStateEditView,
    EndStatePreviewView: EndStatePreviewView
  });
})(go.apps.dialogue.states.end = {});
