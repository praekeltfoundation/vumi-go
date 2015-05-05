(function(exports) {
  function repaintSortable($el) {
    // This utility function should be used along with jquery ui's
    // .sortable() for repainting an element's connections.
    // jsPlumb 1.7.5 doesn't seem to play nice with jquery ui's .sortable(),
    // so we need to give jsPlumb an offset for it to repaint correctly. When
    // we specify an offset, jsPlumb sometimes gets unhappy: it seems to
    // expect some internal state for an element to exist, but the state has
    // been cleared by something else. Calling .manage() seems to ensure that
    // the state does exist
    jsPlumb.manage($el.attr('id'), $el.get(0));
    jsPlumb.repaint($el, $el.offset());
  }


  function repaintDraggable($el) {
    // This utility function should be used along with jquery ui's .draggable()
    // for repainting an element's connections. jsPlumb 1.7.5's .draggable()
    // doesn't seem to play nice when elements with jsPlumb endpoints and
    // connections attached to them move (for example, because their parent
    // element's dimensions changed). Its fair to expect a manual offset
    // recaclulation and repaint in these situtations, but
    // .recalculateOffsets() (the method exposed by jsPlumb for this) doesn't
    // appear to help. To solve this, we instead use jquery ui's .draggable()
    // and repaint on drag events using .updateOffset() (an undocumented
    // (internal?) method which seems to be used internally by
    // jsPlumb.repaintEverything()) and .repaint(). jsPlumb appears to still
    // manage draggables and calculate offsets even when jsPlumb.draggable()
    // isn't used, so to avoid seeing weird artefacts from jsPlumb sometimes
    // calculating offsets, we remove the element from the state jsPlumb keeps
    // to manage draggables.
    var id = $el.attr('id');
    jsPlumb.getDragManager().elementRemoved(id);

    jsPlumb.updateOffset({
      elId: id,
      recalc: true
    });

    jsPlumb.repaint($el);
  }


  exports.repaintSortable = repaintSortable;
  exports.repaintDraggable = repaintDraggable;
})(go.components.plumbing.utils = {});
