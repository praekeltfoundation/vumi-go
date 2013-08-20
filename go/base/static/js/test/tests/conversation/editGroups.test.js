describe("go.conversation.editGroups", function() {
  describe("GroupRowView", function() {
    var GroupRowView = go.conversation.editGroups.GroupRowView,
        GroupModel = go.contacts.models.GroupModel;

    var group;

    beforeEach(function() {
      group = new GroupRowView({
        model: new GroupModel({key: 'abc'})
      });
    });

    afterEach(function() {
      group.remove();
    });

    describe("when '.marker' is changed", function() {
      beforeEach(function() {
        group.render();
      });

      it("should update its model's 'selected' attribute", function() {
        assert(!group.model.get('selected'));

        group.$('.marker')
          .prop('checked', true)
          .change();

        assert(group.model.get('selected'));

        group.$('.marker')
          .prop('checked', false)
          .change();

        assert(!group.model.get('selected'));
      });
    });
  });
});
