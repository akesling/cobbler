"""The "Public" Face of Cobbler's Object Store
    
    The functions defined herein (ignoring sub-modules) should be the
    only ones used to access the object store.
    
    Most object attributes which are reserved
    (including the attribute representing type) are preprended with
    an underscore.  For example, to find all objects of the Distro 
    type one must use the find criteria {"_type":"Distro"}.  This is
    intended to prevent collisions with Field names and allow 
    developers to define field names as best fits their problem.
    
    It should, however, be noted that there are still certain reserved
    keywords, such as ``validate``, which are not available for Field
    assignment.
"""

from store_exceptions import *
import objects
import handlers
import time
import random
#import base64

__all__ = (
    'get',
    'get_types',
    'set',
    'find',
    'new',
)


##############################################################################
### Helper Functions #########################################################


def _create_uid(ctime=None):
    # It _really_ doesn't matter what style of UID is used, as long as they
    # are unique.
    
    # Preference would be to use the following, but it was decided to keep
    # with the 2.0.x/2.1.x UID style for backward replicate compatibility:
    if not ctime: ctime = time.time()
    return "%016f::%010d" % (ctime, random.randint(0,1e10-1))
    #data = "%s%s" % (time.time(), random.uniform(1,9999999))
    #return base64.b64encode(data).replace("=","").strip()


##############################################################################
### Object Store "Public" Interface ##########################################


def get(uid, source='base'):
    if source not in handlers.types:
        raise InvalidSource()
    
    repr = getattr(handlers, source+'_load_handler')(uid)
    obj = getattr(objects, repr['_type'])(
            load_handler=handlers.base_load_handler,
            store_handler=handlers.base_store_handler,
        )
    # TODO: This should handle logging Field setter exceptions when inflation
    #       of a field fails.
    obj.inflate(repr)
    return obj


def get_types():
    # TODO: Allow getting of types other than base types
    return objects._item_types


def set(obj):
    # TODO: This should handle logging of validation exceptions
    obj.validate()
    obj._store()


def find(criteria, source='base'):
    if source not in handlers.types:
        raise InvalidSource(
            "The object source of %s is not provided." % source)
    
    return getattr(handlers, source+'_find_handler')(criteria)


def new(obj_type, source='base'):
    if source not in handlers.types:
        raise InvalidSource()
    
    if obj_type in get_types():
        obj = getattr(objects, obj_type)(
            load_handler=handlers.base_load_handler,
            store_handler=handlers.base_store_handler,
        )
        ctime = time.time()
        obj._uid = _create_uid(ctime)
        obj._ctime = cur_time
        obj._mtime = cur_time
        return obj
    else:
        raise objects.TypeNotFound(
            "The object type %s is not presently defined." % obj_type)

