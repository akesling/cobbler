import xmlrpclib
import api_settings as settings

try:
    from cobbler import utils
except ImportError:
    utils = None
    

class CobblerAPI(xmlrpclib.Server, object):
    
    def __init__(self, url=None, user=None, password=None):
        if not url: url          = settings.cobbler_url
        self._url = url
        print url
        
        if utils and settings.run_local:
            self._shared_secret  = utils.get_shared_secret() 
        else:
            self._shared_secret  = None
        
        super(CobblerAPI, self).__init__(self._url)
    
    def __getattr__(self, name):
        if hasattr(self, name):
            return object.__getattr__(self, name)
        else:
            return super(CobblerAPI, self).__getattr__(name)
