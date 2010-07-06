"""
new_distro.py defines a set of methods designed for testing Cobbler's
distros.

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

from base import *
import urllib2

class DistroTests(CobblerTest):
        
    def test_new_working_distro(self):
        """
        Attempt to create a Cobbler distro and tests its existence using find_distro
        """
        did, distro_name = self.create_distro()
        self.assertTrue(self.api.find_distro({'name': distro_name}) != None)
        return did, distro_name

    def test_new_nonworking_distro(self):
        """
        Attempt to create a distro lacking required information, 
        passes if api returns False.
        """
        did = self.api.new_distro(self.token)
        self.api.modify_distro(did, "name", "whatever", self.token)
        self.assertFalse(self.api.save_distro(did, self.token))
        return did
    
    def test_remove_distro(self):
        """
        Attempt to remove a distro
        """
        did, distro_name = self.test_new_working_distro()
        self.remove_distro(distro_name)
        self.assertTrue(self.api.find_distro({'name': distro_name}) == [])
    
    def test_copy_distro(self):
        """
        Attempt to copy a distro
        """
        did, distro_name = self.test_new_working_distro()
        result, new_name = self.copy_distro(did)
        self.assertTrue(self.api.find_distro({'name': new_name}) != None)
        
        return (did, distro_name), (new_name)
    
    def test_rename_distro(self):
        """
        Attempt to rename a distro
        """
        did, distro_name = self.test_new_working_distro()
        result, new_name = self.rename_distro(did)
        self.assertTrue(self.api.find_distro({'name': new_name}) != None)
        
        return (did, distro_name), (new_name)
    
    def test_new_distro_without_token(self):
        """
        Attempt to run new_distro method without supplying authenticated token
        """
        self.assertRaises(xmlrpclib.Fault, self.api.new_distro)

    def test_ks_mirror_accessible(self):
        url = "http://%s/cblr/ks_mirror/" % (cfg['cobbler_server']) 
        # Just want to be sure no 404 HTTPError is thrown:
    
        response = urllib2.urlopen(url)
        print response

