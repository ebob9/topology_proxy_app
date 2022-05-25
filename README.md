topology_proxy_app
----------

#### Synopsis
This Flask app listens on a HTTP port, and requests CloudGenix Topology API info based on the URL.

This is useful to allow simple TCP/HTTP monitoring apps that can't perform complex "REST API" requests/authn to do health checks and report on the CloudGenix Network Topology status.


#### Example

```GET http://127.0.0.1:8080/site/14903726461310212/path/14903726467600009```

```
{
  "_created_on_utc": 14903726479510039, 
  "_etag": 0, 
  "_schema": 0, 
  "_updated_on_utc": 0, 
  "network": "AT&T LTE", 
  "path_id": "14903726467600009", 
  "source_node_id": "14331248581420167", 
  "status": "up", 
  "target_circuit_name": "Lab Cradlepoint", 
  "target_node_id": "14903726461310212", 
  "type": "internet-stub", 
  "wan_nw_id": "14497548080350189"
} 
```

#### Features
* API caching and re-use.
* Query /site to get a full site list.
* Query /site/:siteid: to get a full topology links list.
* Query /site/:siteid:/swi/:swi_id: or /site/:siteid:/path/:swi_id: to retrieve a single swi_id/path_id.

#### Requirements
* Active CloudGenix Account
* Python >= 2.7 (3.x not tested yet)
* Python modules:
    * cloudgenix >=5.1.1b1 - <https://github.com/CloudGenix/sdk-python>
    * flask - <https://github.com/pallets/flask>
    * werkzeug - <https://github.com/pallets/werkzeug>
    * get_docker_secret (used for docker only) - 
    * 

#### Installation/Use
* Set CGX_AUTH_TOKEN environment variable to a static CloudGenix AUTH_TOKEN.
* Run `topo_app.py`. By default, `topo_app.py` listens on 0.0.0.0, port 8080.
  * Run `topo_app.py --help` for info on args and switches.

#### License
MIT

#### Version
Version | Changes
------- | --------
**2.0.3**| Update to 5.6.2b2 SDK, latest flask & migrate to cachelib
**2.0.2**| Memcached and Simple Cache support (never pushed to github)
**2.0.1**| Fix for high multi-threading worker issue (CGX sdk /tmp file for CA Verify)
**2.0.0**| Update for Docker Container and static AUTH_TOKEN support (removes user/password support)
**1.1.0**| Update to replace Dict cache with SimpleCache() and also support MemcachedCache().
**1.0.0**| Initial Release.
