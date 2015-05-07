// go.apps.dialogue.style
// ======================
// Styling for the dialogue screen that cannot be done through css

(function(exports) {
  var initialize = function() {
    var plumbDefaults = jsPlumb.Defaults;

    var colors = {
      normal: '#428bca',
      hover: '#b41e31'
    };

    _(plumbDefaults.EndpointStyle).extend({
      radius: 6,
      fillStyle: colors.normal
    });

    _(plumbDefaults.PaintStyle).extend({
      lineWidth: 4,
      strokeStyle: colors.normal
    });

    plumbDefaults.HoverPaintStyle = {strokeStyle: colors.hover};
    plumbDefaults.EndpointHoverStyle = {fillStyle: colors.hover};

    plumbDefaults.Connector = [
      'Flowchart', {
       cornerRadius: 200
    }];

    plumbDefaults.ConnectionOverlays = [[
      'Arrow', {
      width: 14,
      height: 14,
      location: 0.85
    }]];
  };

  _(exports).extend({
    initialize: initialize
  });
})(go.apps.dialogue.style = {});
