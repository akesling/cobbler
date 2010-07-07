"""
Code for Cobbler's XMLRPC API

Copyright 2007-2009, Red Hat, Inc
Michael DeHaan <mdehaan@redhat.com>
 
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
02110-1301  USA
"""

import sys, socket, time, os, errno, re, random, stat, string
import base64
import SimpleXMLRPCServer
from SocketServer import ThreadingMixIn
import xmlrpclib
import base64
import fcntl
import traceback
import glob
try:
    import subprocess
except:
    import sub_process as subprocess
from threading import Thread

import core as cobbler_api
import utils
from cexceptions import *
import item_distro
import item_profile
import item_system
import item_repo
import item_image
import clogger
import pxegen
import utils
#from utils import * # BAD!
from utils import _

# FIXME: make configurable?
TOKEN_TIMEOUT = 60*60 # 60 minutes
EVENT_TIMEOUT = 7*24*60*60 # 1 week
CACHE_TIMEOUT = 10*60 # 10 minutes

# task codes
EVENT_RUNNING   = "running"
EVENT_COMPLETE  = "complete"
EVENT_FAILED    = "failed"
# normal events
EVENT_INFO      = "notification"

# for backwards compatibility with 1.6 and prev XMLRPC
# do not remove!
REMAP_COMPAT = {
   "ksmeta"          : "ks_meta",
   "kopts"           : "kernel_options",
   "kopts_post"      : "kernel_options_post",
   "netboot-enabled" : "netboot_enabled"
}


class CobblerThread(Thread):
    def __init__(self,event_id,remote,logatron,options):
        Thread.__init__(self)
        self.event_id        = event_id
        self.remote          = remote
        self.logger          = logatron
        if options is None:
            options = {}
        self.options         = options

    def on_done(self):
        pass

    def run(self):
        time.sleep(1)
        try:
            rc = self._run(self)
            self.remote._set_task_state(self,self.event_id,EVENT_COMPLETE)
            self.on_done()
            return rc
        except:
            utils.log_exc(self.logger)
            self.remote._set_task_state(self,self.event_id,EVENT_FAILED)
            return False  
 
# *********************************************************************
# *********************************************************************

class CobblerXMLRPCInterface:
    """
    This is the interface used for all XMLRPC methods, for instance,
    as used by koan or CobblerWeb.
   
    Most read-write operations require a token returned from "login". 
    Read operations do not.
    """

    def __init__(self,api):
        """
        Constructor.  Requires a Cobbler API handle.
        """
        self.api = api
        self.logger = self.api.logger
        self.token_cache = {}
        self.object_cache = {}
        self.timestamp = self.api.last_modified_time()
        self.events = {}
        self.shared_secret = utils.get_shared_secret()
        random.seed(time.time())
        self.translator = utils.Translator(keep=string.printable)
        
        # Construct specific variants of generic actions (new_distro from
        # new_item, etc.)
        self._build_interface()
    
    def _build_interface(self, objs=None, interface=None):
        """
        Construct specific variants (new_distro, modify_distro, etc.) of 
        generic actions (new_item, modify_item, etc.).  Curry the generic
        method to create the specific method and monkey-patch it to self.
        
        The goal is to reduce clutter in CobblerXMLRPCInterface to make it
        easier to maintain.  And potentially down the road, have all of this
        dynamically generated from the object store itself....
        """
        default_objs = objs or [
            # ( Object type, (args, kwargs) )
            ( 'distro',      ((), {}) ),
            ( 'profile',     ((), {}) ),
            ( 'system',      ((), {}) ),
            ( 'repo',        ((), {}) ),
            ( 'image',       ((), {}) ),
        ]
        
        interface = interface or {
            # Method            : ( object types to operate on, (args, kwargs) )
            'copy_item'         : ( default_objs, ((), {}) ),
            'find_items'        : ( default_objs, ((), {}) ),
            'get_item'          : ( default_objs, ((), {}) ),
            'get_items'         : ( default_objs, ((), {}) ),
            'get_item_handle'   : ( default_objs, ((), {}) ),
            'modify_item'       : ( default_objs, ((), {}) ),
            'new_item'          : ( default_objs[:] + [('subprofile', ((), {'is_subobject': True}))],
                                  ((), {}) ),
            'remove_item'       : ( default_objs, ((), {}) ),
            'rename_item'       : ( default_objs, ((), {}) ),
            'save_item'         : ( default_objs, ((), {}) ),
        }
        
        for meth, chunk in interface.items():
            types, args   = chunk
            args, kwargs  = args
            
            base_method   = getattr(self, meth)
            
            for obj_info in types:
                obj_type, obj_args   = obj_info
                obj_args, obj_kwargs = obj_args
                
                obj_args = list(obj_args)
                obj_args.extend(args)
                obj_kwargs.update(kwargs)
                
                new_method_name = meth.replace("item", obj_type)
                new_method = utils.curry(base_method, obj_type, *obj_args, **obj_kwargs)
                
                setattr(self, new_method_name, new_method)

