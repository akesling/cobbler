# Settings configuration for Cobbler Client API

xmlrpc_port = "25151"
http_port   = "80"
server      = "127.0.0.1"
cobbler_url = "http://%s:%s/cobbler_api" % (server, http_port)
run_local = True
