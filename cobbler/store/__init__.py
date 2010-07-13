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

import objects, handlers

def get(uid):
    pass

def get_types():
    return objects._item_types

def set(obj):
    pass

def find(criteria):
    pass

def new(obj_type):
    if obj_type in get_types():
        obj = getattr(objects, obj_type)(
            load_handler=handlers.base_load_handler(),
            store_handler=handlers.base_store_handler(),
        )
        return obj
    else:
        raise objects.TypeNotFound(
            "The object type %s is not presently defined." % obj_type)