###############################################################################
## Object Access/Manipulation Methods #########################################
    
    
    def copy_item(self,what,object_id,newname,token=None):
        """
        Creates a new object that matches an existing object, as specified by an id.
        """
        self._log("copy_item(%s)" % what,object_id=object_id,token=token)
        self.check_access(token,"copy_%s" % what)
        obj = self.__get_object(object_id)
        return self.api.copy_item(what,obj,newname)
    
    
    def find_items(self, what, criteria=None,sort_field=None,expand=True, *args, **kwargs):
        """
        Returns a list of hashes.
        Works like get_items but also accepts criteria as a hash to search on.
        Example:  { "name" : "*.example.org" }
        Wildcards work as described by 'pydoc fnmatch'.
        """
        self._log("find_items(%s); criteria(%s); sort(%s)" % (what,criteria,sort_field))
        items = self.api.find_items(what,criteria=criteria)
        items = self.__sort(items,sort_field)
        if not expand:     
            items = [x.name for x in items]
        else:
            items = [x.to_datastruct() for x in items]
        return self.xmlrpc_hacks(items)
    
    
    def get_item(self, what, name, flatten=False):
        """
        Returns a hash describing a given object.
        what -- "distro", "profile", "system", "image", "repo", etc
        name -- the object name to retrieve
        flatten -- reduce hashes to string representations (True/False)
        """
        self._log("get_item(%s,%s)"%(what,name))
        item=self.api.get_item(what,name)
        if item is not None:
            item=item.to_datastruct()
        if flatten:
            item = utils.flatten(item)
        return self.xmlrpc_hacks(item)
    
    
    def get_items(self, what, *args, **kwargs):
        """
        Returns a list of hashes.  
        what is the name of a cobbler object type, as described for get_item.
        Individual list elements are the same for get_item.
        """
        # FIXME: is the xmlrpc_hacks method still required ?
        item = [x.to_datastruct() for x in self.api.get_items(what)]
        return self.xmlrpc_hacks(item)
    
    
    def get_item_handle(self,what,name,token=None):
        """
        Given the name of an object (or other search parameters), return a
        reference (object id) that can be used with modify_* functions or save_* functions
        to manipulate that object.
        """
        found = self.api.get_item(what,name)
        if found is None:
            raise CX("internal error, unknown %s name %s" % (what,name))
        return "%s::%s" % (what,found.name)
    
    
    def new_item(self,what,token,is_subobject=False):
        """
        Creates a new (unconfigured) object, returning an object
        handle that can be used with modify_* methods and then finally
        save_* methods.  The handle only exists in memory until saved.
        "what" specifies the type of object: 
            distro, profile, system, repo, or image
        """      
        self._log("new_item(%s)"%what,token=token)
        self.check_access(token,"new_%s"%what)
        if what == "distro":
            d = item_distro.Distro(self.api._config,is_subobject=is_subobject)
        elif what == "profile":
            d = item_profile.Profile(self.api._config,is_subobject=is_subobject)
        elif what == "system":
            d = item_system.System(self.api._config,is_subobject=is_subobject)
        elif what == "repo":
            d = item_repo.Repo(self.api._config,is_subobject=is_subobject)
        elif what == "image":
            d = item_image.Image(self.api._config,is_subobject=is_subobject)
        else:
            raise CX("internal error, collection name is %s" % what)
        key = "___NEW___%s::%s" % (what,self.__get_random(25))
        self.object_cache[key] = (time.time(), d) 
        return key
    
    
    def modify_item(self,what,object_id,attribute,arg,token):
        """
        Adjusts the value of a given field, specified by 'what' on a given object id.
        Allows modification of certain attributes on newly created or
        existing distro object handle.
        """
        self._log("modify_item(%s)" % what,object_id=object_id,attribute=attribute,token=token)
        obj = self.__get_object(object_id)
        self.check_access(token, "modify_%s"%what, obj, attribute)
        # support 1.6 field name exceptions for backwards compat
        attribute = REMAP_COMPAT.get(attribute,attribute)
        method = obj.remote_methods().get(attribute, None)
        if method == None:
            # it's ok, the CLI will send over lots of junk we can't process
            # (like newname or in-place) so just go with it.
            return False
            # raise CX("object has no method: %s" % attribute)
        return method(arg)
    
    
    def remove_item(self,what,name,token,recursive=True):
        """
        Deletes an item from a collection.  
        Note that this requires the name of the distro, not an item handle.
        """
        self._log("remove_item (%s, recursive=%s)" % (what,recursive),name=name,token=token)
        self.check_access(token, "remove_item", name)
        return self.api.remove_item(what,name,delete=True,with_triggers=True,recursive=recursive)
    
    
    def rename_item(self,what,object_id,newname,token=None):
        """
        Renames an object specified by object_id to a new name.
        """
        self._log("rename_item(%s)" % what,object_id=object_id,token=token)
        obj = self.__get_object(object_id)
        return self.api.rename_item(what,obj,newname)
     
     
    def save_item(self,what,object_id,token,editmode="bypass"):
        """
        Saves a newly created or modified object to disk.
        Calling save is required for any changes to persist.
        """
        self._log("save_item(%s)" % what,object_id=object_id,token=token)
        obj = self.__get_object(object_id)
        self.check_access(token,"save_%s"%what,obj)
        if editmode == "new":
            rc = self.api.add_item(what,obj,check_for_duplicate_names=True)
        else:
            rc = self.api.add_item(what,obj)
        return rc
    
    
    def get_item_names(self, what):
        """
        Returns a list of object names (keys) for the given object type.
        This is just like get_items, but transmits less data.
        """
        return [x.name for x in self.api.get_items(what)]
    
    
    def find_items_paged(self, what, criteria=None, sort_field=None, page=None, items_per_page=None, token=None):
        """
        Returns a list of hashes as with find_items but additionally supports
        returning just a portion of the total list, for instance in supporting
        a web app that wants to show a limited amount of items per page.
        """
        # FIXME: make token required for all logging calls
        self._log("find_items_paged(%s); criteria(%s); sort(%s)" % (what,criteria,sort_field), token=token)
        items = self.api.find_items(what,criteria=criteria)
        items = self.__sort(items,sort_field)
        (items,pageinfo) = self.__paginate(items,page,items_per_page)
        items = [x.to_datastruct() for x in items]
        return self.xmlrpc_hacks({
            'items'    : items,
            'pageinfo' : pageinfo
        })
    
    
    def has_item(self,what,name,token=None):
        """
        Returns True if a given collection has an item with a given name,
        otherwise returns False.
        """
        self._log("has_item(%s)"%what,token=token,name=name)
        found = self.api.get_item(what,name)
        if found is None:
            return False
        else:
            return True
        
    
    def xapi_object_edit(self,object_type,object_name,edit_type,attributes,token):
        """
        Extended API:  New style object manipulations, 2.0 and later
        Prefered over using new_, modify_, save_ directly.
        Though we must preserve the old ways for backwards compatibility these 
        cause much less XMLRPC traffic.
        
        edit_type - One of 'add', 'rename', 'copy', 'remove'
        
        Ex: xapi_object_edit("distro","el5","add",{"kernel":"/tmp/foo","initrd":"/tmp/foo"},token)
        """
        self.check_access(token,"xedit_%s" % object_type, token)
        
        if edit_type == "add" and not attributes.has_key("clobber"):
            handle = 0
            try:
                handle = self.get_item_handle(object_type, object_name)
            except:
                utils.log_exc(self.logger)
                pass
            if handle != 0:
                raise CX("it seems unwise to overwrite this object, try 'edit'")
        
        if edit_type == "add":
            is_subobject = object_type == "profile" and "parent" in attributes
            handle = self.new_item(object_type, token, is_subobject=is_subobject)
        else:
            handle = self.get_item_handle(object_type, object_name)
        
        if edit_type == "rename":
            self.rename_item(object_type, handle, attributes["newname"], token)
            handle = self.get_item_handle(object_type, attributes["newname"], token)
        if edit_type == "copy":
            self.copy_item(object_type, handle, attributes["newname"], token)
            handle = self.get_item_handle(object_type, attributes["newname"], token)
        if edit_type in [ "copy", "rename" ]:
            del attributes["name"] 
            del attributes["newname"] 

        if edit_type != "remove":
            # FIXME: this doesn't know about interfaces yet!
            # if object type is system and fields add to hash and then
            # modify when done, rather than now.
            imods = {}
            # FIXME: needs to know about how to delete interfaces too!
            for (k,v) in attributes.iteritems():
                if not object_type == "system" or not self.__is_interface_field(k):
                    
                    # in place modifications allow for adding a key/value pair while keeping other k/v
                    # pairs intact.
                    if k in [ "ks_meta", "kernel_options", "kernel_options_post", "template_files", "fetchable_files"] and attributes.has_key("in_place") and attributes["in_place"]:
                        details = self.get_item(object_type,object_name)
                        v2 = details[k]
                        (ok, input) = utils.input_string_or_hash(v)
                        for (a,b) in input.iteritems():
                           v2[a] = b
                        v = v2
                    
                    self.modify_item(object_type,handle,k,v,token)
                
                else:
                    modkey = "%s-%s" % (k, attributes.get("interface","eth0"))
                    imods[modkey] = v
            if object_type == "system" and not attributes.has_key("delete_interface"):
                self.modify_system(handle, 'modify_interface', imods, token)
            elif object_type == "system":
                self.modify_system(handle, 'delete_interface', attributes.get("interface", "eth0"), token)
        
        
        else:
           self.remove_item(object_type, object_name, token, recursive=True)
           return True
        
        # FIXME: use the bypass flag or not?
        return self.save_item(object_type, handle, token)
    
    
    def get_repo_config_for_profile(self,profile_name,**rest):
        """
        Return the yum configuration a given profile should use to obtain
        all of it's cobbler associated repos.
        """
        obj = self.api.find_profile(profile_name)
        if obj is None:
           return "# object not found: %s" % profile_name
        return self.api.get_repo_config_for_profile(obj)
    
    
    def get_repo_config_for_system(self,system_name,**rest):
        """
        Return the yum configuration a given profile should use to obtain
        all of it's cobbler associated repos.
        """
        obj = self.api.find_system(system_name)
        if obj is None:
           return "# object not found: %s" % system_name
        return self.api.get_repo_config_for_system(obj)
    
    
    def get_template_file_for_profile(self,profile_name,path,**rest):
        """
        Return the templated file requested for this profile
        """
        obj = self.api.find_profile(profile_name)
        if obj is None:
           return "# object not found: %s" % profile_name
        return self.api.get_template_file_for_profile(obj,path)
    
    
    def get_template_file_for_system(self,system_name,path,**rest):
        """
        Return the templated file requested for this system
        """
        obj = self.api.find_system(system_name)
        if obj is None:
           return "# object not found: %s" % system_name
        return self.api.get_template_file_for_system(obj,path)
    
    
    def register_new_system(self,info,token=None,**rest):
        """
        If register_new_installs is enabled in settings, this allows
        /usr/bin/cobbler-register (part of the koan package) to add 
        new system records remotely if they don't already exist.
        There is a cobbler_register snippet that helps with doing
        this automatically for new installs but it can also be used
        for existing installs.  See "AutoRegistration" on the Wiki.
        """
   
        enabled = self.api.settings().register_new_installs
        if not str(enabled) in [ "1", "y", "yes", "true" ]:
            raise CX("registration is disabled in cobbler settings")
         
        # validate input
        name     = info.get("name","")
        profile  = info.get("profile","")
        hostname = info.get("hostname","")
        interfaces = info.get("interfaces",{})
        ilen       = len(interfaces.keys())
        
        if name == "":
            raise CX("no system name submitted")
        if profile == "":
            raise CX("profile not submitted")
        if ilen == 0:
            raise CX("no interfaces submitted")
        if ilen >= 64:
            raise CX("too many interfaces submitted")
        
        # validate things first
        name = info.get("name","")
        inames = interfaces.keys()
        if self.api.find_system(name=name):
            raise CX("system name conflicts")
        if hostname != "" and self.api.find_system(hostname=hostname):
            raise CX("hostname conflicts")
        
        for iname in inames:
            mac      = info["interfaces"][iname].get("mac_address","")
            ip       = info["interfaces"][iname].get("ip_address","")
            if ip.find("/") != -1:
                raise CX("no CIDR ips are allowed")
            if mac == "":
                raise CX("missing MAC address for interface %s" % iname) 
            if mac != "":
                system = self.api.find_system(mac_address=mac)
                if system is not None: 
                   raise CX("mac conflict: %s" % mac)
            if ip != "":
                system = self.api.find_system(ip_address=ip)
                if system is not None:
                   raise CX("ip conflict: %s"%  ip)
        
        # looks like we can go ahead and create a system now
        obj = self.api.new_system()
        obj.set_profile(profile)
        obj.set_name(name)
        if hostname != "":
           obj.set_hostname(hostname)
        obj.set_netboot_enabled(False)
        for iname in inames:
            if info["interfaces"][iname].get("bridge","") == 1:
               # don't add bridges
               continue
            #if info["interfaces"][iname].get("module","") == "":
            #   # don't attempt to add wireless interfaces
            #   continue
            mac      = info["interfaces"][iname].get("mac_address","")
            ip       = info["interfaces"][iname].get("ip_address","")
            netmask  = info["interfaces"][iname].get("netmask","")
            if mac == "?":
                # see koan/utils.py for explanation of network info discovery
                continue;
            obj.set_mac_address(mac, iname)
            if hostname != "":
                obj.set_dns_name(hostname, iname)
            if ip != "" and ip != "?":
                obj.set_ip_address(ip, iname)
            if netmask != "" and netmask != "?":
                obj.set_subnet(netmask, iname)
        self.api.add_system(obj)
        return 0
     
    
    def disable_netboot(self,name,token=None,**rest):
        """
        This is a feature used by the pxe_just_once support, see manpage.
        Sets system named "name" to no-longer PXE.  Disabled by default as
        this requires public API access and is technically a read-write operation.
        """
        self._log("disable_netboot",token=token,name=name)
        # used by nopxe.cgi
        if not self.api.settings().pxe_just_once:
            # feature disabled!
            return False
        systems = self.api.systems()
        obj = systems.find(name=name)
        if obj == None:
            # system not found!
            return False
        obj.set_netboot_enabled(0)
        # disabling triggers and sync to make this extremely fast.
        systems.add(obj,save=True,with_triggers=False,with_sync=False,quick_pxe_update=True)
        return True
    
    
