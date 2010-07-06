"""
Base.py defines a base set of helper methods for running automated Cobbler
XMLRPC API tests

Copyright 2009, Red Hat, Inc
Steve Salevan <ssalevan@redhat.com>

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

import yaml
import unittest
import traceback
import xmlrpclib
import random
import commands
import urlgrabber
import os.path
import cobbler.api as api

cfg = None

CONFIG_LOC = "./apitests.conf"
def read_config():
    global cfg
    f = open(CONFIG_LOC, 'r')
    cfg = yaml.load(f)
    f.close()

read_config()


TEST_DISTRO_PREFIX = "TEST-DISTRO-"
TEST_PROFILE_PREFIX = "TEST-PROFILE-"
TEST_SYSTEM_PREFIX = "TEST-SYSTEM-"

FAKE_KS_CONTENTS = "HELLO WORLD"

# Files to pretend are kernel/initrd, don't point to anything real.
# These will be created if they don't already exist.
FAKE_KERNEL = "/tmp/cobbler-testing-fake-kernel"
FAKE_INITRD = "/tmp/cobbler-testing-fake-initrd"
FAKE_KICKSTART = "/tmp/cobbler-testing-kickstart"

class CobblerTest(unittest.TestCase):

    def __cleanUpObjects(self):
        """ Cleanup the test objects we created during testing. """
        for system_name in self.cleanup_systems:
            try:
                self.api.remove_system(system_name, self.token)
            except Exception, e:
                print("ERROR: unable to delete system: %s" % system_name)
                print(e)
                pass

        for profile_name in self.cleanup_profiles:
            try:
                self.api.remove_profile(profile_name, self.token)
            except Exception, e:
                print("ERROR: unable to delete profile: %s" % profile_name)
                print(e)
                pass

        for distro_name in self.cleanup_distros:
            try:
                self.api.remove_distro(distro_name, self.token)
                print("Removed distro: %s" % distro_name)
            except Exception, e:
                print("ERROR: unable to delete distro: %s" % distro_name)
                print(e)
                pass

    def setUp(self):
        """
        Sets up Cobbler API connection and logs in
        """
        self.api = api.CobblerAPI(username=cfg["cobbler_user"],
            password=cfg["cobbler_pass"])
        self.token = self.api.token

        # Store object names to clean up in teardown. Be sure not to 
        # store anything in here unless we're sure it was successfully
        # created by the tests.
        self.cleanup_distros = []
        self.cleanup_profiles = []
        self.cleanup_systems = []

        # Create a fake kernel/init pair in /tmp, Cobbler doesn't care what
        # these files actually contain.
        if not os.path.exists(FAKE_KERNEL):
            commands.getstatusoutput("touch %s" % FAKE_KERNEL)
        if not os.path.exists(FAKE_INITRD):
            commands.getstatusoutput("touch %s" % FAKE_INITRD)
        if not os.path.exists(FAKE_KICKSTART):
            f = open(FAKE_KICKSTART, 'w')
            f.write(FAKE_KS_CONTENTS)
            f.close()

    def tearDown(self):
        """
        Removes any Cobbler objects created during a test
        """
        self.__cleanUpObjects()
        
    def create_distro(self, distro_dict=None):
        """
        Create a test distro with a random name, store it for cleanup 
        during teardown.

        Returns a tuple of the objects ID and name.
        """
        if not distro_dict:
            distro_dict = {
                "name"                      : "%s%s" % (TEST_DISTRO_PREFIX, random.randint(1, 1000000)),
                "kernel"                    : FAKE_KERNEL,
                "initrd"                    : FAKE_INITRD,
                "kopts"                     : { "dog" : "fido", "cat" : "fluffy" },
                "ksmeta"                    : "good=sg1 evil=gould",
                "breed"                     : "redhat",
                "os-version"                : "rhel5",
                "owners"                    : "same dave",
                "mgmt-classes"              : "blip",
                "comment"                   : "test distro",
                "redhat_management_key"     : "1-ABC123",
                "redhat_management_server"  : "mysatellite.example.com",
            }
        
        did = self.api.new_distro(self.token)
        for attr, val in distro_dict.items():
            self.api.modify_distro(did, attr, val, self.token)
        
        self.api.save_distro(did, self.token)
        self.cleanup_distros.append(distro_dict['name'])

        url = "http://%s/cblr/svc/op/list/what/distros" % cfg['cobbler_server'] 
        data = urlgrabber.urlread(url)
        self.assertNotEquals(-1, data.find(distro_dict['name']))

        return (did, distro_dict['name'])
    
    def remove_distro(self, distro_name):
        """
        Remove the given distro.
        """
        return self.api.remove_distro(distro_name, self.token)
    
    def copy_distro(self, distro_id):
        """
        Copy the given distro and return (success, copy's name).
        """
        new_name = "%s%s" % (TEST_DISTRO_PREFIX, random.randint(1, 1000000))
        success = self.api.copy_distro(distro_id, new_name, self.token)
        if success:
            self.cleanup_distros.append(new_name)
        return success, new_name
    
    def rename_distro(self, distro_id):
        """
        Renam the given distro and return (success, copy's name).
        """
        new_name = "%s%s" % (TEST_DISTRO_PREFIX, random.randint(1, 1000000))
        success = self.api.rename_distro(distro_id, new_name, self.token)
        if success:
            self.cleanup_distros.append(new_name)
        return success, new_name

    def create_profile(self, distro_name, profile_dict=None):
        """
        Create a test profile with random name associated with the given distro.

        Returns (profile ID, profile name).
        """
        if not profile_dict:
            profile_name = "%s%s" % (TEST_PROFILE_PREFIX, random.randint(1, 1000000))
            profile_dict = {
                "name"                      : profile_name,
                "distro"                    : distro_name,
                "kickstart"                 : FAKE_KICKSTART,
                "kopts"                     : { "dog" : "fido", "cat" : "fluffy" },
                "kopts-post"                : { "phil" : "collins", "steve" : "hackett" },
                "ksmeta"                    : "good=sg1 evil=gould",
                "breed"                     : "redhat",
                "owners"                    : "sam dave",
                "mgmt-classes"              : "blip",
                "comment"                   : "test profile",
                "redhat_management_key"     : "1-ABC123",
                "redhat_management_server"  : "mysatellite.example.com",
                "virt_bridge"               : "virbr0",
                "virt_cpus"                 : "2",
                "virt_file_size"            : "3",
                "virt_path"                 : "/opt/qemu/%s" % profile_name,
                "virt_ram"                  : "1024",
                "virt_type"                 : "qemu",
            }
        else:
            profile_dict["distro"] = distro_name
        
        profile_id = self.api.new_profile(self.token)
        for attr, val in profile_dict.items():
            self.api.modify_profile(profile_id, attr, val, self.token)
        
        self.api.save_profile(profile_id, self.token)
        self.cleanup_profiles.append(profile_dict['name'])

        # Check cobbler services URLs:
        url = "http://%s/cblr/svc/op/ks/profile/%s" % (cfg['cobbler_server'], 
                profile_dict['name'])
        data = urlgrabber.urlread(url)
        self.assertEquals(FAKE_KS_CONTENTS, data)

        url = "http://%s/cblr/svc/op/list/what/profiles" % cfg['cobbler_server'] 
        data = urlgrabber.urlread(url)
        self.assertNotEquals(-1, data.find(profile_dict['name']))

        return (profile_id, profile_dict['name'])
    
    def copy_profile(self, profile_id):
        """
        Copy the given profile and return (success, copy's name).
        """
        new_name = "%s%s" % (TEST_PROFILE_PREFIX, random.randint(1, 1000000))
        success = self.api.copy_profile(profile_id, new_name, self.token)
        if success:
            self.cleanup_profiles.append(new_name)
        return success, new_name
    
    def rename_profile(self, profile_id):
        """
        Rename the given profile and return (success, copy's name).
        """
        new_name = "%s%s" % (TEST_PROFILE_PREFIX, random.randint(1, 1000000))
        success = self.api.rename_profile(profile_id, new_name, self.token)
        if success:
            self.cleanup_profiles.append(new_name)
        return success, new_name

    def create_system(self, profile_name, system_dict=None):
        """ 
        Create a system record. 
        
        Returns (system id, system name).
        """
        if not system_dict:
            system_dict = {
                "name" : "%s%s" % (TEST_SYSTEM_PREFIX, random.randint(1, 1000000)),
                "profile" : profile_name,
            }
        else:
            system_dict['profile'] = profile_name
        
        system_id = self.api.new_system(self.token)
        for attr, val in system_dict.items():
            self.api.modify_system(system_id, attr, val, self.token)
        self.api.save_system(system_id, self.token)
        
        return (system_id, system_dict['name'])

    def copy_system(self, system_id):
        """
        Copy the given system and return (success, copy's name).
        """
        new_name = "%s%s" % (TEST_SYSTEM_PREFIX, random.randint(1, 1000000))
        success = self.api.copy_system(system_id, new_name, self.token)
        if success:
            self.cleanup_systems.append(new_name)
        return success, new_name
    
    def rename_system(self, system_id):
        """
        Rename the given system and return (success, copy's name).
        """
        new_name = "%s%s" % (TEST_SYSTEM_PREFIX, random.randint(1, 1000000))
        success = self.api.rename_system(system_id, new_name, self.token)
        if success:
            self.cleanup_systems.append(new_name)
        return success, new_name
        
    
