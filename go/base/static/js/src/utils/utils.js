(function(exports) {
  var GoError = go.errors.GoError;

  // Get an element id from a Backbone view, selector, element or jquery
  // wrapped element
  exports.idOf = function(viewOrEl) {
      var $el, id;
      
      if (viewOrEl instanceof Backbone.View) { $el = viewOrEl.$el; }
      else {
        $el = $(viewOrEl);
        if (!$el.length) { throw new GoError(viewOrEl + " not found"); }
      }

      id = $el.attr('id');
      if (!id) { throw new GoError(viewOrEl + " has no id"); }
      return id;
  };
})(go.utils = {});