###############################################################################
## Background Task Methods ####################################################
    
    
    def background_buildiso(self, options, token):
        """
        Generates an ISO in /var/www/cobbler/pub that can be used to install
        profiles without using PXE.
        """
        def runner(self):
            return self.remote.api.build_iso(
                self.options.get("iso","/var/www/cobbler/pub/generated.iso"),
                self.options.get("profiles",None),
                self.options.get("systems",None),
                self.options.get("tempdir",None),
                self.options.get("distro",None),
                self.options.get("standalone",False),
                self.options.get("source",None),
                self.options.get("exclude_dns",False),
                self.logger
            )
        def on_done(self):
            if self.options.get("iso","") == "/var/www/cobbler/pub/generated.iso":
                msg = "ISO now available for <A HREF=\"/cobbler/pub/generated.iso\">download</A>"
                self.remote._new_event(msg)
        return self.__start_task(runner, token, "buildiso", "Build Iso", options, on_done)
    
    
    def background_aclsetup(self, options, token):
        def runner(self):
            return self.remote.api.acl_config(
                self.options.get("adduser",None),
                self.options.get("addgroup",None),
                self.options.get("removeuser",None),
                self.options.get("removegroup",None),
                self.logger
            )
        return self.__start_task(runner, token, "aclsetup", "(CLI) ACL Configuration", options)
    
    
    def background_dlcontent(self, options, token):
        """
        Download bootloaders and other support files.
        """
        def runner(self):
            return self.remote.api.dlcontent(self.options.get("force",False), self.logger)
        return self.__start_task(runner, token, "get_loaders", "Download Bootloader Content", options)
    
    
    def background_sync(self, options, token):
        def runner(self):
            return self.remote.api.sync(self.options.get("verbose",False),logger=self.logger)
        return self.__start_task(runner, token, "sync", "Sync", options) 
    
    
    def background_hardlink(self, options, token):
        def runner(self):
            return self.remote.api.hardlink(logger=self.logger)
        return self.__start_task(runner, token, "hardlink", "Hardlink", options)
    
    
    def background_validateks(self, options, token):
        def runner(self):
            return self.remote.api.validateks(logger=self.logger)
        return self.__start_task(runner, token, "validateks", "Kickstart Validation", options)
    
    
    def background_replicate(self, options, token):
        def runner(self):
            # FIXME: defaults from settings here should come from views, fix in views.py
            return self.remote.api.replicate(
                self.options.get("master", None),
                self.options.get("distro_patterns", ""),
                self.options.get("profile_patterns", ""),
                self.options.get("system_patterns", ""),
                self.options.get("repo_patterns", ""),
                self.options.get("image_patterns", ""),
                self.options.get("prune", False),
                self.options.get("omit_data", False),
                self.logger
            )
        return self.__start_task(runner, token, "replicate", "Replicate", options)
    
    
    def background_import(self, options, token):
        def runner(self):
            return self.remote.api.import_tree(
                self.options.get("path", None),
                self.options.get("name", None),
                self.options.get("available_as", None),
                self.options.get("kickstart_file", None),
                self.options.get("rsync_flags",None),
                self.options.get("arch",None),
                self.options.get("breed", None),
                self.options.get("os_version", None),
                self.logger
            ) 
        return self.__start_task(runner, token, "import", "Media import", options)
                     
    
    def background_reposync(self, options, token):
        def runner(self):
            # NOTE: WebUI passes in repos here, CLI passes only:
            repos = options.get("repos", [])
            only = options.get("only", None)
            if only is not None:
                repos = [ only ] 

            if len(repos) > 0:
                for name in repos:
                    self.remote.api.reposync(tries=self.options.get("tries",
                        3), name=name, nofail=True, logger=self.logger)
            else:
                self.remote.api.reposync(tries=self.options.get("tries",3),
                        name=None, nofail=False, logger=self.logger)
            return True
        return self.__start_task(runner, token, "reposync", "Reposync", options)
    
    
    def background_power_system(self, options, token):
        def runner(self):
            for x in self.options.get("systems",[]):
                object_id = self.remote.get_system_handle(x,token)
                self.remote.power_system(object_id,self.options.get("power",""),token,logger=self.logger)
            return True
        self.check_access(token, "power")
        return self.__start_task(runner, token, "power", "Power management (%s)" % options.get("power",""), options)
    
    
