from django.http import Http404


def voucher_pool_or_404(user_api, key):
    """Return the voucher pool with the given `key` or raise `Http404`"""
    voucher_pool_store = user_api.airtime_voucher_pool_store
    voucher_pool = voucher_pool_store.get_voucher_pool_by_key(key)
    if voucher_pool is None:
        raise Http404("Voucher pool not found.")
    return voucher_pool
