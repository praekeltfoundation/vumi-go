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
        el: this.$el,
        jst: 'JST.conversation_editGroups_row',
        data: {model: this.model}
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
    rowType: GroupRowView,

    columnTitles: [
      '',
      'Name'
    ]
  });

  var EditConversationGroupsView = Backbone.View.extend({
    initialize: function(options) {
      this.table = new GroupTableView({
        el: this.$('.groups-table'),
        models: this.model.get('groups')
      });
    },

    render: function() {
      this.table.render();
      return this;
    }
  });

  _.extend(exports, {
    GroupRowView: GroupRowView,
    GroupTableView: GroupTableView,
    EditConversationGroupsView: EditConversationGroupsView
  });
})(go.conversation.editGroups = {});
