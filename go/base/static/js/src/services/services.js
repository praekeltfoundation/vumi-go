// go.services
// ===============

(function(exports) {
  var ajaxForm = go.utils.ajaxForm;

  var BaseVoucherPoolView = Backbone.View.extend({

    events: {
      'click a[rel="modal"]': 'showModal'
    },

    initialize: function() {
    },

    getModal: function() {
        return null;
    },

    showModal: function(event) {
      event.preventDefault();
      event.stopPropagation();

      var $modal = this.getModal();
      var $link = $(event.currentTarget);
      var url = $link.attr('href');
      var keepOpen = $link.data('keep-open');
      $modal.load(url, function() {
        var $form = $modal.find('form');
        if ($form.length > 0) {
          ajaxForm($form, function() {
            if (!keepOpen) {
              $modal.modal('hide');
            }
          });
        }
        $modal.modal('show');
      });
    }
  });

  _.extend(exports, {
    BaseVoucherPoolView: BaseVoucherPoolView
  });

})(go.services = {});
