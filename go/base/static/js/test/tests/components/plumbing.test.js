describe("go.components.plumbing", function() {
  describe(".PlumbEventDispatcher", function() {
    var PlumbEventDispatcher = go.components.plumbing.PlumbEventDispatcher,
        PlumbError = go.components.plumbing.PlumbError,
        dispatcher,
        plumb,
        v1,
        v2;

    beforeEach(function() {
      $('body').append("<div class='dummy'></div>");
      $('.dummy').html("<div id='v1'></div><div id='v2'></div>");

      dispatcher = new PlumbEventDispatcher();
      plumb = dispatcher.plumb;

      v1 = new Backbone.View({el: '.dummy #v1'});
      v2 = new Backbone.View({el: '.dummy #v2'});

      dispatcher.subscribe(v1);
      dispatcher.subscribe(v2);
    });

    afterEach(function() { $('body').remove('.dummy'); });

    it("should dispatch 'plumb:connect' events to views", function(done) {
      var v1Connected = false,
          v2Connected = false,
          maybeDone = function() { v1Connected && v2Connected && done(); };

      v1.on('plumb:connect', function(e) {
        assert.equal(e.sourceHost, v1);
        assert.equal(e.targetHost, v2);
        v1Connected = true;
        maybeDone();
      });

      v2.on('plumb:connect', function(e) {
        assert.equal(e.sourceHost, v1);
        assert.equal(e.targetHost, v2);
        v2Connected = true;
        maybeDone();
      });

      plumb.connect({source: 'v1', target: 'v2', scope: '.dummy'});
    });

    describe(".getAll", function() {
      it("should return all the dispatcher's views", function() {
        assert.deepEqual(dispatcher.getAll(), [v1, v2]);
        assert.deepEqual((new PlumbEventDispatcher()).getAll(),[]);
      });
    });

    describe(".get", function() {
      it("should get the view", function() {
        assert.equal(dispatcher.get('.dummy #v1'), v1);
      });

      it("should get the view from an element", function() {
        assert.equal(dispatcher.get($('.dummy #v1').get(0)), v1);
      });

      it("should get the view from a jquery wrapped element", function() {
        assert.equal(dispatcher.get($('.dummy #v1')), v1);
      });

      it("should thrown an error if the view is not found", function() {
        $('.dummy').append("<div id='v'></div>");
        assert.throws(function() { dispatcher.get('.dummy #v'); }, PlumbError);
      });
    });

    describe(".subscribe", function() {
      it("should add a view to the dispatcher", function() {
        $('.dummy').append("<div id='v'></div>");
        var v = new Backbone.View({el: '.dummy #v'});

        assert.equal(dispatcher, dispatcher.subscribe(v));
        assert.propertyVal(dispatcher._views, 'v', v);
      });
    });

    describe(".unsubscribe", function() {
      it("should remove a view", function() {
        assert.equal(dispatcher, dispatcher.unsubscribe(v1));
        assert.deepEqual(dispatcher.getAll(), [v2]);
      });

      it("should remove a view given its selector", function() {
        assert.equal(dispatcher, dispatcher.unsubscribe('.dummy #v1'));
        assert.deepEqual(dispatcher.getAll(), [v2]);
      });

      it("should remove a view given its element", function() {
        var el = $('.dummy #v1').get(0);
        assert.equal(dispatcher, dispatcher.unsubscribe(el));
        assert.deepEqual(dispatcher.getAll(), [v2]);
      });

      it("should remove a view given its jquery wrapped element", function() {
        assert.equal(dispatcher, dispatcher.unsubscribe($('.dummy #v1')));
        assert.deepEqual(dispatcher.getAll(), [v2]);
      });
    });
  });
});
