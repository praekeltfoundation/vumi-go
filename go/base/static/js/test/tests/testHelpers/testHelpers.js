// go.testHelpers
// ==============

(function(exports) {
  var assertFails = function(fn) { assert.throws(fn, chai.AssertionError); };

  var oneElExists = function(selector) {
    return $(selector).length === 1;
  };

  var noElExists = function(selector) {
    return $(selector).length === 0;
  };

  var assertModelAttrs = function(model, attrs) {
    // Backbone.rpc adds an extra `_rpcId` attribute which isn't part of
    // our model attributes. We need to exclude it for equality testing.
    return assert.deepEqual(
      _(model.toJSON()).omit('_rpcId'),
      attrs);
  };

  _.extend(exports, {
    assertFails: assertFails,
    oneElExists: oneElExists,
    noElExists: noElExists,
    assertModelAttrs: assertModelAttrs
  });
})(go.testHelpers = {});
