#!/usr/bin/env python
# under normal circumstances, this script would not be necessary. the
# sample_application would have its own setup.py and be properly installed;
# however since it is not bundled in the sdist package, we need some hacks
# to make it work

import os
import sys
import argparse

sys.path.append(os.path.dirname(__name__))
from topo import create_app

# create an app instance
app = create_app()


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

    args = vars(parser.parse_args())

    # app.run(host="0.0.0.0", debug=True)

    # app.run(host='0.0.0.0', port=443,
    #         ssl_context='adhoc',
    #         debug=True)

    # app.run(host='0.0.0.0', port=8080,
    #         debug=True)

    app.run(host=args['ip'], port=args['port'], debug=args['debug'])
