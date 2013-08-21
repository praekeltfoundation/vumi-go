// go.conversation.editGroups
// ==========================

(function(exports) {
  var TableView = go.components.tables.TableView,
      RowView = go.components.tables.RowView;

  var TemplateView = go.components.views.TemplateView;

  var GroupRowView = RowView.extend({
    initialize: function(options) {
      GroupRowView.__super__.initialize.call(this, options);

      this.template = new TemplateView({
        jst: 'JST.conversation_editGroups_row',
        data: {model: this.model},
        el: this.$el
      });
    },

    render: function() {
      this.template.render();
      return this;
    },

    events: {
      'change .marker': function() {
        this.model.set(
          'inConversation',
          this.$('.marker').is(':checked'),
          {silent: true});
      }
    }
  });

  var GroupTableView = TableView.extend({
    rowType: GroupTableView,

    columnTitles: [
      '',
      'Name'
    ]
  });

  var EditConversationGroupsView = Backbone.View.extend({
    initialize: function(options) {
      this.table = new GroupTableView({
        el: this.$('.edit-table'),
        models: this.model.get('groups')
      });
    }
  });

  _.extend(exports, {
    GroupRowView: GroupRowView,
    GroupTableView: GroupTableView,
    EditConversationGroupsView: EditConversationGroupsView
  });
})(go.conversation.editGroups = {});
