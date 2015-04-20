// go.apps.dialogue.states.freetext
// ================================
// Structures for freetext states (states where users enter any text they want)

(function(exports) {
  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      ExitEndpointView = states.ExitEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView,
      TextEditView = states.partials.TextEditView,
      maxChars = states.maxChars;

  var FreeTextStateEditView = DialogueStateEditView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_freetext_edit',
        partials: {text: new TextEditView({mode: this})}
      };
    }
  });

  var FreeTextStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_freetext_preview'
      };
    }
  });

  var FreeTextStateView = DialogueStateView.extend({
    maxChars: maxChars,

    typeName: 'freetext',

    editModeType: FreeTextStateEditView,
    previewModeType: FreeTextStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', type: EntryEndpointView},
      {attr: 'exit_endpoint', type: ExitEndpointView}],

    events: _({
      'keyup .text': 'onTextChange'
    }).defaults(DialogueStateEditView.prototype.events),

    onTextChange: function(e) {
      this.model.set('text', $(e.target).val(), {silent: true});
      this.render();
      $(e.target).focus();
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
    FreeTextStateView: FreeTextStateView,

    FreeTextStateEditView: FreeTextStateEditView,
    FreeTextStatePreviewView: FreeTextStatePreviewView
  });
})(go.apps.dialogue.states.freetext = {});
