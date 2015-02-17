// go.apps.dialogue.models
// =======================
// Models for dialogue screen.

(function(exports) {
  var Model = go.components.models.Model;

  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      ConnectionModel = stateMachine.ConnectionModel,
      StateModel = stateMachine.StateModel;

  var contacts = go.contacts.models,
      GroupModel = contacts.GroupModel,
      GroupCollection = contacts.GroupCollection;

  var channel = go.channel.models,
      ChannelTypeModel = channel.ChannelTypeModel,
      ChannelTypeCollection = channel.ChannelTypeCollection;

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
      dummy: 'go.apps.dialogue.models.DummyStateModel',
      choice: 'go.apps.dialogue.models.ChoiceStateModel',
      freetext: 'go.apps.dialogue.models.FreeTextStateModel',
      end: 'go.apps.dialogue.models.EndStateModel',
      group: 'go.apps.dialogue.models.GroupStateModel',
      send: 'go.apps.dialogue.models.SendStateModel',
      httpjson: 'go.apps.dialogue.models.HttpJsonStatemodel'
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
        text: '',
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
        text: '',
        entry_endpoint: {},
        exit_endpoint: {}
      }).defaults(FreeTextStateModel.__super__.defaults.call(this));
    }
  });

  var GroupStateModel = DialogueStateModel.extend({
    storableOnContact: false,

    relations: [{
      type: Backbone.HasOne,
      key: 'group',
      relatedModel: GroupModel,
      includeInJSON: ['key']
    }, {
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
        group: null,
        entry_endpoint: {},
        exit_endpoint: {}
      }).defaults(GroupStateModel.__super__.defaults.call(this));
    }
  });

  var SendStateModel = DialogueStateModel.extend({
    storableOnContact: false,

    relations: [{
      type: Backbone.HasOne,
      key: 'channel_type',
      includeInJSON: 'name',
      relatedModel: ChannelTypeModel
    }, {
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
        text: '',
        channel_type: null,
        entry_endpoint: {},
        exit_endpoint: {}
      }).defaults(GroupStateModel.__super__.defaults.call(this));
    }
  });
  
  var HttpJsonStateModel = DialogueStateModel.extend({
    storableOnContact: false,

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
        url: '',
        method: 'POST',
        entry_endpoint: {},
        exit_endpoint: {}
      }).defaults(GroupStateModel.__super__.defaults.call(this));
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
        text: '',
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

  var DialogueMetadataModel = Model.extend({
    defaults: {repeatable: false}
  });

  var DialogueModel = Model.extend({
    methods: {
      read: {
        method: 'conversation.dialogue.get_poll',
        params: ['campaign_id', 'conversation_key'],
        parse: function(resp) { return resp.poll; }
      },
      update: {
        method: 'conversation.dialogue.save_poll',
        params: function() {
          return [
            this.get('campaign_id'),
            this.get('conversation_key'),
            {poll: this}];
        }
      }
    },

    idAttribute: 'conversation_key',

    relations: [{
      type: Backbone.HasOne,
      key: 'urls',
      relatedModel: Model
    }, {
      type: Backbone.HasMany,
      key: 'groups',
      relatedModel: GroupModel,
      collectionType: GroupCollection
    }, {
      type: Backbone.HasMany,
      key: 'channel_types',
      relatedModel: ChannelTypeModel,
      collectionType: ChannelTypeCollection
    }, {
      type: Backbone.HasOne,
      key: 'poll_metadata',
      relatedModel: DialogueMetadataModel
    }, {
      type: Backbone.HasMany,
      key: 'states',
      relatedModel: DialogueStateModel,
      collectionType: DialogueStateModelCollection,
      reverseRelation: {
        key: 'dialogue',
        includeInJSON: false
      }
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
      urls: {},
      groups: [],
      connections: [],
      poll_metadata: {}
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
    EndStateModel: EndStateModel,
    GroupStateModel: GroupStateModel,
    SendStateModel: SendStateModel,
    HttpJsonStateModel: HttpJsonStateModel
  });
})(go.apps.dialogue.models = {});