###############################################################################
## Other Assorted Methods #####################################################
    
    def run_install_triggers(self,mode,objtype,name,ip,token=None,**rest):
        
        """
        This is a feature used to run the pre/post install triggers.
        See CobblerTriggers on Wiki for details
        """
        
        self._log("run_install_triggers",token=token)
        
        if mode != "pre" and mode != "post":
            return False
        if objtype != "system" and objtype !="profile":
            return False
        
        # the trigger script is called with name,mac, and ip as arguments 1,2, and 3
        # we do not do API lookups here because they are rather expensive at install
        # time if reinstalling all of a cluster all at once.
        # we can do that at "cobbler check" time.
        
        utils.run_triggers(self.api, None, "/var/lib/cobbler/triggers/install/%s/*" % mode, additional=[objtype,name,ip],logger=self.logger)
        
        
        return True
    
    
    def version(self,token=None,**rest):
        """
        Return the cobbler version for compatibility testing with remote applications.
        See api.py for documentation.
        """
        self._log("version",token=token)
        return self.api.version()
    
    
    def extended_version(self,token=None,**rest):
        """
        Returns the full dictionary of version information.  See api.py for documentation.
        """
        self._log("version",token=token)
        return self.api.version(extended=True)
    
    
    def get_distros_since(self,mtime):
        """
        Return all of the distro objects that have been modified
        after mtime.
        """
        data = self.api.get_distros_since(mtime, collapse=True)
        return self.xmlrpc_hacks(data)

    
    def get_profiles_since(self,mtime):
        """
        See documentation for get_distros_since
        """
        data = self.api.get_profiles_since(mtime, collapse=True)
        return self.xmlrpc_hacks(data)
    
    
    def get_systems_since(self,mtime):
        """
        See documentation for get_distros_since
        """
        data = self.api.get_systems_since(mtime, collapse=True)
        return self.xmlrpc_hacks(data)
    
    
    def get_repos_since(self,mtime):
        """
        See documentation for get_distros_since
        """
        data = self.api.get_repos_since(mtime, collapse=True)
        return self.xmlrpc_hacks(data)
    
    
    def get_images_since(self,mtime):
        """
        See documentation for get_distros_since
        """
        data = self.api.get_images_since(mtime, collapse=True)
        return self.xmlrpc_hacks(data)
    
    
    def get_repos_compatible_with_profile(self,profile=None,token=None,**rest):
        """
        Get repos that can be used with a given profile name
        """
        self._log("get_repos_compatible_with_profile",token=token)
        profile = self.api.find_profile(profile)
        if profile is None:
            return -1
        results = []
        distro = profile.get_conceptual_parent()
        repos = self.get_repos()
        for r in repos:
           # there be dragons!
           # accept all repos that are src/noarch
           # but otherwise filter what repos are compatible
           # with the profile based on the arch of the distro.
           if r["arch"] is None or r["arch"] in [ "", "noarch", "src" ]:
              results.append(r)
           else:
              # some backwards compatibility fuzz
              # repo.arch is mostly a text field
              # distro.arch is i386/x86_64/ia64/s390x/etc
              if r["arch"] in [ "i386", "x86", "i686" ]:
                  if distro.arch in [ "i386", "x86" ]:
                      results.append(r)
              elif r["arch"] in [ "x86_64" ]:
                  if distro.arch in [ "x86_64" ]:
                      results.append(r)
              elif r["arch"].startswith("s390"):
                  if distro.arch in [ "s390x" ]:
                      results.append(r)
              else:
                  if distro.arch == r["arch"]:
                      results.append(r)
        return results    
              
    
    # this is used by the puppet external nodes feature
    def find_system_by_dns_name(self,dns_name):
        # FIXME: implement using api.py's find API
        # and expose generic finds for other methods
        # WARNING: this function is /not/ expected to stay in cobbler long term
        systems = self.get_systems()
        for x in systems:
           for y in x["interfaces"]:
              if x["interfaces"][y]["dns_name"] == dns_name:
                  name = x["name"]
                  return self.get_system_for_koan(name)
        return {}
    
    
    def get_distro_as_rendered(self,name,token=None,**rest):
        """
        Return the distribution as passed through cobbler's
        inheritance/graph engine.  Shows what would be installed, not
        the input data.
        """
        return self.get_distro_for_koan(self,name)
    
    
    def get_distro_for_koan(self,name,token=None,**rest):
        """
        Same as get_distro_as_rendered.
        """
        self._log("get_distro_as_rendered",name=name,token=token)
        obj = self.api.find_distro(name=name)
        if obj is not None:
            return self.xmlrpc_hacks(utils.blender(self.api, True, obj))
        return self.xmlrpc_hacks({})

    
    def get_profile_as_rendered(self,name,token=None,**rest):
        """
        Return the profile as passed through cobbler's
        inheritance/graph engine.  Shows what would be installed, not
        the input data.
        """
        return self.get_profile_for_koan(name,token)
    
    
    def get_profile_for_koan(self,name,token=None,**rest):
        """
        Same as get_profile_as_rendered
        """
        self._log("get_profile_as_rendered", name=name, token=token)
        obj = self.api.find_profile(name=name)
        if obj is not None:
            return self.xmlrpc_hacks(utils.blender(self.api, True, obj))
        return self.xmlrpc_hacks({})
    
    
    def get_system_as_rendered(self,name,token=None,**rest):
        """
        Return the system as passed through cobbler's
        inheritance/graph engine.  Shows what would be installed, not
        the input data.
        """
        return self.get_system_for_koan(self,name)
    
    
    def get_system_for_koan(self,name,token=None,**rest):
        """
        Same as get_system_as_rendered.
        """
        self._log("get_system_as_rendered",name=name,token=token)
        obj = self.api.find_system(name=name)
        if obj is not None:
            hash = utils.blender(self.api,True,obj)
            # Generate a pxelinux.cfg?
            image_based = False
            profile = obj.get_conceptual_parent()
            distro  = profile.get_conceptual_parent()
            arch = distro.arch
            if distro is None and profile.COLLECTION_TYPE == "profile":
                image_based = True
                arch = profile.arch

            if obj.is_management_supported():
                if not image_based:
                    hash["pxelinux.cfg"] = self.pxegen.write_pxe_file(
                        None, obj, profile, distro, arch)
                else:
                    hash["pxelinux.cfg"] = self.pxegen.write_pxe_file(
                        None, obj,None,None,arch,image=profile)

            return self.xmlrpc_hacks(hash)
        return self.xmlrpc_hacks({})
    
    
    def get_repo_as_rendered(self,name,token=None,**rest):
        """
        Return the repo as passed through cobbler's
        inheritance/graph engine.  Shows what would be installed, not
        the input data.
        """
        return self.get_repo_for_koan(self,name)
    
    
    def get_repo_for_koan(self,name,token=None,**rest):
        """
        Same as get_repo_as_rendered.
        """
        self._log("get_repo_as_rendered",name=name,token=token)
        obj = self.api.find_repo(name=name)
        if obj is not None:
            return self.xmlrpc_hacks(utils.blender(self.api, True, obj))
        return self.xmlrpc_hacks({})
    
    
    def get_image_as_rendered(self,name,token=None,**rest):
        """
        Return the image as passed through cobbler's
        inheritance/graph engine.  Shows what would be installed, not
        the input data.
        """
        return self.get_image_for_koan(self,name)
    
    
    def get_image_for_koan(self,name,token=None,**rest):
        """
        Same as get_image_as_rendered.
        """
        self._log("get_image_as_rendered",name=name,token=token)
        obj = self.api.find_image(name=name)
        if obj is not None:
            return self.xmlrpc_hacks(utils.blender(self.api, True, obj))
        return self.xmlrpc_hacks({})
    
    
    def get_random_mac(self,virt_type="xenpv",token=None,**rest):
        """
        Wrapper for utils.get_random_mac
        Used in the webui
        """
        self._log("get_random_mac",token=None)
        return utils.get_random_mac(self.api,virt_type)
    
    
    def xmlrpc_hacks(self,data):
        """
        Convert None in XMLRPC to just '~' to make extra sure a client
        that can't allow_none can deal with this.  ALSO: a weird hack ensuring
        that when dicts with integer keys (or other types) are transmitted
        with string keys.
        """
        return utils.strip_none(data)
    
    
    def get_status(self,mode="normal",token=None,**rest):
        """
        Returns the same information as `cobbler status`
        While a read-only operation, this requires a token because it's potentially a fair amount of I/O
        """
        self.check_access(token,"sync")
        return self.api.status(mode=mode)
    
    
    def is_kickstart_in_use(self,ks,token=None,**rest):
        self._log("is_kickstart_in_use",token=token)
        for x in self.api.profiles():
           if x.kickstart is not None and x.kickstart == ks:
               return True
        for x in self.api.systems():
           if x.kickstart is not None and x.kickstart == ks:
               return True
        return False
    
    
    def generate_kickstart(self,profile=None,system=None,REMOTE_ADDR=None,REMOTE_MAC=None,**rest):
        self._log("generate_kickstart")
        return self.api.generate_kickstart(profile,system)
    
    
    def get_blended_data(self,profile=None,system=None):
        if profile is not None and profile != "":
            obj = self.api.find_profile(profile)
            if obj is None:
                raise CX("profile not found: %s" % profile)
        elif system is not None and system != "":
            obj = self.api.find_system(system)
            if obj is None:
                raise CX("system not found: %s" % system)
        else:
            raise CX("internal error, no system or profile specified")
        return self.xmlrpc_hacks(utils.blender(self.api, True, obj))
    
    
    def get_settings(self,token=None,**rest):
        """
        Return the contents of /etc/cobbler/settings, which is a hash.
        """
        self._log("get_settings",token=token)
        results = self.api.settings().to_datastruct()
        self._log("my settings are: %s" % results, debug=True)
        return self.xmlrpc_hacks(results)
    
    
    def upload_log_data(self, sys_name, file, size, offset, data, token=None,**rest):
        
        """
        This is a logger function used by the "anamon" logging system to
        upload all sorts of auxilliary data from Anaconda.
        As it's a bit of a potential log-flooder, it's off by default
        and needs to be enabled in /etc/cobbler/settings.
        """
        
        self._log("upload_log_data (file: '%s', size: %s, offset: %s)" % (file, size, offset), token=token, name=sys_name)
        
        # Check if enabled in self.api.settings()
        if not self.api.settings().anamon_enabled:
            # feature disabled!
            return False
        
        # Find matching system record
        systems = self.api.systems()
        obj = systems.find(name=sys_name)
        if obj == None:
            # system not found!
            self._log("upload_log_data - system '%s' not found" % sys_name, token=token, name=sys_name)
            return False
        
        return self.__upload_file(sys_name, file, size, offset, data)
    
    
    def check(self, token):
        """
        Returns a list of all the messages/warnings that are things
        that admin may want to correct about the configuration of 
        the cobbler server.  This has nothing to do with "check_access"
        which is an auth/authz function in the XMLRPC API.
        """
        self.check_access(token, "check")
        return self.api.check(logger=self.logger)
    
    
    def get_events(self, for_user=""):
        """
        Returns a hash(key=event id) = [ statetime, name, state, [read_by_who] ]
        If for_user is set to a string, it will only return events the user
        has not seen yet.  If left unset, it will return /all/ events.
        """
        
        # return only the events the user has not seen
        self.events_filtered = {}
        for (k,x) in self.events.iteritems():
           if for_user in x[3]:
              pass
           else:
              self.events_filtered[k] = x
        
        # mark as read so user will not get events again
        if for_user is not None and for_user != "":
           for (k,x) in self.events.iteritems():
               if for_user in x[3]:
                  pass
               else:
                  self.events[k][3].append(for_user)
        
        return self.events_filtered
    
    
    def get_event_log(self,event_id):
        """
        Returns the contents of a task log.
        Events that are not task-based do not have logs.
        """
        event_id = str(event_id).replace("..","").replace("/","")
        path = "/var/log/cobbler/tasks/%s.log" % event_id
        self._log("getting log for %s" % event_id)
        if os.path.exists(path):
           fh = open(path, "r")
           data = str(fh.read())
           data = self.translator(data)
           fh.close()
           return data
        else:
           return "?"
    
    
    def get_task_status(self, event_id):
        event_id = str(event_id)
        if self.events.has_key(event_id):
            return self.events[event_id]
        else:
            raise CX("no event with that id")
    
    
    def last_modified_time(self, token=None):
        """
        Return the time of the last modification to any object.
        Used to verify from a calling application that no cobbler
        objects have changed since last check.
        """
        return self.api.last_modified_time()
    
    
    def update(self, token=None):
        """
        Deprecated method.  Now does nothing.
        """
        return True
    
    
    def ping(self):
        """
        Deprecated method.  Now does nothing.
        """
        return True
    
    
    def get_user_from_token(self,token):
        """
        Given a token returned from login, return the username
        that logged in with it.
        """
        if not self.token_cache.has_key(token):
            raise CX("invalid token: %s" % token)
        else:
            return self.token_cache[token][1]
    
    
    def check_access_no_fail(self,token,resource,arg1=None,arg2=None):
        """
        This is called by the WUI to decide whether an element
        is editable or not. It differs form check_access in that
        it is supposed to /not/ log the access checks (TBA) and does
        not raise exceptions.
        """
        
        need_remap = False
        for x in [ "distro", "profile", "system", "repo", "image" ]:
           if arg1 is not None and resource.find(x) != -1:
              need_remap = True
              break
        
        if need_remap:
           # we're called with an object name, but need an object
           arg1 = self.__name_to_object(resource,arg1)
        
        try:
           self.check_access(token,resource,arg1,arg2)
           return True 
        except:
           utils.log_exc(self.logger)
           return False 
    
    
    def check_access(self,token,resource,arg1=None,arg2=None):
        validated = self.__validate_token(token)
        user = self.get_user_from_token(token)
        if user == "<DIRECT>":
            self._log("CLI Authorized", debug=True)
            return True
        rc = self.api.authorize(user,resource,arg1,arg2)
        self._log("%s authorization result: %s" % (user,rc),debug=True)
        if not rc:
            raise CX("authorization failure for user %s" % user) 
        return rc
    
    
    def login(self,login_user,login_password):
        """
        Takes a username and password, validates it, and if successful
        returns a random login token which must be used on subsequent
        method calls.  The token will time out after a set interval if not
        used.  Re-logging in permitted.
        """
       
        # if shared secret access is requested, don't bother hitting the auth
        # plugin
        if login_user == "":
            if login_password == self.shared_secret:
                return self.__make_token("<DIRECT>")
            else:
                utils.die(self.logger, "login failed")
        
        # this should not log to disk OR make events as we're going to
        # call it like crazy in CobblerWeb.  Just failed attempts.
        if self.__validate_user(login_user,login_password):
            token = self.__make_token(login_user)
            return token
        else:
            utils.die(self.logger, "login failed (%s)" % login_user)
    
    
    def logout(self,token):
        """
        Retires a token ahead of the timeout.
        """
        self._log("logout", token=token)
        if self.token_cache.has_key(token):
            del self.token_cache[token]
            return True
        return False    
    
    
    def token_check(self,token):
        """
        This is a demo function that does not return anything useful.
        """
        self.__validate_token(token)
        return True
    
    
    def sync(self,token):
        """
        Run sync code, which should complete before XMLRPC timeout.  We can't
        do reposync this way.  Would be nice to send output over AJAX/other
        later.
        """
        # FIXME: performance
        self._log("sync",token=token)
        self.check_access(token,"sync")
        return self.api.sync()
    
    
    def read_or_write_kickstart_template(self,kickstart_file,is_read,new_data,token):
        """
        Allows the web app to be used as a kickstart file editor.  For security
        reasons we will only allow kickstart files to be edited if they reside in
        /var/lib/cobbler/kickstarts/ or /etc/cobbler.  This limits the damage
        doable by Evil who has a cobbler password but not a system password.
        Also if living in /etc/cobbler the file must be a kickstart file.
        """
        
        if is_read:
           what = "read_kickstart_template"
        else:
           what = "write_kickstart_template"
        
        self._log(what,name=kickstart_file,token=token)
        self.check_access(token,what,kickstart_file,is_read)
        
        if kickstart_file.find("..") != -1 or not kickstart_file.startswith("/"):
            utils.die(self.logger,"tainted file location")
        
        if not kickstart_file.startswith("/etc/cobbler/") and not kickstart_file.startswith("/var/lib/cobbler/kickstarts"):
            utils.die(self.logger, "unable to view or edit kickstart in this location")
        
        if kickstart_file.startswith("/etc/cobbler/"):
           if not kickstart_file.endswith(".ks") and not kickstart_file.endswith(".cfg"):
              # take care to not allow config files to be altered.
              utils.die(self.logger, "this does not seem to be a kickstart file")
           if not is_read and not os.path.exists(kickstart_file):
              utils.die(self.logger, "new files must go in /var/lib/cobbler/kickstarts")
        
        if is_read:
            fileh = open(kickstart_file,"r")
            data = fileh.read()
            fileh.close()
            return data
        else:
            if new_data == -1:
                # delete requested
                if not self.is_kickstart_in_use(kickstart_file,token):
                    os.remove(kickstart_file)
                else:
                    utils.die(self.logger, "attempt to delete in-use file")
            else:
                fileh = open(kickstart_file,"w+")
                fileh.write(new_data)
                fileh.close()
            return True
    
    
    def read_or_write_snippet(self,snippet_file,is_read,new_data,token):
        """
        Allows the WebUI to be used as a snippet file editor.  For security
        reasons we will only allow snippet files to be edited if they reside in
        /var/lib/cobbler/snippets.
        """
        # FIXME: duplicate code with kickstart view/edit
        # FIXME: need to move to API level functions
        
        if is_read:
           what = "read_snippet"
        else:
           what = "write_snippet"
        
        self._log(what,name=snippet_file,token=token)
        self.check_access(token,what,snippet_file,is_read)
         
        if snippet_file.find("..") != -1 or not snippet_file.startswith("/"):
            utils.die(self.logger, "tainted file location")
        
        if not snippet_file.startswith("/var/lib/cobbler/snippets"):
            utils.die(self.logger, "unable to view or edit snippet in this location")
        
        if is_read:
            fileh = open(snippet_file,"r")
            data = fileh.read()
            fileh.close()
            return data
        else:
            if new_data == -1:
                # FIXME: no way to check if something is using it
                os.remove(snippet_file)
            else:
                fileh = open(snippet_file,"w+")
                fileh.write(new_data)
                fileh.close()
            return True
    
    
    def power_system(self,object_id,power=None,token=None,logger=None):
        """
        Internal implementation used by background_power, do not call
        directly if possible.  
        Allows poweron/poweroff/reboot of a system specified by object_id.
        """
        obj = self.__get_object(object_id)
        self.check_access(token, "power_system", obj)
        if power=="on":
            rc=self.api.power_on(obj, user=None, password=None, logger=logger)
        elif power=="off":
            rc=self.api.power_off(obj, user=None, password=None, logger=logger)
        elif power=="reboot":
            rc=self.api.reboot(obj, user=None, password=None, logger=logger)
        else:
            utils.die(self.logger, "invalid power mode '%s', expected on/off/reboot" % power)
        return rc
    
    
    def clear_system_logs(self, object_id, token=None, logger=None):
        """
        clears console logs of a system
        """
        obj = self.__get_object(object_id)
        self.check_access(token, "clear_system_logs", obj)
        rc=self.api.clear_logs(obj, logger=logger)
        return rc
    
    
