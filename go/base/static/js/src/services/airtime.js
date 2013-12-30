// go.services.airtime
// ====================

(function(exports) {
  var BaseVoucherPoolView = go.services.BaseVoucherPoolView;

  var VoucherPoolListView = BaseVoucherPoolView.extend({

    initialize: function() {
    },

    getModal: function() {
        return this.$('div#airtime-modal');
    }

  });

  _.extend(exports, {
    VoucherPoolListView: VoucherPoolListView
  });
})(go.services.airtime = {});
