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

types = (
    'base',
)

##############################################################################
### Base Handlers ############################################################

_active_items = []
_items = {}

def base_boot_handler():
    return True

def base_find_handler(criteria, slice=['_uid']):
    def slice_item(item, slice):
        record = []
        for attr in slice:
            record.append(getattr(item, attr).get())
        return tuple(record)
    
    slice = list(slice)
    if '_uid' not in slice:
        slice.insert(0, '_uid')
    
    result = []
    for uid, item in _items.iteritems():
        for name, value in criteria.iteritems():
            if getattr(item, name).get() != value:
                break
        else:
            result.append(item)
    return map(lambda x: slice_item(x, slice), result)

def base_load_handler(uid):
    try:
        return _items[uid]
    except KeyError:
        raise ItemNotFound(
            "The Item you have requested with uid %s does not exist." % uid)
    return True

def base_store_handler(item):
    if item._uid.get() in _active_items:
        _items[item._uid.get()] = item
    return True
    
def base_register_handler(uid):
    _active_items.append(uid)
    return True

def base_remove_handler(uid):
    _active_items.remove(uid)
    if uid in _items:
        del _items[uid] 
    return True

##############################################################################
### Other Handlers ###########################################################
