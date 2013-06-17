// go.testHelpers
// ==============

(function(exports) {
  var oneElExists = function(selector) {
    return $(selector).get().length === 1;
  };

  var noElExists = function(selector) {
    return $(selector).get().length === 0;
  };

  var loadTemplate = function(path, root) {
    var name = path
      .replace(/\..+$/, '')
      .split('/')
      .join('_');

    $.ajax({
        type : 'GET',
        url: (root || '/../../templates/') + path,
        async: false,
        success : function(raw) { JST[name] = _.template(raw); }
    });
  };

  var unloadTemplates = function() { JST = {}; };

  _.extend(exports, {
    loadTemplate: loadTemplate,
    oneElExists: oneElExists,
    noElExists: noElExists,
    loadTemplate: loadTemplate,
    unloadTemplates: unloadTemplates
  });
})(go.testHelpers = {});
