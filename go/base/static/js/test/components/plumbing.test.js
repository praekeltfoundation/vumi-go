describe("go.components.plumbing", function() {
  describe(".PlumbEventDispatcher", function() {
    var PlumbEventDispatcher = go.components.plumbing.PlumbEventDispatcher
      , dispatcher
      , plumb
      , v1
      , v2;

    beforeEach(function() {
      $('body').append("<div class='dummy'></div>");
      $('.dummy').html("<div id='v1'></div><div id='v2'></div>");

      dispatcher = new PlumbEventDispatcher();
      plumb = dispatcher.plumb;

      v1 = new Backbone.View({el: '.dummy #v1', dispatcher: dispatcher});
      v2 = new Backbone.View({el: '.dummy #v2', dispatcher: dispatcher});

      dispatcher.hosts.add(v1);
      dispatcher.hosts.add(v2);
    });

    afterEach(function() { $('body').remove('.dummy'); });

    it("should dispatch 'plumb:connect' events to views", function(done) {
      var v1Connected = false
        , v2Connected = false
        , maybeDone = function() { v1Connected && v2Connected && done(); };

      v1.on('plumb:connect', function(e) {
        assert.equal(e.sourceView, v1);
        assert.equal(e.targetView, v2);
        v1Connected = true;
        maybeDone();
      });

      v2.on('plumb:connect', function(e) {
        assert.equal(e.sourceView, v1);
        assert.equal(e.targetView, v2);
        v2Connected = true;
        maybeDone();
      });

      plumb.connect({source: 'v1', target: 'v2', scope: '.dummy'});
    });


    describe(".hosts", function() {
      describe(".all", function() {
        it("should return all the dispatcher's hosts", function() {
          assert.deepEqual(dispatcher.hosts.all(), [v1, v2]);
          assert.deepEqual((new PlumbEventDispatcher()).hosts.all(),[]);
        });
      });

      describe(".get", function() {
        it("should return null if no such host exists", function() {
          assert.equal(dispatcher.hosts.get('.v2'), null);
        });

        it("should accept selectors", function() {
          assert.equal(dispatcher.hosts.get('.dummy #v1'), v1);
        });

        it("should accept elements", function() {
          assert.equal(dispatcher.hosts.get($('.dummy #v1').get(0)), v1);
        });

        it("should accept jquery wrapped elements", function() {
          assert.equal(dispatcher.hosts.get($('.dummy #v1')), v1);
        });
      });

      describe(".add", function() {
        it("should add a view using its id", function() {
          var v;
          $('.dummy').append("<div id='v'></div>");

          v = new Backbone.View({el: '.dummy #v', dispatcher: dispatcher});
          assert.equal(v, dispatcher.hosts.add(v));
          assert.propertyVal(dispatcher.hosts._hosts, 'v', v);
        });
      });
    });
  });
});
