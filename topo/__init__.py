from flask import Flask, jsonify, Response, request, make_response
from cachelib.simple import SimpleCache
from cachelib.memcached import MemcachedCache
import cloudgenix
from cloudgenix import jdout

__author__ = 'Aaron Edwards'

APP_NAME = "Topology Proxy App"
APP_VERSION = "2.0.3"

TIME_BETWEEN_API_UPDATES = 300  # seconds
MAX_CACHE_AGE = 5  # minutes

# set cache
topo_cache = SimpleCache()

# create the API constructor
sdk = cloudgenix.API(update_check=False, ssl_verify=False)

# set a custom user-agent header extension in case we need it to track down issues.
req_session = sdk.expose_session()
user_agent = req_session.headers.get('User-Agent')
user_agent += ' ({0} v{1})'.format(APP_NAME, APP_VERSION)
req_session.headers.update({
    'User-Agent': str(user_agent)
})

# create the flask app
app = Flask(__name__)

# set pretty json printing
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True


def query_topo_from_path(path):
    """
    Query the topology API and Cache for the path request
    :param path: string with the path of the request.
    :return: list or dict with the response.
    """

    from_cache = False

    # remove leading and trailing '/'
    path_strip = path.strip('/')
    # split into array
    path_list = path_strip.split('/')

    if len(path_list) not in [2, 4]:
        # only valid pattern is site/:id/swi/:id or site/:id
        # also, can use 'path' or 'swi' for swi.
        return {
            "error": "URL Not Found",
            "return_code": 404
        }, from_cache

    # get IDs
    if path_list[0].lower() != 'site':
        # only valid pattern is site/:id/swi/:id or site/:id
        # also, can use 'path' or 'swi' for swi.
        return {
            "error": "URL Not Found",
            "return_code": 404
        }, from_cache

    if len(path_list) == 4 and path_list[2].lower() not in ['swi', 'path']:
        # only valid pattern is site/:id/swi/:id or site/:id
        # also, can use 'path' or 'swi' for swi.
        return {
            "error": "URL Not Found",
            "return_code": 404
        }, from_cache
    # basic query validation done. make query.

    target_site = path_list[1]

    # check the cache
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
            return {
                "error": "API call failed (forbidden)",
                "return_code": 403,
                "data": raw_topo
            }, from_cache
        # any other reason, return error.
        return {
            "error": "API call failed",
            "return_code": 500,
            "data": raw_topo
        }, from_cache

    # if we get here, got a good response. Update cache if not from cache.
    if not from_cache:
        app.logger.debug('%s not from_cache', target_site)
        topo_cache.set(target_site, raw_topo, timeout=TIME_BETWEEN_API_UPDATES)

    # is it a /site/:siteid: query?
    if len(path_list) == 2:
        # site query, give full topology info for the site.
        full_links = raw_topo.get('links', [])
        if not full_links:
            # no links - not found.
            return {
                "error": "No links found",
                "return_code": 404
            }, from_cache
        else:
            # got match, return
            return full_links, from_cache

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
            }, from_cache
        else:
            # got match, return
            return swi_record, from_cache


def query_sites():
    """
    Query the sites API.
    :return: list or dict with the response, from_cache (bool)
    """

    # check the cache
    from_cache = False
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
            return {
                "error": "API call failed (forbidden)",
                "return_code": 403,
                "data": raw_sites
            }, from_cache
        # any other reason, return error.
        return {
            "error": "API call failed",
            "return_code": 500,
            "data": raw_sites
        }, from_cache

    # if we get here, got a good response. Update cache if not from cache.
    if not from_cache:
        app.logger.debug('allsites not from_cache')
        topo_cache.set('allsites', raw_sites, timeout=TIME_BETWEEN_API_UPDATES)

    # good data, return items only.
    items = raw_sites.get('items', [])
    if not items:
        return {
            "error": "Empty sites list or API call failed",
            "return_code": 500,
            "data": raw_sites
        }, from_cache
    else:
        # everything good, return items
        return items, from_cache


def create_app(auth_token=None, memcached=None, ssl_verify=True):
    # app is created automatically when this is imported.

    # SDK constructor is set to ssl_verify=False at launch. This prevents
    # workers from creating default CA_VERIFY /tmp files for each by default.
    # if this is not changed by calling app, the CA_VERIFY will set to True by default.
    # But first, check if ssl_verify is different than what the constructor is already using.
    if sdk.verify != ssl_verify:
        sdk.ssl_verify(ssl_verify)

    # if set, update SDK with auth token
    if auth_token is not None:
        # parse auth_token to get info
        auth_token_dict = sdk.parse_auth_token(auth_token)

        # Get and update constructor with Tenant ID
        tenant_id = auth_token_dict.get('t.id')
        sdk.tenant_id = tenant_id

        region = auth_token_dict.get('region')
        if region:
            sdk.update_region_to_controller(region)

        # Static Token uses X-Auth-Token header instead of cookies.
        sdk.add_headers({
            'X-Auth-Token': auth_token
        })

    # Set Memcache if used.
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
        result, from_cache = query_sites()

        if type(result) is dict and result.get('return_code'):
            return_code = result.get('return_code')

        response = make_response(jsonify(result), return_code)

        # add cache info headers
        if from_cache:
            cache_type = topo_cache.__class__.__name__
            response.headers['X-From-Cache'] = from_cache
            response.headers['X-Cache-Type'] = cache_type
        else:
            response.headers['X-From-Cache'] = from_cache

        return response

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def get_topo(path):
        return_code = 200

        # get topo info
        result, from_cache = query_topo_from_path(request.path)

        if type(result) is dict and result.get('return_code'):
            return_code = result.get('return_code')

        response = make_response(jsonify(result), return_code)

        # add cache info headers
        if from_cache:
            cache_type = topo_cache.__class__.__name__
            response.headers['X-From-Cache'] = from_cache
            response.headers['X-Cache-Type'] = cache_type
        else:
            response.headers['X-From-Cache'] = from_cache

        return response

    return app


