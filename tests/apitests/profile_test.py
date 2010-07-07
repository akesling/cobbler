"""
new_profile.py defines a set of methods designed for testing Cobbler
profiles.

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

import urllib2

from base import *

class ProfileTests(CobblerTest):

    def test_new_working_profile(self):
        """
        Attempt to create a Cobbler profile.
        """
        distro_name = self.create_distro()[1]
        pid, profile_name = self.create_profile(distro_name)
        self.assertTrue(self.api.find_profiles({'name': profile_name}) != [])
        return pid, profile_name
        
    def test_new_nonworking_profile(self):
        """
        Attempt to create a profile lacking required information.
        """
        pid = self.api.new_profile(self.token)
        self.api.modify_profile(pid, "name", "anythinggoes", self.token)
        self.assertFalse(self.api.save_profile(pid, self.token))

    def test_remove_profile(self):
        """
        Attempt to remove a profile.
        """
        pid, profile_name = self.test_new_working_profile()
        self.api.remove_profile(profile_name, self.token)
        self.assertTrue(self.api.find_profiles({'name': profile_name}) == [])
    
    def test_copy_profile(self):
        """
        Attempt to copy a profile.
        """
        pid, profile_name = self.test_new_working_profile()
        result, new_name = self.copy_profile(pid)
        self.assertTrue(self.api.find_profiles({'name': new_name}) != [])
        
        return (pid, profile_name), (new_name)
    
    def test_rename_profile(self):
        """
        Attempt to rename a profile.
        """
        pid, profile_name = self.test_new_working_profile()
        result, new_name = self.rename_profile(pid)
        self.assertTrue(self.api.find_profiles({'name': new_name}) != [])
        
        return (pid, profile_name), (new_name)
    
    def test_new_profile_without_token(self):
        """
        Attempt to run new_profile method without supplying authenticated token
        """
        self.assertRaises(xmlrpclib.Fault, self.api.new_profile)


    def test_getks_no_such_profile(self):
        url = "http://%s/cblr/svc/op/ks/profile/%s" % (cfg['cobbler_server'], 
                "doesnotexist")
        try:
            response = urllib2.urlopen(url)
            self.fail()
        except urllib2.HTTPError, e:
            self.assertEquals(404, e.code)
