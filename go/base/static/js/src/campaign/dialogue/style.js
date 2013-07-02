// go.campaign.dialogue.style
// ==========================
// Styling for the dialogue screen that cannot be done through css

(function(exports) {
  var initialize = function() {
    _(jsPlumb.Defaults.EndpointStyle).extend({
      radius: 6,
      fillStyle: '#0bcac3'
    });

    _(jsPlumb.Defaults.PaintStyle).extend({
      lineWidth: 4,
      strokeStyle: '#0bcac3'
    });

    jsPlumb.Defaults.Connector = [
      'Flowchart', {
       cornerRadius: 10
    }];

    jsPlumb.Defaults.ConnectionOverlays = [[
      'Arrow', {
      width: 14,
      height: 14,
      location: 0.75
    }]];
  };

  _(exports).extend({
    initialize: initialize
  });
})(go.campaign.dialogue.style = {});
