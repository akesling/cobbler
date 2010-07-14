"""The Object Handlers for Cobbler's Object Store

The handlers used for all objects fit into a small set of functions.  The 
functionality currently provided is:
    - boot  (run varying related tasks at Object Store boot time)
    - find  (find which objects fit certain criteria)
    - load  (actually load an object from the store)
    - store (update the item in the store)

Handlers are also split into which sources they reference (since handlers are
what tie into the actual exactly what backend is used.)  Currently only the 
most basic handlers are provided which tie into what is effectively a local
Cobbler database.  The plan is to provide backends for varying resources (such
as (potentially) CouchDB and SQLAlchemy). If you want a different backend
than what is currently available, feel free to implement your own handlers 
based off of those provided.
"""

from store_exceptions import *

##############################################################################
### Base Handlers ############################################################

def base_boot_handler():
    pass

def base_find_handler(criteria):
    pass

def base_load_handler(uid):
    pass

def base_store_handler(item):
    pass

##############################################################################
### Other Handlers ###########################################################
