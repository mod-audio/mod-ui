shopify_ids_hack = {
    'http://code.google.com/p/amsynth/amsynth': True,
}

def get_plugins_licenses(plugins):
    for plugin in plugins:
        if shopify_ids_hack.get(plugin['uri']):
            plugin['licensed'] = True
    return plugins
