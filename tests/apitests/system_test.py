"""
Copyright 2009, Red Hat, Inc

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

from base import *
import time

class SystemTests(CobblerTest):

    def setUp(self):
        CobblerTest.setUp(self)
        (self.distro_id, self.distro_name) = self.create_distro()
        (self.profile_id, self.profile_name) = self.create_profile(self.distro_name)

    def test_new_working_system(self):
        """ Test creation of a cobbler system. """
        (system_id, system_name) = self.create_system(self.profile_name)
        systems = self.api.find_system({'name': system_name})
        self.assertTrue(len(systems) > 0)
        return system_id, system_name
    
    def test_new_nonworking_system(self):
        """
        Attempt to create a system lacking required information.
        """
        system_id = self.api.new_system(self.token)
        self.api.modify_profile(system_id, "name", "%s%s" % (TEST_SYSTEM_PREFIX, random.randint(1, 1000000)), self.token)
        self.assertFalse(self.api.save_system(system_id, self.token))
    
    def test_remove_system(self):
        """
        Attempt to remove a cobbler system.
        """
        system_id, system_name = self.test_new_working_system()
        self.api.remove_system(system_name, self.token)
        self.assertTrue(self.api.find_system({'name': system_name}) == [])
    
    def test_copy_system(self):
        """
        Attempt to copy a cobbler system.
        """
        system_id, system_name = self.test_new_working_system()
        result, new_name = self.copy_system(system_id)
        self.assertTrue(self.api.find_system({'name': new_name}) != [])

        return (system_id, system_name), (new_name)
    
    def test_rename_system(self):
        """
        Attempt to copy a cobbler system.
        """
        system_id, system_name = self.test_new_working_system()
        result, new_name = self.rename_system(system_id)
        self.assertTrue(self.api.find_system({'name': new_name}) != [])

        return (system_id, system_name), (new_name)
    
    def test_new_system_without_token(self):
        """
        Attempt to run new_system method without supplying authenticated token
        """
        self.assertRaises(xmlrpclib.Fault, self.api.new_system)


        
    # Old tests laying around indicate this should pass, but it no longer seems too?
    #def test_nopxe(self):
    #    """ Test network boot loop prevention. """
    #    (system_id, system_name) = self.create_system(self.profile_name)
    #    self.api.modify_system(system_id, 'netboot_enabled', True, self.token)
    #    self.api.save_system(system_id, self.token)
    #    #systems = self.api.find_system({'name': system_name})

    #    url = "http://%s/cblr/svc/op/nopxe/system/%s" % \
    #            (cfg['cobbler_server'], system_name)
    #    data = urlgrabber.urlread(url)
    #    time.sleep(2)
    #    results = self.api.get_blended_data("", system_name)
    #    print(results['netboot_enabled'])
    #    self.assertFalse(results['netboot_enabled'])

        
