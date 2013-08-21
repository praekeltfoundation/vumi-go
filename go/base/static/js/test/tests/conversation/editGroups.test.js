describe("go.conversation.editGroups", function() {
  describe("GroupRowView", function() {
    var GroupRowView = go.conversation.editGroups.GroupRowView,
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
});
