var vumigo = require('vumigo_v02');

var App = vumigo.App;
var InteractionMachine = vumigo.InteractionMachine;


var DialogueApp = App.extend(function(self) {
    App.call(self, null);
});


if (typeof api != 'undefined') {
    new InteractionMachine(api, new DialogueApp());
}


this.DialogueApp = DialogueApp;
