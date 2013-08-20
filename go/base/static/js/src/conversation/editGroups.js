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
        jst: 'JST.conversation_editGroups',
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
          'selected',
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

  _.extend(exports, {
    GroupRowView: GroupRowView,
    GroupTableView: GroupTableView
  });
})(go.conversation.editGroups = {});
