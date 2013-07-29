// go.campaign.dialogue.models
// ===========================
// Models for dialogue screen.

(function(exports) {
  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      ConnectionModel = stateMachine.ConnectionModel,
      StateModel = stateMachine.StateModel,
      StateMachineModel = stateMachine.StateMachineModel;

  var DialogueEndpointModel = EndpointModel.extend({
    defaults: function() { return {uuid: uuid.v4()}; }
  });

  var ChoiceEndpointModel = DialogueEndpointModel.extend({
    defaults: {user_defined_value: false},

    initialize: function() {
      this.on('change:label', function(m, v) {
        if (!this.get('user_defined_value')) { this.setValue(v); }
      }, this);
    },

    setValue: function(v) { return this.set('value', go.utils.slugify(v)); }
  });

  var DialogueStateModel = StateModel.extend({
    storableOnContact: true,

    relations: [],

    subModelTypes: {
      dummy: 'go.campaign.dialogue.models.DummyStateModel',
      choice: 'go.campaign.dialogue.models.ChoiceStateModel',
      freetext: 'go.campaign.dialogue.models.FreeTextStateModel',
      end: 'go.campaign.dialogue.models.EndStateModel'
    },

    defaults: function() {
      return {
        uuid: uuid.v4(),
        user_defined_store_as: false,
        store_on_contact: false,
      };
    },

    initialize: function() {
      this.on('change:name', function(m, v) {
        if (!this.get('user_defined_store_as')) { this.setStoreAs(v); }
      }, this);
    },

    setStoreAs: function(v) { return this.set('store_as', go.utils.slugify(v)); }
  });

  var DialogueStateModelCollection = Backbone.Collection.extend({
    model: DialogueStateModel,
    comparator: function(state) { return state.get('ordinal'); }
  });

  var DummyStateModel = DialogueStateModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'entry_endpoint',
      relatedModel: DialogueEndpointModel
    }, {
      type: Backbone.HasOne,
      key: 'exit_endpoint',
      relatedModel: DialogueEndpointModel
    }],

    defaults: function() {
      return _({
        entry_endpoint: {},
        exit_endpoint: {}
      }).defaults(DummyStateModel.__super__.defaults.call(this));
    }
  });

  var ChoiceStateModel = DialogueStateModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'entry_endpoint',
      relatedModel: DialogueEndpointModel
    }, {
      type: Backbone.HasMany,
      key: 'choice_endpoints',
      relatedModel: ChoiceEndpointModel
    }],

    defaults: function() {
      return _({
        entry_endpoint: {}
      }).defaults(ChoiceStateModel.__super__.defaults.call(this));
    }
  });

  var FreeTextStateModel = DialogueStateModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'entry_endpoint',
      relatedModel: DialogueEndpointModel
    }, {
      type: Backbone.HasOne,
      key: 'exit_endpoint',
      relatedModel: DialogueEndpointModel
    }],

    defaults: function() {
      return _({
        entry_endpoint: {},
        exit_endpoint: {}
      }).defaults(FreeTextStateModel.__super__.defaults.call(this));
    }
  });

  var EndStateModel = DialogueStateModel.extend({
    storableOnContact: false,

    relations: [{
      type: Backbone.HasOne,
      key: 'entry_endpoint',
      relatedModel: DialogueEndpointModel
    }],

    defaults: function() {
      return _({
        entry_endpoint: {}
      }).defaults(EndStateModel.__super__.defaults.call(this));
    }
  });

  var DialogueConnectionModel = ConnectionModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'source',
      includeInJSON: ['uuid'],
      relatedModel: DialogueEndpointModel
    }, {
      type: Backbone.HasOne,
      key: 'target',
      includeInJSON: ['uuid'],
      relatedModel: DialogueEndpointModel
    }]
  });

  var DialogueModel = Backbone.RelationalModel.extend({
    idAttribute: 'conversation_key',
    relations: [{
      type: Backbone.HasMany,
      key: 'states',
      relatedModel: DialogueStateModel,
      collectionType: DialogueStateModelCollection
    }, {
      type: Backbone.HasOne,
      key: 'start_state',
      includeInJSON: ['uuid'],
      relatedModel: DialogueStateModel
    }, {
      type: Backbone.HasMany,
      key: 'connections',
      parse: true,
      relatedModel: DialogueConnectionModel
    }],

    defaults: {
      states: [],
      connections: []
    }
  });

  _(exports).extend({
    DialogueModel: DialogueModel,

    DialogueConnectionModel: DialogueConnectionModel,
    DialogueEndpointModel: DialogueEndpointModel,
    ChoiceEndpointModel: ChoiceEndpointModel,

    DialogueStateModel: DialogueStateModel,
    DummyStateModel: DummyStateModel,
    ChoiceStateModel: ChoiceStateModel,
    FreeTextStateModel: FreeTextStateModel,
    EndStateModel: EndStateModel
  });
})(go.campaign.dialogue.models = {});
