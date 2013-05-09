// go.campaigns.setup.interactive
// ==============================
//
// Models, Views and other stuff for the interactive message setup screen.
//
// State Types
// -----------
//   * OPTION - the user chooses an option from a list
//   * TEXT - the user enters text
//   * END -  the user is displayed a message, but cannot respond (thus ending
//   the session).

  
(function(exports) {
  // Main Controller and View
  // ------------------------
  
  // InteractiveMessageController
  // ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  //
  // Controls the interactive message setup screen.
  exports.InteractiveMessagesController = function(options) {
    this.dispatcher = go.components.plumbing.PlumbDispatcher();
  };

  exports.InteractiveMessageController.prototype = {
    addState: function() {}
  };

  exports.InteractiveMessageView = Backbone.View.extend({
  });

  // State Models
  // ------------

  // StateModel
  // ~~~~~~~~~~
  //
  // Abstract model for an interactive message state
  exports.StateModel = Backbone.Model.extend({
  });

  // StateCollection
  // ~~~~~~~~~~~~~~~
  //
  // Collection of `StateModel`s
  exports.StateCollection = Backbone.Collection.extend({
    model: exports.StateModel
  });

  // OptionStateModel
  // ~~~~~~~~~~~~~~~~
  //
  // Model for the `OPTION` state type
  exports.OptionStateModel = StateModel.extend({
  });

  // TextStateModel
  // ~~~~~~~~~~~~~~
  //
  // Model for the `TEXT` state type
  exports.TextStateModel = StateModel.extend({
  });

  // EndStateModel
  // ~~~~~~~~~~~~~
  //
  // Model for the `END` state type
  exports.EndStateModel = StateModel.extend({
  });

  // State Views
  // -----------

  // StateShellView
  // ~~~~~~~~~~~~~~
  //
  // View that contains a StateView and the input components used to
  // dynamically choose/change the state's type.
  exports.StateShellView = Backbone.View.extend({
  });

  // StateView
  // ~~~~~~~~~
  //
  // Abstract model for an interactive message state
  exports.StateView = Backbone.View.extend({
  });

  // OptionStateView
  // ~~~~~~~~~~~~~~~
  //
  // View for the `OPTION` state type
  exports.OptionStateView = StateView.extend({
  });

  // TextStateView
  // ~~~~~~~~~~~~~
  //
  // View for the `TEXT` state type
  exports.TextStateView = StateView.extend({
  });

  // EndStateView
  // ~~~~~~~~~~~~
  //
  // View for the `END` state type
  exports.EndStateView = StateView.extend({
  });

})(go.campaigns.setup.interactive = {});
