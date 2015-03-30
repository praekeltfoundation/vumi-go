// go.channel.models
// =================

(function(exports) {
  var Model = go.components.models.Model;

  var ChannelTypeModel = Model.extend({
    idAttribute: 'name'
  });

  var ChannelTypeCollection = Backbone.Collection.extend({
    model: ChannelTypeModel,
    comparator: 'name'
  });

  _.extend(exports, {
    ChannelTypeModel: ChannelTypeModel,
    ChannelTypeCollection: ChannelTypeCollection
  });
})(go.channel.models = {});
