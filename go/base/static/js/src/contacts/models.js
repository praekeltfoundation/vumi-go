// go.contacts.models
// ==================

(function(exports) {
  var Model = go.components.models.Model;

  var GroupModel = Model.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'urls',
      relatedModel: Model
    }],
    idAttribute: 'key'
  });

  var GroupCollection = Backbone.Collection.extend({
    model: GroupModel
  });

  _.extend(exports, {
    GroupModel: GroupModel,
    GroupCollection: GroupCollection
  });
})(go.contacts.models = {});
