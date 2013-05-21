// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  // Acts as a 'base' for class-like objects which can be extended (with the
  // prototype chain set up automatically)
  exports.Extendable = function () {};

  // Backbone has an internal `extend()` function which it assigns to its
  // structures. We need this function, so we arbitrarily choose
  // `Backbone.Model`, since it has the `extend()` function we are looking for.
  var extend = Backbone.Model.extend;

  exports.Extendable.extend = function() {
    Array.prototype.unshift.call(arguments, {});
    return extend.call(this, _.extend.apply(this, arguments));
  };

  exports.highlightActiveLinks = function() {
    // find links in the document that match the current
    // windows url and set them as active.

    var loc = window.location;
    var url = loc.href;
    url = url.replace(loc.host, '').replace(loc.protocol + '//', '');

    $('a[href="' + url + '"]').addClass('active');
  };
})(go.utils = {});
