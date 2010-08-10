"""The Object Handlers for Cobbler's Object Store
 
The handlers used for all objects fit into a small set of functions.  The 
functionality currently provided is:
    * boot  (run varying related tasks at Object Store boot time)
    * find  (find which objects fit certain criteria)
    * load  (actually load an object from the store)
    * store (update the item in the store)

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
    'test',
)

##############################################################################
### Base Handlers ############################################################

_active_items = []
_items = {}

def base_boot():
    return True

def base_find(criteria, slice=['_uid']):
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

def base_load(uid):
    try:
        return _items[uid].deflate()
    except KeyError:
        raise ItemNotFound(
            "The Item you have requested with uid %s does not exist." % uid)
    return True

def base_store(item):
    if item._uid.get() in _active_items:
        _items[item._uid.get()] = item
    return True
    
def base_register(uid):
    _active_items.append(uid)
    return True

def base_remove(uid):
    _active_items.remove(uid)
    if uid in _items:
        del _items[uid] 
    return True

##############################################################################
### Test Handlers ############################################################

# These handlers are used for the test suite, so as to be able to not be able
# to test everything (other than the handlers themselves) without interfering
# with any existing configuration

_test_active_items = []
_test_items = {}

def test_boot():
    return True

def test_find(criteria, slice=['_uid']):
    def slice_item(item, slice):
        record = []
        for attr in slice:
            record.append(getattr(item, attr).get())
        return tuple(record)
    
    slice = list(slice)
    if '_uid' not in slice:
        slice.insert(0, '_uid')
    
    result = []
    for uid, item in _test_items.iteritems():
        for name, value in criteria.iteritems():
            if getattr(item, name).get() != value:
                break
        else:
            result.append(item)
    return map(lambda x: slice_item(x, slice), result)

def test_load(uid):
    try:
        return _test_items[uid].deflate()
    except KeyError:
        raise ItemNotFound(
            "The Item you have requested with uid %s does not exist." % uid)
    return True

def test_store(item):
    if item._uid.get() in _test_active_items:
        _test_items[item._uid.get()] = item
    return True
    
def test_register(uid):
    _test_active_items.append(uid)
    return True

def test_remove(uid):
    _test_active_items.remove(uid)
    if uid in _test_items:
        del _test_items[uid] 
    return True

def test_flush():
    # clean up the "store" so that tests don't interfere with each other
    global _test_active_items, _test_items
    _test_active_items, _test_items = [], {}

##############################################################################
### Other Handlers ###########################################################
