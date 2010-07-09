"""Cobbler's Object Store API (New as of Cobbler 2.2)

This object store design was inspired by the CouchDB Python Library as well 
as Django's Model and Form APIs.
"""

__docformat__ = 'restructuredtext en'

import simplejson as json

import logging
_log = logging.getLogger('objects')

##############################################################################
### The Heart of the Matter ##################################################


class MetaField(type):
    pass


class BaseField(object):
    """The Field type from which all are descended.
    
    Fields contain information relating to a specific attribute of an Item.
    They may be augmented with advanced functionality (such as references
    to Items) but at their most basic level represent standard serializable 
    types.
    """
    __metaclass__ = MetaField
    
    default = None
    
    def __init__(self):
        self._value = default
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return self._value
    
    def __set__(self, instance, value):
        self._value = value
    
    def __delete__(self, instance):
        self._fields.remove(self._name)
        super(BaseField, self).__delete__(self, instance)
    
    def __unicode__(self):
        return unicode(self._value)
    
    def __str__(self):
        return self.__unicode__()
    
    def validate(self):
        """The most basic Field validation method
        
        ``validate`` may be called directly, but is mainly called when 
        ``validate``ing an Item (this happens when trying to save an item 
        back to the object store for example).
        
        Expected results from calling ``validate``:
            - If the field is valid, ``validate`` returns a True value.
            - If the field is invalid, ``validate`` will ``raise`` an 
                appropriate Exception which subclasses the 
                CobblerValidationException.
        """
        if default is not None:
            return True
        else:
            raise InvalidDefault(
                    u"Field of type %s does not have a valid default value." %
                    self.__class__.__name__)


class MetaItem(type):
    """Metaclass For All Item Types
    
    This is what allows the nice magic of clean Item type declarations.
    
    Example::
    
        class Distro(Item):
            name = cobbler.objects.StrField(required=True)
            ...
    
    """
    # Pardon the logging barf sprinkled about... I figured it might be 
    # useful to have the creation of Item types be logged in case 
    # some configuration is malformed and needs to be debugged.
    
    _log = logging.getLogger('objects.MetaItem')
    def __new__(cls, cls_name, bases, attrs):
        if _log.getEffectiveLevel() <= logging.DEBUG:
            _log.DEBUG(u"Creating Item Type (%s)" % cls_name)
        
        # Build a nice happy logger for each Item type.
        if '_log' not in attrs:
            attrs['_log'] = logging.getLogger("objects.Item.%s" % cls_name)
        
        # Manipulate Field attributes on subclassed Items as needed
        # The Item class itself shouldn't have any Fields
        if '_fields' not in attrs:
            attrs['_fields'] = []
        for name, val in attrs.items():
            if isinstance(val, BaseField):
                if _log.getEffectiveLevel() <= logging.DEBUG:
                    _log.DEBUG(
                        u"Binding FieldType (%s) to Field (%s) on ItemType (%s)"% 
                        (val.__class__.__name__, attr, name)
                    )
                # It's always nice to know what you're called
                val._name = name
                attrs['_fields'].append(name)
        
        return super(MetaItem, cls).__new__(cls, name, bases, attrs)


class BaseItem(object):
    __metaclass__ = MetaItem
    
    def validate(self):
        """The most basic Item validation method
        
        The Item's ``validate`` method calls all member Fields' ``validate``
        methods, and returns ``True`` if they all pass.  If one does not
        pass, that Field will have thrown an exception which subclasses 
        CobblerValidationException.  This method does not catch such 
        exceptions.
        """
        for fld_name in self._fields:
            getattr(self, fld_name).validate()
        return True


##############################################################################
### Default Fields ###########################################################


class StrField(BaseField):
    default = ""
    
    def __set__(self, instance, value):
        super(StrField, self).__set__(instance, unicode(value))


class ListField(BaseField):
    default = []
    
    def __set__(self, instance, value):
        super(ListField, self).__set__(instance, list(value))


class DictField(BaseField):
    default = {}
    
    def __set__(self, instance, value):
        super(DictField, self).__set__(instance, dict(value))


#class StrawberryField(BaseField):
#   def forever(self):
#       return self.forever()


##############################################################################
### Default Items ############################################################

# TODO: This should probably be moved to a nice little configuration location,
#       since this is effectively going to be user pluggable... at the moment
#       this is likely unnecessary though, since Cobbler isn't in need of any
#       new Items as yet.


class Distro(BaseItem):
    owners = ListField()


class Image(BaseItem):
    pass


class Profile(BaseItem):
    pass


class System(BaseItem):
    pass


class Repo(BaseItem):
    pass


##############################################################################
### Object Store Exceptions ##################################################

## Validation exceptions ####################################################


class CobblerValidationException(Exception):
    pass


class InvalidDefault(CobblerValidationException):
    pass
