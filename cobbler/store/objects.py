"""Cobbler's Object Store API (New as of Cobbler 2.2)

This object store design was inspired by the CouchDB Python Library as well 
as Django's Model and Form APIs.
"""

__docformat__ = 'restructuredtext en'

import time, datetime

from store_exceptions import *

import logging
LOG_PREFIX = 'store.objects'
_log = logging.getLogger(LOG_PREFIX)

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
                 visible=True, editable=True, required=False):
        # Maybe add an inheritable attribute?  Is there any way to make it such
        # that you don't have to manually define default="<<inherit>>" every
        # time you do this?
        self.default = default or type(self).default
        self.editable = editable
        self.tags = list(tags or type(self).tags)
        self.visible = bool(visible)
        self._value = self.default
        
        # TODO: fix validate code for requirement... at the moment it catches
        #       on default being None... but it doesn't output a clean error
        self.required = required
        self.default = None
    
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
    
    def set(self, value):
        """This Field's setter"""
        self._value = self._coerce(value)
    
    def is_set(self):
        """Check if this Field has been set."""
        if None != self._value != self.default:
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
        if self._value is not None and isinstance(self._value, self._type):
            return True
        else:
            raise InvalidValue(
                    u"Field '%s' of type '%s' does not " \
                    u"have a valid value (%s)." %
                    (self._name, self.__class__.__name__, self._value))


##############################################################################
### Default Fields ###########################################################


class BoolField(BaseField):
    default = False
    _coerce = bool
    _type = bool


class DateTimeField(BaseField):
    # Don't bother coercing datetime... if it's invalid it's invalid
    _coerce = lambda x:x
    _type = datetime.datetime
    
    def __init__(self, *args, **kwargs):
        self.default = datetime.datetime.now()
        super(DateTimeField, self).__init__(self, *args, **kwargs)


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


class TimeField(FloatField):
    default = 0.0
    def __init__(self, *args, **kwargs):
        self.default = time.time()
        super(TimeField, self).__init__(self, *args, **kwargs)


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
### Items ####################################################################


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
    
    _log = logging.getLogger(LOG_PREFIX+'.MetaItem')
    def __new__(cls, cls_name, bases, attrs):
        if _log.getEffectiveLevel() <= logging.DEBUG:
            _log.DEBUG(u"Creating Item Type (%s)" % cls_name)
        
        # Build a nice happy logger for each Item type.
        if '_log' not in attrs:
            attrs['_log'] = logging.getLogger(LOG_PREFIX+'.Item.%s' % cls_name)
        
        
        # Manipulate Field attributes on subclassed Items as needed
        
        if '_fields' not in attrs:
            attrs['_fields'] = []
        if '_requirements' not in attrs:
            attrs['_requirements'] = []
        # Make sure that subclassing doesn't destroy field or requirement 
        # information
        for base in bases:
            if hasattr(base, '_fields'):
                attrs['_fields'].extend(base._fields)
            if hasattr(base, '_requirements'):
                attrs['_requirements'].extend(base._requirements)
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
        
        # Bind the object's name to it's requirements so that we
        # can return clearer errors.
        for req in attrs['_requirements']:
            if not req._item:
                req._item = item
        
        # Record the type of new items so we can ask for these later
        if cls_name is not 'BaseItem':
            _item_types.append(cls_name)
        
        return super(MetaItem, cls).__new__(cls, name, bases, attrs)


class ItemIterator(object):
    #Because having __dict__ is absolutely unnecessary
    __slots__ = ['item', 'count']
    
    def __init__(self, item):
        self.item = item
        self.count = 0
    
    def next(self):
        name = self.item._fields[self.count]
        field = getattr(self.item, name)
        self.count += 1
        return name, field


class BaseItem(object):
    """The Most Basic Item Class (From Which All Are Derived)
    
        - ``_requirements`` is a list of meta-requirements associated with the 
            given item.  Things which find their way here are generic enough
            problems that they have they own specification method outside of
            either an Item's or its Fields' validation methods.
    """
    __metaclass__ = MetaItem
    _requirements = []
    
    #Fields
    # _uid, _mtime, and _ctime management occur within the handlers
    # primarily because these relate to object management more than
    # the data an Item represents.
    _uid = StrField(required=True, editable=False)
    _mtime = TimeField(required=True, editable=False)
    _ctime = TimeField(required=True, editable=False)
    
    def __init__(self, load_handler, store_handler):
        self._load_handler = load_handler
        self._store_handler = store_handler
    
    def __iter__(self):
        return ItemIterator(self)
    
    def __str__(self):
        return unicode(self)
    
    def __unicode__(self):
        return unicode(dict(self))
    
    def _load(self, handler=None):
        if not handler:
            repr = self._load_handler(self._uid)
        else:
            repr = handler(self)
        
        self.inflate(repr)
    
    def _store(self, handler=None):
        if not handler:
            self._store_handler(self)
    
    def inflate(self, repr):
        """Take an object representation and use it to inflate this object
        
            - ``repr`` must be coercible into a functional python dictionary.
            
        If a different format than a python dict is available, the handling 
        code should do the coercion prior to an inflation attempt.
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
        
        If a different format than a python dict is preferable, the 
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
        for req in self._requirements:
            req.validate()
        return True



##############################################################################
### Requirements And Their Builders/Helpers ##################################


class BaseRequirement(object):
    def validate(self):
        """Validate the Given Requirement"""
        return True

    
class GroupRequirement(BaseRequirement):
    """Evaluate a Group of Conditions"""
    def __init__(self, cond_list, grouping="all", group_name=None, item=None):
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
        # If item isn't set _now_, it _should_ be set in __new__
        self._item = item
        
        # Wouldn't it be nice if we had a name for our group?  That seems
        # like it could make errors _so_ much cleaner.
        self._group_name = group_name
    
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
                    self._group_name or repr(func),
                ))
        super(GroupRequirement, self).validate()

def require_one_of(*args):
    """
    ``args`` should be a list of Field objects.  Take this list and build an
    appropriate GroupRequirement.
    """
    return GroupRequirement(
            map(lambda x:x.is_set, args), 
            group_name=" ".join(map(lambda x:x._name, args)), 
            grouping="any",
           )
    
    
def require_any_of(*args):
    """
    ``args`` should be a list of Field objects.  Take this list and build an
    appropriate GroupRequirement.
    """
    return GroupRequirements(
            map(lambda x:x.is_set, args), 
            group_name=" ".join(map(lambda x:x._name, args)), 
            grouping="any",
           )


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
            display_name=u"Kernel Options (Post Install)",
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
