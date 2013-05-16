// go.campaign.dialogue
// ====================
// Models, Views and other stuff for the dialogue screen
  
(function(exports) {
  var Extendable = go.utils.Extendable;

  // Main Controller and View
  // ------------------------
  
  // Controls the dialogue setup screen
  exports.DialogueController = Extendable.extend({
    // Options
    //   - states: initial states to add
    constructor: function(options) {
    },
    addState: function(state) {}
  });

  // The view for the dialogue screen
  var DialogueView = Backbone.View.extend({});

  // State Models
  // ------------
  //
  // States types:
  //   - MENU: the user chooses an option from a menu
  //   - CONTENT: the user enters text
  //   - END:  the user is displayed a message, but cannot respond (thus ending
  //   the session).

  // Model for a dialogue state.
  var DialogueStateModel = Backbone.Model.extend({
    reset: function(typeName) {}
  });

  // Collection of `StateModel`s
  var DialogueStateCollection = Backbone.Collection.extend({
    model: DialogueStateModel
  });

  // State Views
  // -----------
  //
  // States view modes:
  //   - EDIT: Allows the user to make changes to the dialogue state
  //   - PREVIEW: A 'read-only' preview of the dialogue state
  
  // View corresponding to `StateModel`s. Dynamically switches between modes
  // (`EDIT` and `PREVIEW`) and state types (`CONTENT`, `TEXT` and `END`).
  var DialogueStateView = Backbone.View.extend({
    initialize: function() {},
    // Reset the view and set it to a new state type
    reset: function(type) {},

    // Switch to preview mode
    preview: function() {},

    // Switch to edit mode
    edit: function() {}
  });

  // Base 'mode' for `DialogueStateViews`. Each mode proxies a dialogue view's
  // render calls and events, acting according to the mode type (for eg,
  // `EDIT`) and state type (for eg, `CONTENT`).
  var DialogueStateViewMode = Extendable.extend({
    constructor: function(view) { this.view = view; }
  });

  // Base `PREVIEW` mode, acting as a base for each state type's `PREVIEW` mode
  var StatePreviewer = DialogueStateViewMode.extend({});

  // Base `EDIT` mode, acting as a base for each state type's `EDIT` mode
  var StateEditor = DialogueStateViewMode.extend({});

  // `PREVIEW` mode for `CONTENT` states
  var ContentStatePreviewer = StatePreviewer.extend({});

  // `EDIT` mode for `CONTENT` states
  var ContentStateEditor = StpreviewateEditor.extend({});

  // Mappings from state types to their respective set of modes
  var DialogueStateViewModes = {
    CONTENT: {EDIT: ContentStateEditor, PREVIEW: ContentStatePreviewer}
  };
})(go.campaign.dialogue = {});
