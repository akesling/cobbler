import xmlrpclib
import api_settings as settings

try:
    from cobbler import utils
except ImportError:
    utils = None
    

class CobblerAPI(xmlrpclib.Server, object):
    
    def __init__(self, url=None, username=None, password=None, *args, **kwargs):
        if not url: url = settings.cobbler_url
        self._url = url
        
        if utils and settings.run_local:
            self._shared_secret = utils.get_shared_secret() 
        else:
            self._shared_secret = None
        
        kwargs.update({'allow_none': True})
        xmlrpclib.Server.__init__(self, self._url, *args, **kwargs)
        
        if username and password:
            self.token = self.login(username, password)
        elif self._shared_secret:
            self.token = self.login("", self._shared_secret)
    
    def __getattr__(self, name):
        return xmlrpclib.Server.__getattr__(self, name)
