#!/usr/bin/env python
#
# (c) 2019 CloudGenix, Inc
#
# License: MIT

from get_docker_secret import get_docker_secret

from topo import create_app

auth_token = get_docker_secret('cgx_auth_token', default=None)
memcached = get_docker_secret('cgx_memcached', default=None)
debug = get_docker_secret('cgx_debug', default=False, cast_to=bool)
always_pretty = get_docker_secret('cgx_always_pretty', default=True, cast_to=bool)

# create an app instance
app = create_app(auth_token=auth_token, memcached=memcached, ssl_verify="/app/CGX_CPROD_CA_BUNDLE.crt")
# Set app to use pretty json by default
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = always_pretty

if __name__ == '__main__':
    app.run(debug=debug)
