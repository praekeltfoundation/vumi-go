describe("go.conversation.dashboard", function() {
  describe(".ConversationDashboardView", function() {
    var ConversationDashboardView = go.conversation.dashboard.ConversationDashboardView;

    var dashboard,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      dashboard = new ConversationDashboardView({
        el: $([
          '<form>',
            '<table class="table">',
              '<thead>',
                '<tr>',
                  '<th></th>',
                '</tr>',
              '</thead>',
              '<tbody>',
                '<tr>',
                  '<td>',
                    '<button ',
                     'class="inline-action"',
                     'data-url="/conversation/action">',
                      'Action',
                    '</button>',
                  '</td>',
                '</tr>',
              '</tbody>',
            '</table>',
          '</form>'
        ].join(''))
      });
    });

    afterEach(function() {
      server.restore();
    });

    describe("when an '.inline-action' button is clicked", function() {
      it("should issue a conversation action request to the appropriate url",
      function(done) {
        server.respondWith(function(req) {
          assert.equal(req.url, '/conversation/action');
          done();
        });

        dashboard.$('.inline-action').eq(0).click();
        server.respond();
      });
    });
  });
});
