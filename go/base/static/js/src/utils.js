// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  var GoError = go.errors.GoError;

  // Acts as a 'base' for class-like objects which can be extended (with the
  // prototype chain set up automatically)
  exports.Extendable = function () {};

  // Backbone has an internal `extend()` function which it assigns to its
  // structures. We need this function, so we arbitrarily choose
  // `Backbone.Model`, since it has the `extend()` function we are looking for.
  exports.Extendable.extend = Backbone.Model.extend;

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
