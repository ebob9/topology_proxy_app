import sys
import datetime

from flask import Flask, jsonify, Response, request, make_response
from werkzeug.contrib.cache import SimpleCache, MemcachedCache
import cloudgenix

# attempt to get username/password
try:
    from .cloudgenix_settings import CLOUDGENIX_USER, CLOUDGENIX_PASSWORD
except ImportError:
    print("ERROR, no username/password specified in topo/cloudgenix_settings.py. cannot continue.")
    sys.exit(1)

__author__ = 'Aaron Edwards'

TIME_BETWEEN_API_UPDATES = 120       # seconds
TIME_BETWEEN_LOGIN_ATTEMPTS = 300    # seconds
REFRESH_LOGIN_TOKEN_INTERVAL = 7    # hours
MAX_CACHE_AGE = 1   # minutes
TOPO_PROXY_VERSION = cloudgenix.version + "-2"


# Generic structure to keep authentication info
sdk_vars = {
    'logintime': datetime.datetime.utcnow(),
    'logged_in': False,
    # to debug, change the following.
    "jsondetailed": False,
}

# set cache
topo_cache = SimpleCache()

# create the API constructor
sdk = cloudgenix.API()
# sdk.set_debug(2)

# create the flask app
app = Flask(__name__)


def check_login():
    # check if login needs refreshed
    curtime = datetime.datetime.utcnow()
    if curtime > (sdk_vars['logintime'] + datetime.timedelta(hours=REFRESH_LOGIN_TOKEN_INTERVAL)) \
            or sdk_vars['logged_in'] is False:
        app.logger.info("{0} - {1} hours since last login. attempting to re-login.".format(
            str(datetime.datetime.utcnow().strftime('%b %d %Y %H:%M:%S')), str(REFRESH_LOGIN_TOKEN_INTERVAL)))

        if sdk_vars['logged_in']:
            # logout to attempt to release session ID
            _ = sdk.interactive.logout()
            # ignore success or fail of logout, continue to log in again.
        sdk_vars['logged_in'] = False
        # try to re-login
        while not sdk_vars['logged_in']:
            # sdk_vars['logged_in'] = sdk.interactive.login(email=CLOUDGENIX_USER, password=CLOUDGENIX_PASSWORD)
            # manually log in to make it more scalable.

            resp = sdk.post.login({"email": CLOUDGENIX_USER, "password": CLOUDGENIX_PASSWORD})

            if resp.cgx_status:
                auth_token = resp.cgx_content.get('x_auth_token')
                if auth_token:
                    auth_region = sdk.parse_region(resp)
                    sdk.update_region_to_controller(auth_region)
                    sdk.reparse_login_cookie_after_region_update(resp)

                    profile_response = sdk.get.profile()
                    sdk.tenant_id = profile_response.cgx_content.get('tenant_id')
                    sdk.email = profile_response.cgx_content.get('email')

                    if sdk.tenant_id:
                        sdk_vars['logged_in'] = True

            if not sdk_vars['logged_in']:
                app.logger.error("{0} - Re-login failed. Will Auto-retry.".format(
                    str(datetime.datetime.utcnow().strftime('%b %d %Y %H:%M:%S'))))
                return False
            else:
                app.logger.info("{0} - Re-login successful.".format(str(datetime.datetime.utcnow().strftime('%b %d %Y %H:%M:%S'))))
                # update and wait!
                sdk_vars['logintime'] = datetime.datetime.utcnow()
                # return and continue
                return True

    else:
        # login is current.
        return True


