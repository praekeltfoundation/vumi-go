(function(exports) {
  var templatesRoot = '../../templates/';

  var loadTemplate = function(path) {
    var name = path
      .replace(/\..+$/, '')
      .split('/')
      .slice(-2)
      .join('_');

    $.ajax({
      type : 'GET',
      async: false,
      url: templatesRoot + path,
      success : function(raw) { window.JST[name] = _.template(raw); }
    });
  };

  _(exports).extend({
    loadTemplate: loadTemplate
  });
})(window.helpers = {});
