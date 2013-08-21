describe("go.conversation.groups", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  describe("GroupRowView", function() {
    var GroupRowView = go.conversation.groups.GroupRowView,
        GroupModel = go.contacts.models.GroupModel;

    var group;

    beforeEach(function() {
      group = new GroupRowView({
        model: new GroupModel({key: 'group1'})
      });
    });

    afterEach(function() {
      group.remove();
      go.testHelpers.unregisterModels();
    });

    describe("when '.marker' is changed", function() {
      beforeEach(function() {
        group.render();
      });

      it("should update its model's 'inConversation' attribute", function() {
        assert(!group.model.get('inConversation'));

        group.$('.marker')
          .prop('checked', true)
          .change();

        assert(group.model.get('inConversation'));

        group.$('.marker')
          .prop('checked', false)
          .change();

        assert(!group.model.get('inConversation'));
      });
    });
  });

  describe("EditConversationGroupsView", function() {
    var EditConversationGroupsView = go.conversation.groups.EditConversationGroupsView,
        ConversationGroupsModel = go.conversation.models.ConversationGroupsModel;

    var view;

    beforeEach(function() {
      view = new EditConversationGroupsView({
        el: $('<div>')
          .append($('<input>')
            .attr('class', 'groups-search')
            .attr('type', 'text'))
          .append($('<table>')
            .attr('class', 'groups-table')),

        model: new ConversationGroupsModel({
          key: 'conversation1',
          groups: [{
            key: 'group1',
            name: 'Spam',
            inConversation: false
          }, {
            key: 'group2',
            name: 'Group 2',
            inConversation: true
          }, {
            key: 'group3',
            name: 'Group 3',
            inConversation: true
          }]
        })
      });
    });

    afterEach(function() {
      view.remove();
      go.testHelpers.unregisterModels();
    });

    describe("when the input in '.search' changes", function() {
      beforeEach(function() {
        view.table.async = false;
        view.table.fadeDuration = 0;
        view.render();
      });

      it("should re-render the table with the new input", function() {
        assert(oneElExists(view.$('[data-uuid=group1]')));
        assert(oneElExists(view.$('[data-uuid=group2]')));
        assert(oneElExists(view.$('[data-uuid=group3]')));

        view
          .$('.groups-search')
          .val('Spam')
          .trigger($.Event('input'));

        assert(oneElExists(view.$('[data-uuid=group1]')));
        assert(noElExists(view.$('[data-uuid=group2]')));
        assert(noElExists(view.$('[data-uuid=group3]')));
      });
    });
  });
});
