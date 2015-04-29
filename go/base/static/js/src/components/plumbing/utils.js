(function(exports) {
  function repaintSortable($el) {
    // jsPlumb 1.7.5 doesn't seem to play nice with jquery ui's .sortable(),
    // so we need to give jsPlumb an offset for it to repaint correctly. When
    // we specify an offset, jsPlumb sometimes gets unhappy: it seems to
    // expect some internal state for an element to exist, but the state has
    // been cleared by something else. Calling .manage() seems to ensure that
    // the state does exist
    jsPlumb.manage($el.attr('id'), $el.get(0));
    jsPlumb.repaint($el, $el.offset());
  }


  exports.repaintSortable = repaintSortable;
})(go.components.plumbing.utils = {});
