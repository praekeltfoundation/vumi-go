describe("go.router.dashboard", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

  describe(".RouterDashboardView", function() {
    var RouterDashboardView = go.router.dashboard.RouterDashboardView;

    var dashboard,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      dashboard = new RouterDashboardView({
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
                     'data-url="/router/action" ',
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

      bootbox.setDefaults({animate: false});
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

      it("should issue a router action request to the appropriate url",
      function(done) {
        server.respondWith(function(req) {
          assert.equal(req.url, '/router/action');
          done();
        });

        dashboard.$('.action').eq(0).click();
        $('.modal [data-bb-handler=confirm]').click();
        server.respond();
      });
    });
  });
});
