"""Cobbler's Object Store API (New as of Cobbler 2.2)

This object store design was inspired by the CouchDB Python Library as well 
as Django's Model and Form APIs.
"""

__all__ = []
__docformat__ = 'restructuredtext en'

import time, datetime
import os

from store_exceptions import *
import __init__ as store

import logging
LOG_PREFIX = 'store.objects'
_log = logging.getLogger(LOG_PREFIX)

# A list which records all item types created
_item_types = []

# TODO: Implement Field value inheritance.  This will likely be done through 
#       The declaration of a _parents Field on the child, and "<<inherit>>"
#       being the value of the field when inheritance is desirable.

##############################################################################
### The Heart of the Matter ##################################################

__all__.extend((
    'BaseField',
))


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
                 visible=True, editable=True, required=False, comment="", 
                 inherit=False):
        # Maybe add an inheritable attribute?  Is there any way to make it such
        # that you don't have to manually define default="<<inherit>>" every
        # time you do this?
        if not (default == "<<inherit>>" and inherit):
            if default:
                self.default = self._coerce(default)
            else:
                self.default = self._coerce(self.default)
        
        
        self.required = required
        if not default and required:
            self.default = None
        
        self.inherit = inherit
        if default == "<<inherit>>" and inherit:
            self.default = default
        
        self.comment = unicode(comment)
        self.editable = editable
        self.tags = list(tags or type(self).tags)
        self.visible = bool(visible)
        
        self._value = None
        
    
    def __set__(self, instance, value):
        self.set(value)
    
    def __delete__(self, instance):
        self._fields.remove(self._name)
        super(BaseField, self).__delete__(self, instance)
    
    def __unicode__(self):
        return unicode(self._value)
    
    def __str__(self):
        return unicode(self)
    
    def __repr__(self):
        return u"<class '%s': default='%s' >" % \
            (self.__class__.__name__, unicode(self.default))
    
    def get(self):
        """This Field's getter"""
        if self._value is not None:
            return self._value
        else:
            return self.default
    
    def set(self, value):
        """This Field's setter"""
        if self.inherit and value == "<<inherit>>":
            self._value = value
        else:
            self._value = self._coerce(value)
    
    def is_set(self):
        """Check if this Field has been set."""
        if None != self._value:
            return True
        else:
            return False
    
    def validate(self):
        """The most basic Field validation method
        This method verifies that the value returned by ``get()`` is not 
        None and that it is of the type defined by ``self._type``.
        
        ``validate`` may be called directly, but is mainly called when 
        validating an Item.  You can (and should) validate all Items you 
        are working on whenever you need to check validity, but be aware
        that this routine is also called when trying to save an Item back
        to the object store.
        
        Expected results from calling ``validate``:
            * If the field is valid, ``validate`` returns a True value.
            * If the field is invalid, ``validate`` will ``raise`` an 
              appropriate Exception which subclasses
              CobblerValidationException.
        """
        value = self.get()
        if (isinstance(value, self._type) \
                         or (self.inherit and value == "<<inherit>>")):
            return True
        else:
            if self.required and self._value is None:
                raise InvalidValue(
                        u"Field '%s' of type '%s' is required." %
                        (self._name, self.__class__.__name__))
            else:
                raise InvalidValue(
                        u"Field '%s' of type '%s' does not " \
                        u"have a valid value (%s)." %
                        (self._name, self.__class__.__name__, self._value))


##############################################################################
### Default Fields ###########################################################

__all__.extend((
    'BoolField',
    'DateTimeField',
    'DictField',
    'FloatField',
    'IntField',
    'ListField',
    'StrField',
    'TimeField',
))


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
    def __init__(self, *args, **kwargs):
        self.default = time.time()
        super(TimeField, self).__init__(*args, **kwargs)


#class StrawberryField(BaseField):
#   def forever(self):
#       return self.forever()


##############################################################################
### Extended Fields ##########################################################

