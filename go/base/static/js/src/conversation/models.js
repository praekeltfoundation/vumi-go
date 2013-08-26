// go.conversation.editGroups
// ==========================

(function(exports) {
  var Model = go.components.models.Model;

  var ConversationGroupsModel = Model.extend({
    idAttribute: 'key',

    url: function() {
      return '/conversations/' + this.id + '/edit_groups/';
    },

    relations: [{
      type: Backbone.HasMany,
      key: 'groups',
      relatedModel: 'go.contacts.models.GroupModel',
      collectionType: 'go.contacts.models.GroupCollection'
    }],

    save: function(attrs, options) {
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

      return ConversationGroupsModel.__super__.save.call(this, attrs, options);
    },

    // We need to bring back Backbone's RESTful sync that we override in `Model`
    // to use RPC instead of REST.
    // TODO remove once conversation actions are part of the go http api
    sync: function(method, model, options) {
      options = options || {};

      options.beforeSend = function(xhr) {
        xhr.setRequestHeader('X-CSRFToken', $.cookie('csrftoken'));
      };

      return Backbone.sync.call(this, method, model, options);
    },
  });

  _(exports).extend({
    ConversationGroupsModel: ConversationGroupsModel
  });
})(go.conversation.models = {});
