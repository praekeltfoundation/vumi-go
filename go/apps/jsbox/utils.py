import json


def jsbox_config_value(config, key):
    jsbox_config = config.get("jsbox_app_config", {})
    key_config = jsbox_config.get(key, {})
    return key_config.get('value')


def jsbox_js_config(config):
    app_config = jsbox_config_value(config, 'config')
    return json.loads(app_config) if app_config is not None else {}
