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
    assignment. An effort is made to make sure all such names are actions
    though, so that shouldn't be a problem when naming Fields.
    
"""

from store_exceptions import *
import objects
import handlers
import time
import random
#import base64

import config

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
    """Create a nice shiny new UID
    
    *Arguments:*

        ``ctime``
            If you desire a UID for an object which was create at time 
            ``ctime`` then you may provide that value.
 
    *Return Value:*
        A canonical Cobbler UID.
    """
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


def get(uid, source=None):
    """Get the Item represented by the provided UID
    
    *Arguments:*

        ``uid``
            A valid UID.
        ``source``
            The origin for the handlers used.  ``base`` represents the
            default *internal* handler used by cobbler, but other handler
            sources are planned to be provided.
    
    *Return Value:*
        An Item object.
    """
    if not source: source = config.default_source
    if source not in handlers.types:
        raise InvalidSource(
            "The object source of '%s' is not provided." % source)
    
    repr = getattr(handlers, source+'_load')(uid)
    obj = objects._item_types[repr['_type'][0]](
            load_handler=getattr(handlers, source+'_load'),
            store_handler=getattr(handlers, source+'_store'),
        )
    # TODO: This should handle logging Field setter exceptions when inflation
    #       of a field fails.
    obj.inflate(repr)
    return obj


def get_types():
    """Return all types available along with their signatures
    
    *Return Value:*
        A list of 2-tuples where the first item is the Type's name 
        and the second item is the Type's signature as a dictionary.
    """
    # TODO: Allow getting of types other than base types
    return objects._item_types.keys()


def set(item):
    """Store provided Item in the Object Store
    
    *Arguments:*
    
        ``item``
            The item to store in the Object Store.
    
    *Return Value:*
        ``True`` on successful call to the ``validate`` method of the 
        provided Item, and ``False`` when validation fails.  If errors 
        are desired, they may be found directly on the object so there 
        is no need to return them.
    """
    # TODO: This should handle logging of validation exceptions
    if item.validate():
        item._store()
        return True
    else:
        return False


def find(criteria, slice=["_uid"], source=None):
    """Find items matching the given criteria
    
    *Arguments:*
    
        ``criteria``
            A dictionary mapping Field name to value required to match.
        ``slice``
            A list of the desired object attributes.        
        ``source``
            The origin for the handlers used.  ``'base'`` represents the
            default *internal* handler used by cobbler, but other handler
            sources are planned to be provided.
    
    *Return Value:*
        A list of tuples containing the requested information.  
        The tuples returned will be ordered in the same fashion as 
        ``slice``.  Whether specified in the slice list or not, the 
        first property in the tuples returned will always be that 
        Item's ``_uid``.  All duplicates and invalid properties in the
        slice list will be ignored/removed from output.
    """
    if not source: source = config.default_source
    if source not in handlers.types:
        raise InvalidSource(
            "The object source of '%s' is not provided." % source)
    
    no_dups = ['_uid']
    for prop in slice:
        if prop in no_dups:
            continue
        else:
            no_dups.append(prop)
    
    return getattr(handlers, source+'_find')(criteria, no_dups)


def new(item_type, source=None):
    """Request a blank Item of the provided type
    
    *Arguments:*

        ``item_type``
            The type of Item which you would like.
        ``source``
            The origin for the handlers used.  ``base`` represents the
            default *internal* handler used by cobbler, but other handler
            sources are planned to be provided.
 
    *Return Value:*
        A blank Item with the default handlers bound to it and populated 
        with its own UID, Creation Time, and Modification Time.
    """
    if not source: source = config.default_source
    if source not in handlers.types:
        raise InvalidSource(
            "The object source of '%s' is not provided." % source)
    
    
    if item_type in get_types():
        item = objects._item_types[item_type](
            load_handler=getattr(handlers, source+'_load'),
            store_handler=getattr(handlers, source+'_store'),
        )
        ctime = time.time()
        item._uid.set(_create_uid(ctime))
        item._ctime.set(ctime)
        item._mtime.set(ctime)
        # Make the object store aware there is a new unstored Item
        getattr(handlers, source+'_register')(item._uid.get())
        return item 
    else:
        raise TypeNotFound(
            "The object type %s is not presently defined." % item_type)
