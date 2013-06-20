// go.testHelpers
// ==============

(function(exports) {
  var oneElExists = function(selector) {
    return $(selector).length === 1;
  };

  var noElExists = function(selector) {
    return $(selector).length === 0;
  };

  _.extend(exports, {
    oneElExists: oneElExists,
    noElExists: noElExists
  });
})(go.testHelpers = {});
