// go.contacts.models
// ==================

(function(exports) {
  var Model = go.components.models.Model;

  var GroupModel = Model.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'urls',
      relatedModel: Model
    }],
    idAttribute: 'key'
  });

  var GroupCollection = Backbone.Collection.extend({
    model: GroupModel,
    comparator: 'name'
  });

  _.extend(exports, {
    GroupModel: GroupModel,
    GroupCollection: GroupCollection
  });
})(go.contacts.models = {});
