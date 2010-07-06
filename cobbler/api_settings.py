# Settings configuration for Cobbler Client API

xmlrpc_port = "25151"
http_port   = "80"
server      = "127.0.0.1"
default_url = "http://%s:%s/cobbler_api"
cobbler_url = default_url % (server, http_port)
run_local = True
