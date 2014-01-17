// go.services.unique_codes
// ====================

(function(exports) {
  var BaseVoucherPoolView = go.services.BaseVoucherPoolView;

  var UniqueCodesPoolView = BaseVoucherPoolView.extend({
  });

  _.extend(exports, {
    UniqueCodesPoolView: UniqueCodesPoolView
  });

})(go.services.unique_codes = {});
