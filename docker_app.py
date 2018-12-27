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

# create an app instance
app = create_app(auth_token=auth_token, memcached=memcached)

if __name__ == '__main__':
    app.run(debug=debug)
