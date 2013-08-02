describe("go.conversation.show", function() {
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
             'class="action"',
             'data-url="/conversation/action">',
              'Action',
            '</button>',
          '</div>'
        ].join(''))
      });
    });

    afterEach(function() {
      server.restore();
    });

    describe("when an '.action' button is clicked", function() {
      it("should issue a conversation action request to the appropriate url",
      function(done) {
        server.respondWith(function(req) {
          assert.equal(req.url, '/conversation/action');
          done();
        });

        actions.$('.action').eq(0).click();
        server.respond();
      });
    });
  });
});
