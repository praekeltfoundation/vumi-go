def configured_endpoints(config):
    poll = config.get("poll", {})

    names = set(
        s['channel_type']
        for s in poll.get('states', []) if s['type'] == 'send')

    types = poll.get('channel_types', [])
    return [t['label'] for t in types if t['name'] in names]


def dialogue_js_config(conv):
    poll = conv.config.get("poll", {})

    config = {
        "name": "poll-%s" % conv.key,
        "endpoints": configured_endpoints(conv.config)
    }

    poll_metadata = poll.get('poll_metadata', {})
    delivery_class = poll_metadata.get('delivery_class')

    if delivery_class is not None:
        config['delivery_class'] = delivery_class

    return config
