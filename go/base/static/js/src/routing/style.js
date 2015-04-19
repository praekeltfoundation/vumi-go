// go.routing.style
// ================
// Styling for the routing screen that cannot be done through css

(function(exports) {
  var colors = {
    normal: '#585858',
    hover: '#b41e31'
  };

  var initialize = function() {
    jsPlumb.Defaults.Connector = ['StateMachine'];

    _(jsPlumb.Defaults.EndpointStyle).extend({
      radius: 5,
      fillStyle: colors.normal
    });

    _(jsPlumb.Defaults.PaintStyle).extend({
      lineWidth: 2,
      strokeStyle: colors.normal
    });

    jsPlumb.Defaults.HoverPaintStyle = {
      strokeStyle: colors.hover
    };

    jsPlumb.Defaults.EndpointHoverStyle = {
      fillStyle: colors.hover
    };
  };

  _(exports).extend({
    initialize: initialize
  });
})(go.routing.style = {});
