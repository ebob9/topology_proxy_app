#!/usr/bin/env python
#
# (c) 2019 CloudGenix, Inc
#
# License: MIT
#
# With standalone option, CGX_AUTH_TOKEN environment variable MUST BE SET.

import os
import sys
import argparse

sys.path.append(os.path.dirname(__name__))
from .topo import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="CloudGenix topology API Simple HTTP gateway.")

    # Allow port and debug sets.
    server_group = parser.add_argument_group('SERVER', 'These options set how the server listens on the network.')
    server_group.add_argument("--port", "-P", help="Port to listen on, default is 8080.",
                              default=8080, type=int)
    server_group.add_argument("--debug", "-D", help="Enable Debug mode",
                              default=False, action='store_true')
    server_group.add_argument("--ip", "-I", help="IP Address to listen on, default is 0.0.0.0 (All)",
                              default="0.0.0.0", type=str)
    server_group.add_argument("--threaded", "-T", help="Use multithreading to handle requests",
                              default=False, action='store_true')
    server_group.add_argument("--memcached", "-M", help="Use Memcached instead of SimpleCache. Specify 'IP:PORT'.",
                              default=None, type=str)

    args = vars(parser.parse_args())

    # app.run(host="0.0.0.0", debug=True)

    # app.run(host='0.0.0.0', port=443,
    #         ssl_context='adhoc',
    #         debug=True)

    # app.run(host='0.0.0.0', port=8080,
    #         debug=True)

    # load auth token from env var.
    auth_token = os.environ.get('CGX_AUTH_TOKEN')
    if not auth_token:
        sys.stderr.write("ERROR: Environment Variable 'CGX_AUTH_TOKEN' not set. Exiting.")
        sys.exit(1)

    # create an app instance
    app = create_app(auth_token=auth_token, memcached=args['memcached'])

    app.run(host=args['ip'],
            port=args['port'],
            debug=args['debug'],
            threaded=args['threaded'])
