describe("go.components.plumbings.utils", function() {
  var utils = go.components.plumbing.utils;


  describe(".repaintSortable", function() {
    var $el;

    beforeEach(function() {
      $el = $('<div>').appendTo('body');
      sinon.stub(jsPlumb, 'manage');
      sinon.stub(jsPlumb, 'repaint');
    });

    afterEach(function() {
      jsPlumb.manage.restore();
      jsPlumb.repaint.restore();
      $el.remove();
    });

    it("should tell jsPlumb to manage the element", function() {
      $el.attr('id', 'foo');
      assert(!jsPlumb.manage.called);

      utils.repaintSortable($el);

      assert(jsPlumb.manage.calledOnce);
      assert(jsPlumb.manage.calledWith('foo', $el.get(0)));
    });

    it("should tell jsPlumb to repaint the element", function() {
      $el.offset({
        left: 21,
        top: 23
      });

      assert(!jsPlumb.repaint.called);

      utils.repaintSortable($el);

      assert(jsPlumb.repaint.calledOnce);
      assert(jsPlumb.repaint.calledWith($el, {
        left: 21,
        top: 23
      }));
    });
  });

  describe(".repaintDraggable", function() {
    var $el;
    var dragManager;

    beforeEach(function() {
      $el = $('<div>').appendTo('body');
      sinon.stub(jsPlumb, 'updateOffset');
      sinon.stub(jsPlumb, 'repaint');

      dragManager = jsPlumb.getDragManager()
      sinon.stub(dragManager, 'elementRemoved');
    });

    afterEach(function() {
      jsPlumb.updateOffset.restore();
      jsPlumb.repaint.restore();
      dragManager.elementRemoved.restore();
      $el.remove();
    });

    it("should tell jsPlumb to reset draggable state for the element", function() {
      $el.attr('id', 'foo');
      assert(!dragManager.elementRemoved.called);

      utils.repaintDraggable($el);

      assert(dragManager.elementRemoved.calledOnce);
      assert(dragManager.elementRemoved.calledWith('foo'));
    });

    it("should tell jsPlumb to update the element's offset", function() {
      $el.attr('id', 'foo');
      assert(!jsPlumb.updateOffset.called);

      utils.repaintDraggable($el);

      assert(jsPlumb.updateOffset.calledOnce);
      assert(jsPlumb.updateOffset.calledWith({
        elId: 'foo',
        recalc: true
      }));
    });

    it("should tell jsPlumb to repaint the element", function() {
      assert(!jsPlumb.repaint.called);

      utils.repaintDraggable($el);

      assert(jsPlumb.repaint.calledOnce);
      assert(jsPlumb.repaint.calledWith($el));
    });
  });
});
