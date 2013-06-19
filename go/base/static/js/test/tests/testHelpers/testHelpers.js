// go.testHelpers
// ==============

(function(exports) {
  var oneElExists = function(selector) {
    return $(selector).get().length === 1;
  };

  var noElExists = function(selector) {
    return $(selector).get().length === 0;
  };

  var loadTemplate = function(path, root, done) {
    var name = path
      .replace(/\..+$/, '')
      .split('/')
      .join('_');

    $.ajax({
      type : 'GET',
      url: (root || '../../templates/') + path,
      success : function(raw) {
        var compiled = _.template(raw);
        JST[name] = compiled;
        done(name, compiled);
      }
    });
  };

  var unloadTemplates = function() { JST = {}; };

  _.extend(exports, {
    oneElExists: oneElExists,
    noElExists: noElExists,
    loadTemplate: loadTemplate,
    unloadTemplates: unloadTemplates
  });
})(go.testHelpers = {});
