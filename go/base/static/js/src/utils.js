// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  // Merges the passed in objects together into a single object
  var merge = exports.merge = function() {
    Array.prototype.unshift.call(arguments, {});
    return _.extend.apply(this, arguments);
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
