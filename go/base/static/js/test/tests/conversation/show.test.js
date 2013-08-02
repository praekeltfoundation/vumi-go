describe("go.conversation.show", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

  describe(".ConversationActionsView", function() {
    var ConversationActionsView = go.conversation.show.ConversationActionsView;

    var actions,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      actions = new ConversationActionsView({
        el: $([
          '<div>',
            '<button ',
             'class="action" ',
             'data-url="/conversation/action" ',
             'data-action="action">',
              'Action',
            '</button>',
          '</div>'
        ].join(''))
      });

      bootbox.animate(false);
    });

    afterEach(function() {
      server.restore();

      $('.bootbox')
        .hide()
        .remove();
    });

    describe("when an '.action' button is clicked", function() {
      it("should display a confirmation modal", function() {
        assert(noElExists('.modal'));
        actions.$('.action').eq(0).click();
        assert(oneElExists('.modal'));
      });

      it("should issue a conversation action request to the appropriate url",
      function(done) {
        server.respondWith(function(req) {
          assert.equal(req.url, '/conversation/action');
          done();
        });

        actions.$('.action').eq(0).click();
        $('.modal [data-handler=1]').click();
        server.respond();
      });
    });
  });
});
