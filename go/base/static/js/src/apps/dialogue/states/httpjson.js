// go.apps.dialogue.states.httpjson
// ============================
// Structures for httpjson states: states that post/get json

(function(exports) {
  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      ExitEndpointView = states.ExitEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var HttpJsonStateEditView = DialogueStateEditView.extend({
    bodyOptions:{
        jst: 'JST.apps_dialogue_states_httpjson_edit'
    },

    data: function() {
      var d = HttpJsonStateEditView.__super__.data.call(this);
      d.method = this.model.get('method');
      d.url = this.model.get('url');

      return d;
    },

    events: _.extend({
      'change .httpjson-method': function(e) {
        this.model.set('method', $(e.target).val(), {silent: true});
      },

      'change .httpjson-url': function(e) {
        this.model.set('url', $(e.target).val(), {silent: true});
      }
    }, DialogueStateEditView.prototype.events)
  });

  var HttpJsonStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: {
        jst: 'JST.apps_dialogue_states_httpjson_preview'
    },

    data: function() {
      var d = HttpJsonStatePreviewView.__super__.data.call(this);
      d.method = this.model.get('method');
      d.url = this.model.get('url');

      return d;
    }
  });

  var HttpJsonStateView = DialogueStateView.extend({
    typeName: 'httpjson',

    editModeType: HttpJsonStateEditView,
    previewModeType: HttpJsonStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', type: EntryEndpointView},
      {attr: 'exit_endpoint', type: ExitEndpointView}]
  });

  _(exports).extend({
    HttpJsonStateView: HttpJsonStateView,
    HttpJsonStateEditView: HttpJsonStateEditView,
    HttpJsonStatePreviewView: HttpJsonStatePreviewView
  });
})(go.apps.dialogue.states.httpjson = {});