###############################################################################
## Helper Methods #############################################################
    
    
    def __generate_event_id(self,optype):
        t = time.time()
        (year, month, day, hour, minute, second, weekday, julian, dst) = time.localtime()
        return "%04d-%02d-%02d_%02d%02d%02d_%s" % (year,month,day,hour,minute,second,optype)
    
    
    def _new_event(self, name):
        event_id = self.__generate_event_id("event")
        event_id = str(event_id)
        self.events[event_id] = [ float(time.time()), str(name), EVENT_INFO, [] ]
    
    
    def __start_task(self, thr_obj_fn, token, role_name, name, args, on_done=None):
        """
        Starts a new background task.
            token      -- token from login() call, all tasks require tokens
            role_name  -- used to check token against authn/authz layers
            thr_obj_fn -- function handle to run in a background thread
            name       -- display name to show in logs/events
            args       -- usually this is a single hash, containing options
            on_done    -- an optional second function handle to run after success (and only success)
        Returns a task id.
        """
        self.check_access(token, role_name)
        event_id = self.__generate_event_id(role_name) # use short form for logfile suffix
        event_id = str(event_id)
        self.events[event_id] = [ float(time.time()), str(name), EVENT_RUNNING, [] ]
        
        self._log("start_task(%s); event_id(%s)"%(name,event_id))
        logatron = clogger.Logger("/var/log/cobbler/tasks/%s.log" % event_id)
         
        thr_obj = CobblerThread(event_id,self,logatron,args)
        thr_obj._run = thr_obj_fn
        if on_done is not None:
           thr_obj.on_done = on_done
        thr_obj.start()
        return event_id
    
    
    def _set_task_state(self,thread_obj,event_id,new_state):
        event_id = str(event_id)
        if self.events.has_key(event_id):
            self.events[event_id][2] = new_state
            self.events[event_id][3] = [] # clear the list of who has read it
        if thread_obj is not None:
            if new_state == EVENT_COMPLETE: 
                thread_obj.logger.info("### TASK COMPLETE ###")
            if new_state == EVENT_FAILED: 
                thread_obj.logger.error("### TASK FAILED ###")
    
    
    def __sorter(self,a,b):
        """
        Helper function to sort two datastructure representations of
        cobbler objects by name.
        """
        return cmp(a["name"],b["name"])
    
    
    def _log(self,msg,user=None,token=None,name=None,object_id=None,attribute=None,debug=False,error=False):
        """
        Helper function to write data to the log file from the XMLRPC remote implementation.
        Takes various optional parameters that should be supplied when known.
        """
         
        # add the user editing the object, if supplied
        m_user = "?"
        if user is not None:
           m_user = user
        if token is not None:
           try:
               m_user = self.get_user_from_token(token)
           except:
               # invalid or expired token?
               m_user = "???"
        msg = "REMOTE %s; user(%s)" % (msg, m_user)
         
        if name is not None:
            msg = "%s; name(%s)" % (msg, name)
        
        if object_id is not None:
            msg = "%s; object_id(%s)" % (msg, object_id)
        
        # add any attributes being modified, if any
        if attribute:
           msg = "%s; attribute(%s)" % (msg, attribute)
        
        # log to the correct logger
        if error:
           logger = self.logger.error
        elif debug:
           logger = self.logger.debug
        else:
           logger = self.logger.info
        logger(msg)
    
    
    def __sort(self,data,sort_field=None):
        """
        Helper function used by the various find/search functions to return
        object representations in order.
        """
        sort_fields=["name"]
        sort_rev=False
        if sort_field is not None:
            if sort_field.startswith("!"):
                sort_field=sort_field[1:]
                sort_rev=True
            sort_fields.insert(0,sort_field)
        sortdata=[(x.sort_key(sort_fields),x) for x in data]
        if sort_rev:
            sortdata.sort(lambda a,b:cmp(b,a))
        else:
            sortdata.sort()
        return [x for (key, x) in sortdata]
            
    
    def __paginate(self,data,page=None,items_per_page=None,token=None):
        """
        Helper function to support returning parts of a selection, for
        example, for use in a web app where only a part of the results
        are to be presented on each screen.
        """
        default_page = 1
        default_items_per_page = 25
         
        try:
            page = int(page)
            if page < 1:
                page = default_page
        except:
            page = default_page
        try:
            items_per_page = int(items_per_page)
            if items_per_page <= 0:
                items_per_page = default_items_per_page
        except:
            items_per_page = default_items_per_page
        
        num_items = len(data)
        num_pages = ((num_items-1)/items_per_page)+1
        if num_pages==0:
            num_pages=1
        if page>num_pages:
            page=num_pages
        start_item = (items_per_page * (page-1))
        end_item   = start_item + items_per_page
        if start_item > num_items:
            start_item = num_items - 1
        if end_item > num_items:
            end_item = num_items
        data = data[start_item:end_item]
        
        if page > 1:
            prev_page = page - 1
        else:
            prev_page = None
        if page < num_pages:
            next_page = page + 1
        else:
            next_page = None
                        
        return (data,{
                'page'        : page,
                'prev_page'   : prev_page,
                'next_page'   : next_page,
                'pages'       : range(1,num_pages+1),
                'num_pages'   : num_pages,
                'num_items'   : num_items,
                'start_item'  : start_item,
                'end_item'    : end_item,
                'items_per_page' : items_per_page,
                'items_per_page_list' : [10,20,50,100,200,500],
        })
    
    
    def __get_object(self, object_id):
        """
        Helper function. Given an object id, return the actual object.
        """
        if object_id.startswith("___NEW___"):
           return self.object_cache[object_id][1]
        (otype, oname) = object_id.split("::",1)
        return self.api.get_item(otype,oname)
    
    
    def __is_interface_field(self,f):
        k = "*%s" % f
        for x in item_system.FIELDS:
           if k == x[0]:
              return True
        return False
    
    
    def get_kickstart_templates(self,token=None,**rest):
        """
        Returns all of the kickstarts that are in use by the system.
        """
        self._log("get_kickstart_templates",token=token)
        #self.check_access(token, "get_kickstart_templates")
        return utils.get_kickstart_templates(self.api)
    
    
    def get_snippets(self,token=None,**rest):
        """
        Returns all the kickstart snippets.
        """
        self._log("get_snippets",token=token)
    
        # FIXME: settings.snippetsdir should be used here
        return self.__get_sub_snippets("/var/lib/cobbler/snippets")
    
    
    def __get_sub_snippets(self, path):
        results = []
        files = glob.glob(os.path.join(path,"*"))
        for f in files:
           if os.path.isdir(f) and not os.path.islink(f):
              results += self.__get_sub_snippets(f)
           elif not os.path.islink(f):
              results.append(f)
        results.sort()
        return results
    
    
    def __upload_file(self, sys_name, file, size, offset, data):
        '''
        system: the name of the system
        name: the name of the file
        size: size of contents (bytes)
        data: base64 encoded file contents
        offset: the offset of the chunk
         files can be uploaded in chunks, if so the size describes
         the chunk rather than the whole file. the offset indicates where
         the chunk belongs
         the special offset -1 is used to indicate the final chunk'''
        contents = base64.decodestring(data)
        del data
        if offset != -1:
            if size is not None:
                if size != len(contents): 
                    return False
        
        #XXX - have an incoming dir and move after upload complete
        # SECURITY - ensure path remains under uploadpath
        tt = string.maketrans("/","+")
        fn = string.translate(file, tt)
        if fn.startswith('..'):
            raise CX("invalid filename used: %s" % fn)
         
        # FIXME ... get the base dir from cobbler settings()
        udir = "/var/log/cobbler/anamon/%s" % sys_name
        if not os.path.isdir(udir):
            os.mkdir(udir, 0755)
        
        fn = "%s/%s" % (udir, fn)
        try:
            st = os.lstat(fn)
        except OSError, e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise
        else:
            if not stat.S_ISREG(st.st_mode):
                raise CX("destination not a file: %s" % fn)
        
        fd = os.open(fn, os.O_RDWR | os.O_CREAT, 0644)
        # log_error("fd=%r" %fd)
        try:
            if offset == 0 or (offset == -1 and size == len(contents)):
                #truncate file
                fcntl.lockf(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                try:
                    os.ftruncate(fd, 0)
                    # log_error("truncating fd %r to 0" %fd)
                finally:
                    fcntl.lockf(fd, fcntl.LOCK_UN)
            if offset == -1:
                os.lseek(fd,0,2)
            else:
                os.lseek(fd,offset,0)
            #write contents
            fcntl.lockf(fd, fcntl.LOCK_EX|fcntl.LOCK_NB, len(contents), 0, 2)
            try:
                os.write(fd, contents)
                # log_error("wrote contents")
            finally:
                fcntl.lockf(fd, fcntl.LOCK_UN, len(contents), 0, 2)
            if offset == -1:
                if size is not None:
                    #truncate file
                    fcntl.lockf(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                    try:
                        os.ftruncate(fd, size)
                        # log_error("truncating fd %r to size %r" % (fd,size))
                    finally:
                        fcntl.lockf(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        return True
    
    
   ######
   # READ WRITE METHODS REQUIRE A TOKEN, use login()
   # TO OBTAIN ONE
   ######
    
    def __get_random(self,length):
        urandom = open("/dev/urandom")
        b64 = base64.encodestring(urandom.read(length))
        urandom.close()
        b64 = b64.replace("\n","")
        return b64 
    
    
    def __make_token(self,user):
        """
        Returns a new random token.
        """
        b64 = self.__get_random(25)
        self.token_cache[b64] = (time.time(), user)
        return b64
    
    
    def __invalidate_expired_tokens(self):
        """
        Deletes any login tokens that might have expired.
        Also removes expired events
        """
        timenow = time.time()
        for token in self.token_cache.keys():
            (tokentime, user) = self.token_cache[token]
            if (timenow > tokentime + TOKEN_TIMEOUT):
                self._log("expiring token",token=token,debug=True)
                del self.token_cache[token]
        # and also expired objects
        for oid in self.object_cache.keys():
            (tokentime, entry) = self.object_cache[oid]
            if (timenow > tokentime + CACHE_TIMEOUT):
                del self.object_cache[oid]
        for tid in self.events.keys():
            (eventtime, name, status, who) = self.events[tid]
            if (timenow > eventtime + EVENT_TIMEOUT):
                del self.events[tid]
            # logfile cleanup should be dealt w/ by logrotate
    
    
    def __validate_user(self,input_user,input_password):
        """
        Returns whether this user/pass combo should be given
        access to the cobbler read-write API.
        
        For the system user, this answer is always "yes", but
        it is only valid for the socket interface.
        
        FIXME: currently looks for users in /etc/cobbler/auth.conf
        Would be very nice to allow for PAM and/or just Kerberos.
        """
        return self.api.authenticate(input_user,input_password)
    
    
    def __validate_token(self,token): 
        """
        Checks to see if an API method can be called when
        the given token is passed in.  Updates the timestamp
        of the token automatically to prevent the need to
        repeatedly call login().  Any method that needs
        access control should call this before doing anything
        else.
        """
        self.__invalidate_expired_tokens()
        
        if self.token_cache.has_key(token):
            user = self.get_user_from_token(token)
            if user == "<system>":
               # system token is only valid over Unix socket
               return False
            self.token_cache[token] = (time.time(), user) # update to prevent timeout
            return True
        else:
            self._log("invalid token",token=token)
            raise CX("invalid token: %s" % token)
    
    
    def __name_to_object(self,resource,name):
        if resource.find("distro") != -1:
            return self.api.find_distro(name)
        if resource.find("profile") != -1:
            return self.api.find_profile(name)
        if resource.find("system") != -1:
            return self.api.find_system(name)
        if resource.find("repo") != -1:
            return self.api.find_repo(name)
        return None
 

# *********************************************************************************
# *********************************************************************************


class CobblerXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer.SimpleXMLRPCServer):
    def __init__(self, args):
        self.allow_reuse_address = True
        SimpleXMLRPCServer.SimpleXMLRPCServer.__init__(self,args)


# *********************************************************************************
# *********************************************************************************


class ProxiedXMLRPCInterface:

    def __init__(self,api,proxy_class):
        self.proxied = proxy_class(api)
        self.logger = self.proxied.api.logger

    def _dispatch(self, method, params, **rest):

        if not hasattr(self.proxied, method):
            raise CX("unknown remote method")

        method_handle = getattr(self.proxied, method)

        # FIXME: see if this works without extra boilerplate
        try:
            return method_handle(*params)
        except Exception, e:
            utils.log_exc(self.logger)
            raise e

