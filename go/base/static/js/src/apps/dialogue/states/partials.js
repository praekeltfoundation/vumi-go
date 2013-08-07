// go.apps.dialogue.states.partials
// ================================
// Partials or components that can be fitted into dialogue states

(function(exports) {
  var TemplateView = go.components.views.TemplateView;

  var DialogueStatePartialView = TemplateView.extend({
    data: function() { return this.mode.data(); },

    initialize: function(options) {
      TemplateView.__super__.initialize.call(this, options);
      this.mode = options.mode;
      this.state = this.mode.state;
    }
  });

  var TextEditView = DialogueStatePartialView.extend({
    className: 'text',
    tagName: 'textarea',

    jst: function(data) { return data.model.get('text'); },

    events: {
      'change': function(e) {
        this.state.model.set('text', $(e.target).val(), {silent: true});
        return this;
      }
    }
  });

  _(exports).extend({
    DialogueStatePartialView: DialogueStatePartialView,
    TextEditView: TextEditView
  });
})(go.apps.dialogue.states.partials = {});