__all__.extend((
    'ChoiceField',
    'ItemField',
))


class ChoiceField(StrField):
    def __init__(self, choices, *args, **kwargs):
        self.choices = list(choices)
        super(ChoiceField, self).__init__(*args, **kwargs)
    
    def validate(self):
        if self.get() not in self.choices:
            raise InvalidChoice(
            u"Field '%s' of type '%s' contains a value" \
             " (%s) not in its list of choices." %
            (self._name, self.__class__.__name__, self._value))
        super(ChoiceField, self).validate()


class ItemField(StrField):
    
    def __init__(self, item_type, *args, **kwargs):
        self.item_type = self._coerce(item_type)
        super(ItemField, self).__init__(*args, **kwargs)
    
    def get_ref(self):
        """Get the object which this field represents.
     
        *Return Value:*
            If this field represents a valid Item, then it returns that Item.
            
            Else it returns False
        """

        if self.validate() and bool(self._value) == True:
            return store.get(
                store.find({'_type': self.item_type, 'name': self.get()})[0])
        else:
            return False
    
    def validate(self):
        exists = lambda t,n: len(store.find({'_type': t, 'name': n}))
        if (self.is_set() or self.required) and \
                not exists(self.item_type, self.get()):
            #print ''
            #print self.get(), self._value, self.default, self.inherit, self.required
            
            if self.required and self.inherit and self.get() == "<<inherit>>":
                #This if-case is here because rendering could be expensive
                rendered = self._item.render()
                if not exists(self.item_type, rendered[self._name]):
                    raise InvalidItem(
                    u"Field '%s' of type '%s' has been unable to properly"
                     " inherit a valid Item. The rendered result returned" \
                     " the name '%s' and type '%s'." %
                    (self._name, self.__class__.__name__, rendered[self._name], 
                    self.item_type))
            else:
                raise InvalidItem(
                u"Field '%s' of type '%s' cannot find an Item" \
                 " with the name '%s' and type '%s'." %
                (self._name, self.__class__.__name__, self.get(), 
                self.item_type))
                
        return super(ItemField, self).validate()

class LocalFileField(StrField):
    def validate(self):
        value = self.get()
        
        if (self.is_set() or self.required) and \
             (value == None or not os.access(os.path.abspath(value), os.R_OK)):
            raise FileNotFound(
            u"Field '%s' of type '%s' contains a value" \
             " (%s) which does not refer to a readable file." %
            (self._name, self.__class__.__name__, self._value))
        return super(LocalFileField, self).validate()
        

##############################################################################
### Items ####################################################################

__all__.extend((
    'BaseItem',
))

def _attach_fields(cls, cls_name, bases, attrs):
    # Manipulate Field attributes on subclassed Items as needed
    
    if '_fields' not in attrs:
        attrs['_fields'] = []
    # Make sure that subclassing doesn't destroy field information
    for base in bases:
        if hasattr(base, '_fields'):
            attrs['_fields'].extend(base._fields)
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
            
    
    
def _attach_reqs(cls, cls_name, bases, attrs):
    if '_requirements' not in attrs:
        attrs['_requirements'] = []
    # Make sure that subclassing doesn't destroy or requirement information
    for base in bases:
        if hasattr(base, '_requirements'):
            attrs['_requirements'].extend(base._requirements)
    # Bind the object's name to it's requirements so that we
    # can return clearer errors.
    for req in attrs['_requirements']:
        if not callable(req) and not req._item:
            req._item = item


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
        
        if '_type' not in attrs:
            attrs['_type'] = StrField(default=cls_name, editable=False)
        
        _attach_fields(cls, cls_name, bases, attrs)
        _attach_reqs(cls, cls_name, bases, attrs)
        
        # Record the type of new items so we can ask for these later
        if cls_name is not 'BaseItem':
            _item_types.append(cls_name)
        
        return super(MetaItem, cls).__new__(cls, cls_name, bases, attrs)
    
    
