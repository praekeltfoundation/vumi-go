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

    var server,
        view;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      view = new EditConversationGroupsView({
        el: $('<div>')
          .append($('<input>')
            .attr('class', 'search')
            .attr('type', 'text'))
          .append($('<button>')
            .attr('class', 'save'))
          .append($('<table>')
            .attr('class', 'group-table')),

        model: new ConversationGroupsModel({
          key: 'conversation1',
          groups: [{
            key: 'group1',
            name: 'Group1',
            inConversation: false
          }, {
            key: 'group2',
            name: 'Group2',
            inConversation: true
          }, {
            key: 'group3',
            name: 'Group3',
            inConversation: true
          }]
        })
      });
    });

    afterEach(function() {
      view.remove();
      server.restore();
      go.testHelpers.unregisterModels();
      $('.bootbox').modal('hide').remove();
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
          .$('.search')
          .val('Group1')
          .trigger($.Event('input'));

        assert(oneElExists(view.$('[data-uuid=group1]')));
        assert(noElExists(view.$('[data-uuid=group2]')));
        assert(noElExists(view.$('[data-uuid=group3]')));
      });
    });

    describe("when '.save' is clicked", function() {
      it("should send the updated model to the server", function(done) {
        // make some updates to the model
        view.model
          .get('groups')
          .get('group3')
          .set('inConversation', false);

        view.model
          .get('groups')
          .get('group1')
          .set('inConversation', true);

        server.respondWith(function(req) {
          assert.equal(req.url, '/conversations/conversation1/edit_groups/');
          assert.deepEqual(JSON.parse(req.requestBody), {
            key: 'conversation1',
            groups: [
              {key: 'group1'},
              {key: 'group2'}]
          });

          done();
        });

        view.$('.save').click();
        server.respond();
      });

      describe("if the save action was successful", function() {
        it("should notify the user", function() {
          server.respondWith('{}');

          assert(noElExists('.modal'));

          view.$('.save').click();
          server.respond();

          assert(oneElExists('.modal'));
          assert.include(
            $('.modal').text(),
            "Groups saved successfully");
        });
      });

      describe("if the save action was not successful", function() {
        it("should notify the user", function() {
          server.respondWith([404, {}, ""]);

          assert(noElExists('.modal'));

          view.$('.save').click();
          server.respond();

          assert(oneElExists('.modal'));
          assert.include(
            $('.modal').text(),
            "Something bad happened, changes couldn't be save");
        });
      });
    });
  });
});
