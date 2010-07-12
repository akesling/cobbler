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
    
    _coerce = lambda x:x
    default = None
    tags = []
    
    def __init__(self, default=None, tooltip=None, display_name=None, tags=None,
                 visible=True):
        self.default = default or type(self).default
        self.tags = list(tags or type(self).tags)
        self.visible = bool(visible)
        self._value = self.default
    
    def __set__(self, instance, value):
        self.set(value)
    
    def __delete__(self, instance):
        self._fields.remove(self._name)
        super(BaseField, self).__delete__(self, instance)
    
    def __unicode__(self):
        return unicode(self._value)
    
    def __str__(self):
        return self.__unicode__()
    
    def get(self):
        return self._value
    
    def set(self):
        if type(self) is not BaseField:
            super(type(self), self).__set__(instance, self._coerce(value))
        else:
            self._value = value
    
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
        if self.default is not None and type(self.default) is self._type:
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
                if not hasattr(val, 'display_name'): 
                    val.display_name = " ".join(
                            map(str.capitalize, val._name.split("_")))
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


class DictField(BaseField):
    default = {}
    _coerce = dict
    _type = dict


class FloatField(BaseField):
    default = 0.0
    _coerce = float
    _type = float


class IntField(BaseField):
    default = 0
    _coerce = int
    _type = int


class ListField(BaseField):
    default = []
    _coerce = list
    _type = list


class StrField(BaseField):
    default = ""
    _coerce = unicode
    _type = unicode


#class StrawberryField(BaseField):
#   def forever(self):
#       return self.forever()


##############################################################################
### Extended Fields ##########################################################


class ChoiceField(StrField):
    def __init__(self, choices, **kwargs):
        self.choices = list(choices)
        super(ChoiceField, self).__init__(**kwargs)
    
    def validate(self):
        if self._value not in self.choices:
            raise InvalidChoice(
            u"Field of type %s contains a value not in its list of choices." %
            self.__class__.__name__)
        super(ChoiceField, self).validate()


##############################################################################
### Default Items ############################################################

# TODO: This should probably be moved to a nice little configuration location,
#       since this is effectively going to be user pluggable... at the moment
#       this is likely unnecessary though, since Cobbler isn't in need of any
#       new Items as yet.


class Distro(BaseItem):
    name = StrField()
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


class InvalidChoice(CobblerValidationException):
    pass