class ItemIterator(object):
    #Because having __dict__ is absolutely unnecessary
    __slots__ = ['item', 'count', 'len']
    
    def __init__(self, item):
        self.item = item
        self.len = len(item._fields)
        self.count = 0
    
    def next(self):
        if self.count >= self.len:
            raise StopIteration()
        name = self.item._fields[self.count]
        value = getattr(self.item, name).get()
        self.count += 1
        return name, value


class BaseItem(object):
    """The Most Basic Item Class (From Which All Are Derived)
    
        * ``_requirements`` is a list of meta-requirements associated with the 
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
        self._errors = []
        self._load_handler = load_handler
        self._store_handler = store_handler
        
        # It's always nice to know who you're a member of
        for field in self._fields:
            getattr(self, field)._item = self
    
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
        if self.validate():
            if not handler:
                if self._store_handler(self):
                    return True
                else:
                    return False
            else:
                if handler(self):
                    return True
                else:
                    return False
        else:
            return False
        
    
    def inflate(self, repr):
        """Take an object representation and use it to inflate this object
        
            * ``repr`` must be coercible into a functional python 
              dictionary.
            
        If a different format than a python dict is available, the handling 
        code should do the coercion prior to an inflation attempt.
        """
        repr = dict(repr)
        for key, val in repr.iteritems():
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
        
        This method literally calls ``dict(self)``.
        
        If a different format than a python dict is preferable, the 
        handling code should do the coercion from a provided format (such
        as taking the deflated dict and munging that how it desires).
        """
        return dict(self)
                
    def render(self, inheritance_path=[]):
        """By default ``render`` is a synonym for ``deflate``
        
        However, if special actions (such as Item level inheritance) are
        desired at configuration time (such as when generating kickstarts,
        or when using Koan) then this should be overridden in the Item's
        declaration.
        """
        # Note that the following block is in fact unnecessary when in BaseItem.
        # But because it is required pretty much everywhere else... it is 
        # included here for homogeneity.
        
        # This makes inheritance acyclic... ----------------------------------
        # INCLUDE THIS WITH ALL INHERITANCE CODE -----------------------------
        if self in inheritance_path:
            return self.deflate()
        inheritance_path.append(self)
        # --------------------------------------------------------------------
        
        return self.deflate()
    
    def validate(self):
        """The most basic Item validation method
        
        The Item's ``validate`` method calls all member Fields' and 
        Requirements'``validate`` methods, catching any 
        CobblerValidationExceptions thrown on failure of Field and/or 
        Requirement validation.
        
        You can (and should) validate all Items you are working on whenever 
        you need to check validity, but be aware that this routine is also 
        called when trying to save an Item back to the object store.
        
        Expected results from calling ``validate``:
            * If all Fields and Requirements are valid, ``validate`` 
                returns a ``True`` value.
            * If any Field or Requirement is invalid, ``validate`` will 
                save the associated exceptions in ``self._errors`` and 
                return a ``False`` value.
        """
        # Assume this Item is valid until proven otherwise.
        valid = True
        self._errors = []
        for fld_name in self._fields:
            try:
                getattr(self, fld_name).validate()
            except CobblerValidationException, cve:
                valid = False
                self._errors.append((fld_name, cve))
        for req in self._requirements:
            if callable(req): req = req(self)
            
            try:
                req.validate()
            except CobblerValidationException, cve:
                valid = False
                self._errors.append((req._group_name, cve))
        return valid


##############################################################################
### Requirements And Their Builders/Helpers ##################################

