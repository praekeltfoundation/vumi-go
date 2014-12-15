def channel_types(poll):
    return set(
        s['channel_type']
        for s in poll.get('states', []) if s['type'] == 'send')


def endpoint_configs(poll):
    names = channel_types(poll)
    types = poll.get('channel_types', [])

    return dict(
        (t['label'], {'delivery_class': t['name']})
        for t in types if t['name'] in names)


def dialogue_js_config(conv):
    poll = conv.config.get("poll", {})

    config = {
        "name": "poll-%s" % conv.key,
        "endpoints": endpoint_configs(poll)
    }

    poll_metadata = poll.get('poll_metadata', {})
    delivery_class = poll_metadata.get('delivery_class')

    if delivery_class is not None:
        config['delivery_class'] = delivery_class

    return config


def configured_endpoints(config):
    poll = config.get("poll", {})
    names = channel_types(poll)
    types = poll.get('channel_types', [])
    return [t['label'] for t in types if t['name'] in names]
