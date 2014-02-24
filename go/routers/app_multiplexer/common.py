# helpers lifted from GFM and Wikipedia
#
# TODO: move these common text helpers to Vumi Core
# https://github.com/praekelt/vumi/issues/727


def clean(content):
    return (content or '').strip()


def mkmenu(options, start=1, format='%s) %s'):
    items = [format % (idx, opt) for idx, opt in enumerate(options, start)]
    return '\n'.join(items)


def smart_truncate(content, k, sfx='...'):
    """
    Useful for truncating text strings in the following manner:

    'MyFancyTeam' => 'MyFancyT...'
    """
    if len(content) <= k:
        return content
    else:
        return content[:k - len(sfx)] + sfx