def query_topo_from_path(path):
    """
    Query the topology API and Cache for the path request
    :param path: string with the path of the request.
    :return: list or dict with the response.
    """

    # remove leading and trailing '/'
    path_strip = path.strip('/')
    # split into array
    path_list = path_strip.split('/')

    if len(path_list) not in [2, 4]:
        # only valid pattern is site/:id/swi/:id or site/:id
        return {
            "error": "URL Not Found",
            "return_code": 404
        }

    # get IDs
    if path_list[0].lower() != 'site':
        # only valid pattern is site/:id/swi/:id or site/:id
        return {
            "error": "URL Not Found",
            "return_code": 404
        }

    if len(path_list) == 4 and path_list[2].lower() not in ['swi', 'path']:
        # only valid pattern is site/:id/swi/:id or site/:id
        return {
            "error": "URL Not Found",
            "return_code": 404
        }
    # basic query validation done. make query.
    # ensure logged in

    if check_login():

        target_site = path_list[1]

        # check the cache
        from_cache = False
        # cache_success, cache_topo = check_topo_cache(target_site, sdk_vars['topo_cache'])
        cache_topo = topo_cache.get(target_site)

        if cache_topo:
            topo_success = True
            raw_topo = cache_topo
            from_cache = True

        else:
            # not in cache, go get.
            topo_query = {
                "type": "basenet",
                "nodes": [
                    target_site
                ]
            }

            cgx_query = sdk.post.topology(topo_query)
            topo_success = cgx_query.cgx_status
            raw_topo = cgx_query.cgx_content

        if not topo_success:
            # print "DEBUG 403: ", raw_topo
            # failed query, check for 403 ('Forbidden') by casting dict to str and searching.
            if 'forbidden' in str(raw_topo).lower():
                # likely 403 response, requeue login
                sdk_vars['logged_in'] = False
                return {
                    "error": "API call failed (forbidden)",
                    "return_code": 403,
                    "data": raw_topo
                }
            # any other reason, return error.
            return {
                "error": "API call failed",
                "return_code": 500,
                "data": raw_topo
            }

        # if we get here, got a good response. Update cache if not from cache.
        if not from_cache:
            app.logger.debug('%s not from_cache', target_site)
            topo_cache.set(target_site, raw_topo, timeout=TIME_BETWEEN_API_UPDATES)
            # sdk_vars['topo_cache'][target_site] = {
            #     'response': raw_topo,
            #     'time': datetime.datetime.utcnow()
            # }

        # is it a /site/:siteid: query?
        if len(path_list) == 2:
            # site query, give full topology info for the site.
            full_links = raw_topo.get('links', [])
            if not full_links:
                # no links - not found.
                return {
                    "error": "No links found",
                    "return_code": 404
                }
            else:
                # got match, return
                return full_links

        # is it a /site/:siteid:/swi/:swi_id: query?
        if len(path_list) == 4:

            target_swi = path_list[3]

            # return get the link that matches the target_swi
            swi_record = next((item for item in raw_topo.get('links', []) if item['path_id'] == target_swi), {})
            if not swi_record:
                # no links - not found.
                return {
                    "error": "Requested SWI/PATH not found",
                    "return_code": 404
                }
            else:
                # got match, return
                return swi_record

    else:
        # login failed, return
        return {
            "error": "API login or user profile retrieval failed",
            "return_code": 500
        }


def query_sites():
    """
    Query the sites API.
    :return: list or dict with the response.
    """

    # ensure logged in

    if check_login():

        # check the cache
        from_cache = False
        # cache_success, cache_sites = check_sites_cache(sdk_vars['topo_cache'])
        cache_sites = topo_cache.get('allsites')

        if cache_sites:
            sites_success = True
            raw_sites = cache_sites
            from_cache = True

        else:
            # not in cache, go get.

            cgx_query = sdk.get.sites()
            sites_success = cgx_query.cgx_status
            raw_sites = cgx_query.cgx_content

        if not sites_success:
            # print "DEBUG 403: ", raw_topo
            # failed query, check for 403 ('Forbidden') by casting dict to str and searching.
            if 'forbidden' in str(raw_sites).lower():
                # likely 403 response, requeue login
                sdk_vars['logged_in'] = False
                return {
                    "error": "API call failed (forbidden)",
                    "return_code": 403,
                    "data": raw_sites
                }
            # any other reason, return error.
            return {
                "error": "API call failed",
                "return_code": 500,
                "data": raw_sites
            }

        # if we get here, got a good response. Update cache if not from cache.
        if not from_cache:
            app.logger.debug('allsites not from_cache')
            topo_cache.set('allsites', raw_sites, timeout=TIME_BETWEEN_API_UPDATES)
            # sdk_vars['topo_cache']['allsites'] = {
            #     'response': raw_sites,
            #     'time': datetime.datetime.utcnow()
            # }

        # good data, return items only.
        items = raw_sites.get('items', [])
        if not items:
            return {
                "error": "Empty sites list or API call failed",
                "return_code": 500,
                "data": raw_sites
            }
        else:
            # everything good, return items
            return items

    else:
        # login failed, return
        return {
            "error": "API login or user profile retrieval failed",
            "return_code": 500
        }


def create_app(configfile=None, memcached=None):
    # app is created automatically when this is imported.

    global topo_cache

    # print("MEMCACHED: %s", memcached)

    if memcached:
        topo_cache = MemcachedCache(servers=memcached.split(','), default_timeout=TIME_BETWEEN_API_UPDATES,
                                    key_prefix="topo-proxy-app-")

    @app.route("/robots.txt")  # die robots die
    def robots_txt():
        robots = "User-agent: *\n" \
                 "Disallow: /\n"
        return Response(robots, mimetype='text/plain')

    @app.route("/site")
    @app.route("/site/")
    def get_sites():
        return_code = 200

        # get topo info
        result = query_sites()

        if type(result) is dict and result.get('return_code'):
            return_code = result.get('return_code')

        return make_response(jsonify(result), return_code)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def get_topo(path):
        return_code = 200

        # get topo info
        result = query_topo_from_path(request.path)

        if type(result) is dict and result.get('return_code'):
            return_code = result.get('return_code')

        return make_response(jsonify(result), return_code)

    return app


