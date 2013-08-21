// go.conversation.editGroups
// ==========================

(function(exports) {
  var Model = go.components.models.Model;

  var ConversationGroupsModel = Model.extend({
    idAttribute: 'key',

    url: function() {
      return '/conversation/' + this.id + '/edit_groups/';
    },

    relations: [{
      type: Backbone.HasMany,
      key: 'groups',
      relatedModel: 'go.contacts.models.GroupModel',
      collectionType: 'go.contacts.models.GroupCollection'
    }],

    save: function(options) {
      options = options || {};

      // Override the attributes sent to the server to only include the groups
      // related to this conversation
      options.attrs = {
        key: this.id,
        groups: this
          .get('groups')
          .where({inConversation: true})
          .map(function(g) { return {key: g.id}; })
      };

      return ConversationGroupsModel.__super__.save.call(this, {}, options);
    },

    // We need to bring back Backbone's RESTful sync that we override in `Model`
    // to use RPC instead of REST.
    // TODO remove once conversation actions are part of the go http api
    sync: function() {
      return Backbone.sync.apply(this, arguments);
    },
  });

  _(exports).extend({
    ConversationGroupsModel: ConversationGroupsModel
  });
})(go.conversation.models = {});