__all__.extend((
    'BaseRequirement',
    'GroupRequirement',
    'require_one_of',
    'require_any_of',
))

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
        Verify that the number of passing conditions matches the 
        ``grouping`` value set at instantiation.
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
    
    It should be noted that requirement generation may be lazily evaluated
    (as it is in the case of this function).  Lazy evaluation is faked in the
    requirements system by allowing requirements passed into an Item to be a
    callable which builds and returns a requirement.
    """
    def lazy(item): 
        req = GroupRequirement(
            map(lambda x:x.is_set, args), 
            group_name="Require One of: %s" % 
                ", ".join(map(lambda x:x._name, args)), 
            grouping="1",
        )
        req._item = item
        return req

    return lazy
    
def require_any_of(*args):
    """
    ``args`` should be a list of Field objects.  Take this list and build an
    appropriate GroupRequirement.
    
    It should be noted that requirement generation may be lazily evaluated
    (as it is in the case of this function).  Lazy evaluation is faked in the
    requirements system by allowing requirements passed into an Item to be a
    callable which builds and returns a requirement.
    """
    def lazy(item): 
        req = GroupRequirement(
            map(lambda x:x.is_set, args), 
            group_name="Require Any of: %s" % 
                ", ".join(map(lambda x:x._name, args)), 
            grouping="any",
        )
        req._item = item
        return req
    
    return lazy

##############################################################################
### Default Items ############################################################

__all__.extend((
    'Distro',
    'Image',
    'Profile',
    'System',
    'Repo',
))

# TODO: This should probably be moved to a nice little configuration location,
#       since this is effectively going to be user pluggable... at the moment
#       this is likely unnecessary though, since Cobbler isn't in need of any
#       new Items as yet.


class Distro(BaseItem):
    _requirements = []
    
    name = StrField(required=True)
    owners = ListField()
    
    distro = ItemField('Distro')
    
    def render(self, inheritance_path=[]):
        # This makes inheritance acyclic... ----------------------------------
        # INCLUDE THIS WITH ALL INHERITANCE CODE -----------------------------
        if self in inheritance_path:
            return self.deflate()
        inheritance_path.append(self)
        # --------------------------------------------------------------------
        
        rendered = super(Distro, self).render(inheritance_path)
        parent = self.profile.get_ref().render(inheritance_path)
        for field, value in rendered:
            if value == "<<inherit>>":
               rendered[field] = parent[field] 
        return rendered
    
    kernel = LocalFileField(
        required=True,
        comment="Absolute path to kernel on filesystem"
        )
    initrd = LocalFileField(
        required=True,
        comment="Absolute path to initrd on filesystem"
        )

    kernel_options = DictField()
    kernel_options_post = DictField(
        display_name=u"Kernel Options (Post Install)",
        )
    
    architecture = ChoiceField(
        default='i386',
        choices=['i386','x86_64','ia64','ppc','s390'],
        )
    breed = ChoiceField(
        default='redhat',
        choices=['redhat', 'debian'],  #XXX: Needs to be loaded from config
        comment="What is the type of distribution?",
        )
    os_version = ChoiceField(
        default='generic26',
        choices=['generic26', 'foo', 'bar'],  #XXX: Needs to be loaded from config
        display_name='OS Version',
        comment='Needed for some virtualization optimizations',
        )
    source_repos = ListField()
    depth = IntField()
    comment = StrField(
        comment="Free form text description",
        )
    tree_build_time = StrField()
    
    kickstart_metadata = DictField()
    mgmt_classes = ListField(
        display_name="Management Classes",
        comment="For external config management",
        )
    mgmt_parameters = DictField(
        inherit=True,
        default="<<inherit>>",
        display_name="Management Parameters",
        comment="Parameters which will be handed to your management application (Must be valid YAML dictionary)",
        )
    template_files = DictField(
        comment="File mappings for built-in configuration management",
        )
    red_hat_management_key = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Registration key for RHN, Satellite, or Spacewalk",
        )
    red_hat_management_server = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Address of Satellite or Spacewalk Server",
        )
    template_remote_kickstarts = BoolField()
    
    
class Image(BaseItem):
    name = StrField(required=True)
    owners = ListField()
    
    architecture = ChoiceField(
        default='i386',
        choices=['i386','x86_64','ia64','ppc','s390'],
        )
    breed = ChoiceField(
        default='redhat',
        choices=['redhat', 'debian'],  #XXX: Needs to be loaded from config
        comment="What is the type of distribution?",
        )
    comment = StrField(
        comment="Free form text description",
        )
    file = LocalFileField(
        comment="Path to local file or nfs://user@host:path",
        )
    depth = IntField()
    image_type = ChoiceField(
        default='iso',
        choices=['iso', 'direct', 'virt-image'],
        )
    network_count = IntField(
        default=1,
        display_name='Virt NICs',
        )
    
    os_version = ChoiceField(
        default='rhel4',
        choices=['rhel4', 'foo', 'bar'],  #XXX: Needs to be loaded from config
        display_name='OS Version',
        comment='ex: rhel4',
        )
    
    kickstart = LocalFileField(
        comment="Path to kickstart/answer file template",
        )
    virt_auto_boot = BoolField(
        default = 0, #XXX: Needs to be loaded from config
        comment="Auto boot this VM?",
        )
    virt_bridge = StrField(
        default="SETTINGS:default_virt_bridge", #XXX: Needs to be loaded from config
        )
    virt_path = StrField(
        inherit=True,
        default="<<inherit>>", 
        comment="Ex: /directory or VolGroup00",
        )
    virt_type = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Virtualization technology to use",
        )
    virt_cpus = IntField(
        default=1, 
        )
    virt_file_size = FloatField(
        default=1, #XXX: Needs to be loaded from config
        comment="(GB)",
        )
    virt_ram = IntField(
        display_name="Virt RAM",
        default=200, #XXX: Needs to be loaded from config
        comment="(MB)",
        )


class Profile(BaseItem):
    name = StrField(required=True)
    owners = ListField()#XXX: Needs to be loaded from config
    
    # XXX: Also, how will the group requirement deal with default being set
    #       on both Fields?
    profile = ItemField(item_type='Profile')
    distro = ItemField(
        required=True,
        inherit=True,
        default='<<inherit>>',
        item_type='Distro',
        )
    
    def render(self, inheritance_path=[]):
        # This makes inheritance acyclic... ----------------------------------
        # INCLUDE THIS WITH ALL INHERITANCE CODE -----------------------------
        if self in inheritance_path:
            return self.deflate()
        inheritance_path.append(self)
        # --------------------------------------------------------------------
        
        rendered = super(Profile, self).render(inheritance_path)
        
        if self.profile.is_set():
            parent = self.profile.get_ref().render(inheritance_path)
        else:
            parent = store.new('Profile').deflate()
        
        if self.distro.is_set():
            distro = self.distro.get_ref().render(inheritance_path)
            for field, value in parent:
                if value == "<<inherit>>":
                   parent[field] = distro[field] 
        
        for field, value in rendered.iteritems():
            if value == "<<inherit>>":
               rendered[field] = parent[field] 
        
        return rendered
    comment = StrField(
        tags=['TextField'],
        )
   
    enable_menu = BoolField(
        inherit=True,
        default="<<inherit>>", #XXX: Needs to be loaded from config
        display_name="Enable PXE Menu?",
        comment="Show this profile in PXE menu?",
        )
    
    kernel_options = DictField(
        inherit=True,
        default="<<inherit>>",
        comment="Ex: selinux=permissive",
        )
    kernel_options_post = DictField(
        inherit=True,
        default="<<inherit>>",
        display_name=u"Kernel Options (Post Install)",
        )
    
    kickstart_metadata = DictField(
        inherit=True,
        default="<<inherit>>",
        comment="Ex: dog=fang agent=86",
        )
    kickstart = LocalFileField(
        inherit=True,
        default=u"<<inherit>>",#XXX: Needs to be loaded from config
        )
    netboot_enabled = BoolField()
    comment = StrField(tags=[u"TextField"])
    depth = IntField(
        default=1,
        )
    server_override = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="See manpage or leave blank",
        )
    virt_path = StrField(
        inherit=True,
        default="<<inherit>>", 
        comment="Ex: /directory or VolGroup00",
        )
    virt_type = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Virtualization technology to use",
        )
    virt_cpus = IntField(
        inherit=True,
        default="<<inherit>>", 
        )
    virt_file_size = FloatField(
        inherit=True,
        default="<<inherit>>",#XXX: Needs to be loaded from config
        comment="(GB)",
        )
    virt_ram = IntField(
        inherit=True,
        default="<<inherit>>",#XXX: Needs to be loaded from config
        comment="(MB)",
        )
    virt_auto_boot = BoolField(
        inherit=True,
        default="<<inherit>>",
        comment="Auto boot this VM?",
        )
    virt_bridge = StrField(
        default="SETTINGS:default_virt_bridge", #XXX: Needs to be loaded from config
        inherit=True,
        )
    repos = ListField(
        inherit=True,
        default="<<inherit>>",
        comment="Repos to auto-assign to this profile",
        )
    dhcp_tag = StrField(
        display_name="DHCP Tag",
        )
    name_servers = ListField(
        default=['foo'],#XXX: Needs to be loaded from config
        )
    name_servers_search = ListField(
        default=['foo'],#XXX: Needs to be loaded from config
        display_name=u"Name Servers Search Path",
        )
    mgmt_classes = ListField(
        inherit=True,
        default="<<inherit>>",
        display_name="Management Classes",
        comment="For external config management",
        )
    mgmt_parameters = DictField(
        inherit=True,
        default="<<inherit>>",
        display_name="Management Parameters",
        comment="Parameters which will be handed to your management application (Must be valid YAML dictionary)",
        )
    template_files = DictField(
        inherit=True,
        default="<<inherit>>",
        comment="File mappings for built-in configuration management",
        )
    red_hat_management_key = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Registration key for RHN, Satellite, or Spacewalk",
        )
    red_hat_management_server = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Address of Satellite or Spacewalk Server",
        )
    template_remote_kickstarts = BoolField()


class System(BaseItem):
    _requirements = []
    
    name = StrField(required=True)
    owners = ListField()
    
    # XXX: Also, how will the group requirement deal with default being set
    #       on both Fields?
    profile = ItemField(item_type='Profile')
    image = ItemField(item_type='Image')
    _requirements.append(require_one_of(profile, image))
    
    def render(self, inheritance_path=[]):
        # This makes inheritance acyclic... ----------------------------------
        # INCLUDE THIS WITH ALL INHERITANCE CODE -----------------------------
        if self in inheritance_path:
            return self.deflate()
        inheritance_path.append(self)
        # --------------------------------------------------------------------
        
        rendered = super(Profile, self).render(inheritance_path)
        profile = self.profile.get_ref().render(inheritance_path)
        image = self.image.get_ref().render(inheritance_path)
        # Since only one of the two should be non-False.
        parent = profile or image
        for field, value in rendered:
            if value == "<<inherit>>":
               rendered[field] = parent[field] 
        return rendered

    kernel_options = DictField()
    kernel_options_post = DictField(
        display_name=u"Kernel Options (Post Install)",
        )
    
    kickstart_metadata = DictField()
    kickstart = StrField(
        inherit=True,
        default=u"<<inherit>>",
        )
    netboot_enabled = BoolField()
    comment = StrField(tags=[u"TextField"])
    depth = IntField()
    server_override = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="See manpage or leave blank",
        )
    virt_path = StrField(
        inherit=True,
        default="<<inherit>>", 
        comment="Ex: /directory or VolGroup00",
        )
    virt_type = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Virtualization technology to use",
        )
    virt_cpus = IntField(
        inherit=True,
        default="<<inherit>>", 
        )
    virt_file_size = FloatField(
        inherit=True,
        default="<<inherit>>",
        comment="(GB)",
        )
    virt_ram = IntField(
        inherit=True,
        default="<<inherit>>",
        comment="(MB)",
        )
    virt_auto_boot = BoolField(
        inherit=True,
        default="<<inherit>>",
        comment="Auto boot this VM?",
        )
    power_type = ChoiceField(
        display_name="Power Management Type",
        default="SETTINGS:power_management_default_type",
        choices=('foo', 'bar', 'baz'),#XXX: Needs to be loaded from config
        )
    power_address = StrField(
        display_name="Power Management Address",
        comment="Ex: power-device.example.org",
        )
    power_user = StrField(
        display_name="Power Username",
        )
    power_pass = StrField(
        display_name="Power Password",
        )
    power_id = StrField(
        display_name=u"Power ID",
        comment=u"Usually a plug number or blade name, if power type requires it",
        )
    hostname = StrField()
    gateway = StrField()
    name_servers = ListField()
    name_servers_search = ListField(
        display_name=u"Name Servers Search Path",
        )
    ipv6_default_device = StrField(
        display_name=u"IPv6 Default Device",
        )
    ipv6_autoconfiguration = BoolField(
        display_name=u"IPv6 Default Device",
        )
    mac_address = StrField(
        display_name=u"MAC Address",
        comment=u"(Place \"random\" in this field for a random MAC Address.)",
        )
    mtu = StrField(
        display_name=u"MTU",
        )
    bonding = ChoiceField(
        display_name="Bonding Mode",
        choices=["na","master","slave"],
        )
    bonding_master = StrField()
    bonding_opts = StrField()
    static = BoolField(
        comment="Is this interface static?",
        )
    subnet = StrField()
    dhcp_tag = StrField(
        display_name="DHCP Tag",
        )
    dns_name = StrField(
        display_name="DNS Name",
        )
    static_routes = ListField()
    virt_bridge = StrField()
    ipv6_address = StrField(
        display_name="IPv6 Address",
        )
    ipv6_secondaries = ListField(
        display_name="IPv6 Secondaries",
        )
    ipv6_mtu = StrField(
        display_name="IPv6 MTU",
        )
    ipv6_static_routes = ListField(
        display_name="IPv6 Static Routes",
        )
    ipv6_default_gateway = StrField(
        display_name="IPv6 Default Gateway",
        )
    mgmt_classes = ListField(
        display_name="Management Classes",
        comment="For external config management",
        )
    mgmt_parameters = DictField(
        inherit=True,
        default="<<inherit>>",
        display_name="Management Parameters",
        comment="Parameters which will be handed to your management application (Must be valid YAML dictionary)",
        )
    template_files = DictField(
        comment="File mappings for built-in configuration management",
        )
    red_hat_management_key = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Registration key for RHN, Satellite, or Spacewalk",
        )
    red_hat_management_server = StrField(
        inherit=True,
        default="<<inherit>>",
        comment="Address of Satellite or Spacewalk Server",
        )
    template_remote_kickstarts = BoolField()
        


class Repo(BaseItem):
    name = StrField(required=True)
    owners = ListField()
    
    architecture = ChoiceField(
        default='i386',
        choices=['i386','x86_64','ia64','ppc','s390'],
        )
    breed = ChoiceField(
        default='redhat',
        choices=['redhat', 'debian'],  #XXX: Needs to be loaded from config
        comment="What is the type of distribution?",
        )
    comment = StrField(
        tags=['TextField'],
        comment="Free form text description",
        )
    keep_updated = BoolField(
        default=True,
        comment="Update this repo on next 'cobbler reposync'?",
        )
    mirror = StrField(
        comment="Address of yum or rsync repo to mirror",
        )
    createrepo_flags = DictField(
        comment="Flags to use with createrepo",
        )
    environment = DictField(
        comment="Use these environment variables during commans (key=value, space delimited)",
        )
    mirror_locally = BoolField(
        comment="Copy files or just reference the mirror internally?",
        )
    priority = IntField(
        default=99,
        comment="Value for yum priorities plugin, if installed",
        )
    yum_options = DictField(
        comment="Options to write to yum config file",
        )
