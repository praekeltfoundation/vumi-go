describe("go.conversation.dashboard", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

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
                     'class="action" ',
                     'data-url="/conversation/action" ',
                     'data-action="action"> ',
                      'Action',
                    '</button>',
                  '</td>',
                '</tr>',
              '</tbody>',
            '</table>',
          '</form>'
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
        dashboard.$('.action').eq(0).click();
        assert(oneElExists('.modal'));
      });

      it("should issue a conversation action request to the appropriate url",
      function(done) {
        server.respondWith(function(req) {
          assert.equal(req.url, '/conversation/action');
          done();
        });

        dashboard.$('.action').eq(0).click();
        $('.modal [data-handler=1]').click();
        server.respond();
      });
    });
  });
});
