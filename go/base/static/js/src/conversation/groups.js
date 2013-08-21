// go.conversation.groups
// ======================

(function(exports) {
  var TableView = go.components.tables.TableView,
      RowView = go.components.tables.RowView;

  var TemplateView = go.components.views.TemplateView;

  var SaveActionView = go.components.actions.SaveActionView;

  var GroupRowView = RowView.extend({
    uuid: function() { return this.model.id; },

    initialize: function(options) {
      GroupRowView.__super__.initialize.call(this, options);

      this.template = new TemplateView({
        el: this.$el,
        jst: 'JST.conversation_groups_row',
        data: {model: this.model}
      });

      this.$el.attr('data-uuid', this.uuid());
    },

    render: function() {
      this.template.render();
      return this;
    },

    events: {
      'change .marker': function(e) {
        this.model.set(
          'inConversation',
          $(e.target).is(':checked'),
          {silent: true});
      }
    }
  });

  var GroupTableView = TableView.extend({
    rowType: GroupRowView,
    columnTitles: ['', 'Name']
  });

  var EditConversationGroupsView = Backbone.View.extend({
    initialize: function(options) {
      this.table = new GroupTableView({
        el: this.$('.groups-table'),
        models: this.model.get('groups')
      });

      this.save = new SaveActionView({
        el: this.$('.groups-save'),
        model: this.model
      });

      // !!!TODO!!! prettier notifications
      this.listenTo(this.save, 'error', function() {
        bootbox.alert("Something bad happened, changes couldn't be saved.");
      });
      this.listenTo(this.save, 'success', function() {
        bootbox.alert("Groups saved successfully.");
      });
    },

    render: function() {
      this.table.render();
      return this;
    },

    events: {
      'input .groups-search': function(e) {
        this.table.render({name: $(e.target).val()});
      }
    }
  });

  _.extend(exports, {
    GroupRowView: GroupRowView,
    GroupTableView: GroupTableView,
    EditConversationGroupsView: EditConversationGroupsView
  });
})(go.conversation.groups = {});
