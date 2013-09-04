// go.routing.style
// ================
// Styling for the routing screen that cannot be done through css

(function(exports) {
  var initialize = function() {
    jsPlumb.Defaults.Connector = ['StateMachine'];

    _(jsPlumb.Defaults.EndpointStyle).extend({
      radius: 3,
      fillStyle: '#2f3436'
    });

    _(jsPlumb.Defaults.PaintStyle).extend({
      lineWidth: 2,
      strokeStyle: '#2f3436'
    });
  };

  _(exports).extend({
    initialize: initialize
  });
})(go.routing.style = {});
