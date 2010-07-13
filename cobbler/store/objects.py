"""Cobbler's Object Store API (New as of Cobbler 2.2)

This object store design was inspired by the CouchDB Python Library as well 
as Django's Model and Form APIs.
"""

__docformat__ = 'restructuredtext en'

import simplejson as json

import logging
_log = logging.getLogger('objects')

# A list which records all item types created
_item_types = []

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
    _type = type(None)
    default = None
    tags = []
    
    def __init__(self, default=None, tooltip=None, display_name=None, tags=None,
                 visible=True):
        # Maybe add an inheritable attribute?  Is there any way to make it such
        # that you don't have to manually define default="<<inherit>>" every
        # time you do this?
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
        """This Field's getter"""
        return self._value
    
    def set(self):
        """This Field's setter"""
        if type(self) is not BaseField:
            super(type(self), self).__set__(instance, self._coerce(value))
        else:
            self._value = value
    
    def is_set(self):
        """Check if this Field has be set."""
        if self._value != self.default:
            return True
        else:
            return False
    
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
        if self.default is not None and isinstance(self.default, self._type):
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
        
        # Record the type of new items so we can ask for these later
        if cls_name is not 'BaseItem':
            _item_types.append(cls_name)
        
        return super(MetaItem, cls).__new__(cls, name, bases, attrs)


class BaseItem(object):
    """The Most Basic Item Class (From Which All Are Derived)
    
        - ``_requirements`` is a list of meta-requirements associated with the 
            given item.  Things which find their way here are generic enough
            problems that they have they own specification method outside of
            either an Item's or its Fields' validation methods.
    """
    __metaclass__ = MetaItem
    _requirements = []
    
    def __init__(self, load_handler, store_handler):
        self._load_handler = load_handler
        self._store_handler = store_handler
    
    def __str__(self):
        return unicode(self)
    
    def __unicode__(self):
        return json.encode(self, )
    
    def _load(self, handler=None):
        if not handler:
            self._load_handler(self)
    
    def _store(self, handler=None):
        if not handler:
            self._store_handler(self)
    
    def inflate(self, repr):
        """Take an object representation and use it to inflate this object
        
            - ``repr`` may be either a JSON string or a python dictionary.
            
        If a different format that JSON or a python dict is available, the 
        handling code should do the coercion prior to an inflation attempt.
        """
        repr = dict(repr)
        for key, val in repr:
            try:
                attr = getattr(self, key)
                if isinstance(attr, BaseField):
                    attr.set(val)
            except AttributeError:
                # Please ignore the fact that this attribute doesn't exist
                #   it is effectively unnecessary to log it (unless you
                #   _really_really_ want to.
                #
                # The try-block is used over a conditional, since it is
                #   the exceptional case that an attribute in a representation
                #   is not valid.  
                #
                # It _is_not_ the Item's responsibility to check validity of
                #   representations, only to check the validity of itself.
                #
                # Handling code which is introducing the representation should
                #   verify its validity all on its own.
                pass
    
    def deflate(self):
        """Return ``self`` as an object representation
        
        This method literally calls dict(self).
        
        If a different format that a python dict is preferable, the 
        handling code should do the coercion from a provided format (such
        as taking the deflated dict and munging that how it desires).
        """
        return dict(self)
                
    
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
        for req in _requirements:
            req.validate()
        return True


##############################################################################
### Default Fields ###########################################################


class BoolField(BaseField):
    default = False
    _coerce = bool
    _type = bool


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
    default = u""
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
### Requirements And Their Builders/Helpers ##################################


class BaseRequirement(object):
    def validate(self):
        """Validate the Given Requirement"""
        return True

    
class GroupRequirement(BaseRequirement):
    """Evaluate a Group of Conditions"""
    def __init__(self, cond_list, grouping="all", item=None):
        """
            - cond_list :  A list of callables which evaluate to a boolean 
                value.
            - grouping :  A number, "any", or "all"... Defines how many of the
                callables must evaluate to true in order to pass the 
                requirement. Negative values are treated as "at least" this 
                many, while positive values are treated as "exactly" this many.
                "any" effectively evaluates to -1.
        """
        self._cond_list = cond_list
        if grouping is "any":
            self._grouping = -1
        if grouping is "all":
            self._grouping = len(self._func_list)
        else:
            self._grouping = grouping
        #If item isn't set _now_, it _should_ be set in __new__
        self._item = item
    
    def validate(self):
        """
        Verify that the number of passing conditions matches the ``grouping`` 
        value set at instantiation.
        """
        
        passed = 0
        for cond in self._cond_list:
            if cond():
                 passed += 1
        if ((self._grouping < 0 and passed < abs(self._grouping)) or \
            passed < self._grouping):
            
            raise InvalidRequirement(
                u"Item of type %s failed a %s on a condition (%s)." % (
                    self._item.__class__.__name__, 
                    self.__class__.__name__, 
                    func.__name__,
                ))
        super(GroupRequirement, self).validate()

def require_one_of(*args):
    """
    ``args`` should be a list of Field objects.  Take this list and build an
    appropriate GroupRequirement.
    """
    return GroupRequirement(map(lambda x:x.is_set, args), grouping=1)
    
    
def require_any_of(*args):
    """
    ``args`` should be a list of Field objects.  Take this list and build an
    appropriate GroupRequirement.
    """
    return GroupRequirements(map(lambda x:x.is_set, args), grouping="any")


##############################################################################
### Default Items ############################################################

# TODO: This should probably be moved to a nice little configuration location,
#       since this is effectively going to be user pluggable... at the moment
#       this is likely unnecessary though, since Cobbler isn't in need of any
#       new Items as yet.


class Distro(BaseItem):
    _requirements = []
    
    name = StrField()
    owners = ListField()
    
    #profile = ItemChoiceField(choices=Profile)
    #image = ItemChoiceField(choices=Image)
    #_requirements.append(require_one_of(profile, image))
    
    kernel_options = DictField()
    kernel_options_post_install = DictField(
            display_name=u"Kernel Options (Post Install",
        )
    
    kickstart_metadata = DictField()
    kickstart = StrField(default=u"<<inherit>>")
    comment = StrField(tags=[u"TextField"])
    netboot_enable = BoolField()
    
    
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


class InvalidRequirement(CobblerValidationException):
    pass


class InvalidDefault(CobblerValidationException):
    pass


class InvalidChoice(CobblerValidationException):
    pass


class TypeNotFound(CobblerValidationException):
    pass


class InvalidFormat(CobblerValidationException):
    pass
