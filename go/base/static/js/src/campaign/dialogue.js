// go.campaign.dialogue
// ====================
// Models, Views and other stuff for the dialogue screen
  
(function(exports) {
  var plumbing = go.components.plumbing;

  // State Models
  // ------------
  //
  // State types:
  //   - MENU: the user chooses an option from a menu
  //   - CONTENT: the user enters text
  //   - END:  the user is displayed a message, but cannot respond (thus ending
  //   the session).

  // Model for a dialogue state.
  var DialogueStateModel = plumbing.StateModel.extend({});

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
  var DialogueStateView = plumbing.StateView.extend({
    initialize: function() {},
    // Reset the view and set it to a new state type
    reset: function(type) {},

    // Switch to preview mode
    preview: function() {},

    // Switch to edit mode
    edit: function() {}
  });

  // Base 'mode' for `DialogueStateViews`. Each mode acts as a 'delegate view',
  // targeting a dialogue view's element and acting according to the mode type
  // (for eg, `EDIT`) and state type (for eg, `CONTENT`).
  var DialogueStateViewMode = Backbone.View.extend({
    constructor: function(view) { this.view = view; }
  });

  // Base `PREVIEW` mode, acting as a base for each state type's `PREVIEW` mode
  var StatePreviewer = DialogueStateViewMode.extend({});

  // Base `EDIT` mode, acting as a base for each state type's `EDIT` mode
  var StateEditor = DialogueStateViewMode.extend({});

  // `PREVIEW` mode for `CONTENT` states
  var ContentStatePreviewer = StatePreviewer.extend({});

  // `EDIT` mode for `CONTENT` states
  var ContentStateEditor = StateEditor.extend({});

  // Mappings from state types to their respective set of modes
  var DialogueStateViewModes = {
    CONTENT: {EDIT: ContentStateEditor, PREVIEW: ContentStatePreviewer}
  };

  // Main Controller and View
  // ------------------------

  // The main model for the dialogue screen. Should be the structure which
  // interacts with the api. Contains the collection of dialogue state models
  // and keeps track of the initial state (state0).
  exports.DialogueModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'states',
      relatedModel: 'go.campaign.dialogue.DialogueStateModel',
      collectionType: 'go.campaign.dialogue.DialogueStateCollection'
    }]
  });
  
  // The main view containing all the dialogue states
  exports.DialogueView = plumbing.PlumbView.extend({
    model: exports.DialogueModel
  });
})(go.campaign.dialogue = {});
