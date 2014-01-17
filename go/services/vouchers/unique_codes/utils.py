from django.http import Http404


def unique_codes_pool_or_404(user_api, key):
    """Return the unique code pool with the given `key` or raise `Http404`"""
    store = user_api.unique_code_pool_store
    unique_code_pool = store.get_pool_by_key(key)
    if unique_code_pool is None:
        raise Http404("Unique code pool not found.")
    return unique_code_pool
