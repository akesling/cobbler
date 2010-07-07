"""

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
# XXX: These tests came from the bottom of remote.py and were just
#       cluttering it up from what I could tell... they may be a useful
#       base for more extensive API testing.  Just storing them here
#       for now.


def _test_setup_modules(authn="authn_testing",authz="authz_allowall",pxe_once=1):

    # rewrite modules.conf so we know we can use the testing module
    # for xmlrpc rw testing (Makefile will put the user value back)
    
    import yaml
    import Cheetah.Template as Template

    MODULES_TEMPLATE = "installer_templates/modules.conf.template"
    DEFAULTS = "installer_templates/defaults"
    fh = open(DEFAULTS)
    data = yaml.load(fh.read())
    fh.close()
    data["authn_module"] = authn
    data["authz_module"] = authz
    data["pxe_once"] = pxe_once
    
    t = Template.Template(file=MODULES_TEMPLATE, searchList=[data])
    open("/etc/cobbler/modules.conf","w+").write(t.respond())


def _test_setup_settings(pxe_once=1):

    # rewrite modules.conf so we know we can use the testing module
    # for xmlrpc rw testing (Makefile will put the user value back)
   
    import yaml
    import Cheetah.Template as Template

    MODULES_TEMPLATE = "installer_templates/settings.template"
    DEFAULTS = "installer_templates/defaults"
    fh = open(DEFAULTS)
    data = yaml.load(fh.read())
    fh.close()
    data["pxe_once"] = pxe_once

    t = Template.Template(file=MODULES_TEMPLATE, searchList=[data])
    open("/etc/cobbler/settings","w+").write(t.respond())

    

def _test_bootstrap_restart():

   rc1 = subprocess.call(["/sbin/service","cobblerd","restart"],shell=False,close_fds=True)
   assert rc1 == 0
   rc2 = subprocess.call(["/sbin/service","httpd","restart"],shell=False,close_fds=True)
   assert rc2 == 0
   time.sleep(5)
   
   _test_remove_objects()

def _test_remove_objects():

   api = cobbler_api.BootAPI() # local handle

   # from ro tests
   d0 = api.find_distro("distro0")
   i0 = api.find_image("image0")
   r0 = api.find_image("repo0")

   # from rw tests
   d1 = api.find_distro("distro1")
   i1 = api.find_image("image1")
   r1 = api.find_image("repo1")
   
   if d0 is not None: api.remove_distro(d0, recursive = True)
   if i0 is not None: api.remove_image(i0)
   if r0 is not None: api.remove_repo(r0)
   if d1 is not None: api.remove_distro(d1, recursive = True)
   if i1 is not None: api.remove_image(i1)
   if r1 is not None: api.remove_repo(r1)
   

def test_xmlrpc_ro():

   _test_bootstrap_restart()

   server = xmlrpclib.Server("http://127.0.0.1/cobbler_api")
   time.sleep(2) 

   # delete all distributions
   distros  = server.get_distros()
   profiles = server.get_profiles()
   systems  = server.get_systems()
   repos    = server.get_repos()
   images   = server.get_systems()
   settings = server.get_settings()
    
   assert type(distros) == type([])
   assert type(profiles) == type([]) 
   assert type(systems) == type([])
   assert type(repos) == type([])
   assert type(images) == type([])
   assert type(settings) == type({})

   # now populate with something more useful
   # using the non-remote API

   api = cobbler_api.BootAPI() # local handle

   before_distros  = len(api.distros())
   before_profiles = len(api.profiles())
   before_systems  = len(api.systems())
   before_repos    = len(api.repos())
   before_images   = len(api.images())

   fake = open("/tmp/cobbler.fake","w+")
   fake.write("")
   fake.close()

   distro = api.new_distro()
   distro.set_name("distro0")
   distro.set_kernel("/tmp/cobbler.fake")
   distro.set_initrd("/tmp/cobbler.fake")
   api.add_distro(distro)
   
   repo = api.new_repo()
   repo.set_name("repo0")

   if not os.path.exists("/tmp/empty"):
      os.mkdir("/tmp/empty",770)
   repo.set_mirror("/tmp/empty")
   files = glob.glob("rpm-build/*.rpm")
   if len(files) == 0:
      raise Exception("Tests must be run from the cobbler checkout directory.")
   subprocess.call("cp rpm-build/*.rpm /tmp/empty",shell=True,close_fds=True)
   api.add_repo(repo)

   profile = api.new_profile()
   profile.set_name("profile0")
   profile.set_distro("distro0")
   profile.set_kickstart("/var/lib/cobbler/kickstarts/sample.ks")
   profile.set_repos(["repo0"])
   api.add_profile(profile)

   system = api.new_system()
   system.set_name("system0")
   system.set_hostname("hostname0")
   system.set_gateway("192.168.1.1")
   system.set_profile("profile0")
   system.set_dns_name("hostname0","eth0")
   api.add_system(system)

   image = api.new_image()
   image.set_name("image0")
   image.set_file("/tmp/cobbler.fake")
   api.add_image(image)

   # reposync is required in order to create the repo config files
   api.reposync(name="repo0")
   
   # FIXME: the following tests do not yet look to see that all elements
   # retrieved match what they were created with, but we presume this
   # all works.  It is not a high priority item to test but do not assume
   # this is a complete test of access functions.

   def comb(haystack, needle):
      for x in haystack:
         if x["name"] == needle:
             return True
      return False
   
   distros = server.get_distros()

   assert len(distros) == before_distros + 1
   assert comb(distros, "distro0")
   
   profiles = server.get_profiles()

   print "BEFORE: %s" % before_profiles
   print "CURRENT: %s" % len(profiles)
   for p in profiles:
      print "   PROFILES: %s" % p["name"]
   for p in api.profiles():
      print "   API     : %s" % p.name

   assert len(profiles) == before_profiles + 1
   assert comb(profiles, "profile0")

   systems = server.get_systems()
   # assert len(systems) == before_systems + 1
   assert comb(systems, "system0")

   repos = server.get_repos()
   # FIXME: disable temporarily
   # assert len(repos) == before_repos + 1
   assert comb(repos, "repo0")


   images = server.get_images()
   # assert len(images) == before_images + 1
   assert comb(images, "image0")

   # now test specific gets
   distro = server.get_distro("distro0")
   assert distro["name"] == "distro0"
   assert type(distro["kernel_options"] == type({}))

   profile = server.get_profile("profile0")
   assert profile["name"] == "profile0"
   assert type(profile["kernel_options"] == type({}))

   system = server.get_system("system0")
   assert system["name"] == "system0"
   assert type(system["kernel_options"] == type({}))

   repo = server.get_repo("repo0")
   assert repo["name"] == "repo0"

   image = server.get_image("image0")
   assert image["name"] == "image0"
  
   # now test the calls koan uses   
   # the difference is that koan's object types are flattened somewhat
   # and also that they are passed through utils.blender() so they represent
   # not the object but the evaluation of the object tree at that object.

   server.update() # should be unneeded
   distro  = server.get_distro_for_koan("distro0")
   assert distro["name"] == "distro0"
   assert type(distro["kernel_options"] == type(""))

   profile = server.get_profile_for_koan("profile0")
   assert profile["name"] == "profile0"
   assert type(profile["kernel_options"] == type(""))

   system = server.get_system_for_koan("system0")
   assert system["name"] == "system0"
   assert type(system["kernel_options"] == type(""))

   repo = server.get_repo_for_koan("repo0")
   assert repo["name"] == "repo0"

   image = server.get_image_for_koan("image0")
   assert image["name"] == "image0"

   # now test some of the additional webui calls
   # compatible profiles, etc

   assert server.ping() == True

   assert server.get_size("distros") == 1
   assert server.get_size("profiles") == 1
   assert server.get_size("systems") == 1
   assert server.get_size("repos") == 1
   assert server.get_size("images") == 1

   templates = server.get_kickstart_templates("???")
   assert "/var/lib/cobbler/kickstarts/sample.ks" in templates
   assert server.is_kickstart_in_use("/var/lib/cobbler/kickstarts/sample.ks","???") == True
   assert server.is_kickstart_in_use("/var/lib/cobbler/kickstarts/legacy.ks","???") == False
   generated = server.generate_kickstart("profile0")
   assert type(generated) == type("")
   assert generated.find("ERROR") == -1
   assert generated.find("url") != -1
   assert generated.find("network") != -1

   yumcfg = server.get_repo_config_for_profile("profile0")
   assert type(yumcfg) == type("")
   assert yumcfg.find("ERROR") == -1
   assert yumcfg.find("http://") != -1
 
   yumcfg = server.get_repo_config_for_system("system0")
   assert type(yumcfg) == type("")
   assert yumcfg.find("ERROR") == -1
   assert yumcfg.find("http://") != -1

   server.register_mac("CC:EE:FF:GG:AA:AA","profile0")
   systems = server.get_systems()
   found = False
   for s in systems:
       if s["name"] == "CC:EE:FF:GG:AA:AA":
           for iname in s["interfaces"]:
               if s["interfaces"]["iname"].get("mac_address") == "CC:EE:FF:GG:AA:AA":
                  found = True
                  break
       if found:
           break

   # FIXME: mac registration test code needs a correct settings file in order to 
   # be enabled.
   # assert found == True

   # FIXME:  the following tests don't work if pxe_just_once is disabled in settings so we need
   # to account for this by turning it on...
   # basically we need to rewrite the settings file 

   # system = server.get_system("system0")
   # assert system["netboot_enabled"] == "True"
   # rc = server.disable_netboot("system0") 
   # assert rc == True
   # ne = server.get_system("system0")["netboot_enabled"]
   # assert ne == False

   # FIXME: tests for new built-in configuration management feature
   # require that --template-files attributes be set.  These do not
   # retrieve the kickstarts but rather config files (see Wiki topics).
   # This is probably better tested at the URL level with urlgrabber, one layer
   # up, in a different set of tests..

   # FIXME: tests for rendered kickstart retrieval, same as above

   assert server.run_install_triggers("pre","profile","profile0","127.0.0.1")
   assert server.run_install_triggers("post","profile","profile0","127.0.0.1")
   assert server.run_install_triggers("pre","system","system0","127.0.0.1")
   assert server.run_install_triggers("post","system","system0","127.0.0.1")
   
   ver = server.version()
   assert (str(ver)[0] == "?" or str(ver).find(".") != -1)

   # do removals via the API since the read-only API can't do them
   # and the read-write tests are seperate

   _test_remove_objects()

   # this last bit mainly tests the tests, to ensure we've left nothing behind
   # not XMLRPC.  Tests polluting the user config is not desirable even though
   # we do save/restore it.

   # assert (len(api.distros()) == before_distros)
   # assert (len(api.profiles()) == before_profiles)
   # assert (len(api.systems()) == before_systems)
   # assert (len(api.images()) == before_images)
   # assert (len(api.repos()) == before_repos)
  
def test_xmlrpc_rw():

   # ideally we need tests for the various auth modes, not just one 
   # and the ownership module, though this will provide decent coverage.

   _test_setup_modules(authn="authn_testing",authz="authz_allowall")
   _test_bootstrap_restart()

   server = xmlrpclib.Server("http://127.0.0.1/cobbler_api") # remote 
   api = cobbler_api.BootAPI() # local instance, /DO/ ping cobblerd

   # note if authn_testing is not engaged this will not work
   # test getting token, will raise remote exception on fail 

   token = server.login("testing","testing")

   # create distro
   did = server.new_distro(token)
   server.modify_distro(did, "name", "distro1", token)
   server.modify_distro(did, "kernel", "/tmp/cobbler.fake", token) 
   server.modify_distro(did, "initrd", "/tmp/cobbler.fake", token) 
   server.modify_distro(did, "kopts", { "dog" : "fido", "cat" : "fluffy" }, token) # hash or string
   server.modify_distro(did, "ksmeta", "good=sg1 evil=gould", token) # hash or string
   server.modify_distro(did, "breed", "redhat", token)
   server.modify_distro(did, "os-version", "rhel5", token)
   server.modify_distro(did, "owners", "sam dave", token) # array or string
   server.modify_distro(did, "mgmt-classes", "blip", token) # list or string
   server.modify_distro(did, "template-files", "/tmp/cobbler.fake=/tmp/a /etc/fstab=/tmp/b",token) # hash or string
   server.modify_distro(did, "comment", "...", token)
   server.modify_distro(did, "redhat_management_key", "ALPHA", token)
   server.modify_distro(did, "redhat_management_server", "rhn.example.com", token)
   server.save_distro(did, token)

   # use the non-XMLRPC API to check that it's added seeing we tested XMLRPC RW APIs above
   # this makes extra sure it's been committed to disk.
   api.deserialize() 
   assert api.find_distro("distro1") != None

   pid = server.new_profile(token)
   server.modify_profile(pid, "name",   "profile1", token)
   server.modify_profile(pid, "distro", "distro1", token)
   server.modify_profile(pid, "enable-menu", True, token)
   server.modify_profile(pid, "kickstart", "/var/lib/cobbler/kickstarts/sample.ks", token)
   server.modify_profile(pid, "kopts", { "level" : "11" }, token)
   server.modify_profile(pid, "kopts_post", "noapic", token)
   server.modify_profile(pid, "virt_auto_boot", 0, token)
   server.modify_profile(pid, "virt_file_size", 20, token)
   server.modify_profile(pid, "virt_ram", 2048, token)
   server.modify_profile(pid, "repos", [], token)
   server.modify_profile(pid, "template-files", {}, token)
   server.modify_profile(pid, "virt_path", "VolGroup00", token)
   server.modify_profile(pid, "virt_bridge", "virbr1", token)
   server.modify_profile(pid, "virt_cpus", 2, token)
   server.modify_profile(pid, "owners", [ "sam", "dave" ], token)
   server.modify_profile(pid, "mgmt_classes", "one two three", token)
   server.modify_profile(pid, "comment", "...", token)
   server.modify_profile(pid, "name_servers", ["one","two"], token)
   server.modify_profile(pid, "name_servers_search", ["one","two"], token)
   server.modify_profile(pid, "redhat_management_key", "BETA", token)
   server.modify_distro(did, "redhat_management_server", "sat.example.com", token)
   server.save_profile(pid, token)

   api.deserialize() 
   assert api.find_profile("profile1") != None

   sid = server.new_system(token)
   server.modify_system(sid, 'name', 'system1', token)
   server.modify_system(sid, 'hostname', 'system1', token)
   server.modify_system(sid, 'gateway', '127.0.0.1', token)
   server.modify_system(sid, 'profile', 'profile1', token)
   server.modify_system(sid, 'kopts', { "dog" : "fido" }, token)
   server.modify_system(sid, 'kopts_post', { "cat" : "fluffy" }, token)
   server.modify_system(sid, 'kickstart', '/var/lib/cobbler/kickstarts/sample.ks', token)
   server.modify_system(sid, 'netboot_enabled', True, token)
   server.modify_system(sid, 'virt_path', "/opt/images", token)
   server.modify_system(sid, 'virt_type', 'qemu', token)
   server.modify_system(sid, 'name_servers', 'one two three four', token)
   server.modify_system(sid, 'name_servers_search', 'one two three four', token)
   server.modify_system(sid, 'modify_interface', { 
       "macaddress-eth0"   : "AA:BB:CC:EE:EE:EE",
       "ipaddress-eth0"    : "192.168.10.50",
       "gateway-eth0"      : "192.168.10.1",
       "virtbridge-eth0"   : "virbr0",
       "dnsname-eth0"      : "foo.example.com",
       "static-eth0"       : False,
       "dhcptag-eth0"      : "section2",
       "staticroutes-eth0" : "a:b:c d:e:f"
   }, token)
   server.modify_system(sid, 'modify_interface', {
       "static-eth1"     : False,
       "staticroutes-eth1" : [ "g:h:i", "j:k:l" ]
   }, token)
   server.modify_system(sid, "mgmt_classes", [ "one", "two", "three"], token)
   server.modify_system(sid, "template_files", {}, token)
   server.modify_system(sid, "comment", "...", token)
   server.modify_system(sid, "power_address", "power.example.org", token)
   server.modify_system(sid, "power_type", "ipmitool", token)
   server.modify_system(sid, "power_user", "Admin", token)
   server.modify_system(sid, "power_pass", "magic", token)
   server.modify_system(sid, "power_id", "7", token)
   server.modify_system(sid, "redhat_management_key", "GAMMA", token)
   server.modify_distro(did, "redhat_management_server", "spacewalk.example.com", token)

   server.save_system(sid,token)
   
   api.deserialize() 
   assert api.find_system("system1") != None
   # FIXME: add some checks on object contents

   iid = server.new_image(token)
   server.modify_image(iid, "name", "image1", token)
   server.modify_image(iid, "image_type", "iso", token)
   server.modify_image(iid, "breed", "redhat", token)
   server.modify_image(iid, "os_version", "rhel5", token)
   server.modify_image(iid, "arch", "x86_64", token)
   server.modify_image(iid, "file", "nfs://server/path/to/x.iso", token)
   server.modify_image(iid, "owners", [ "alex", "michael" ], token)
   server.modify_image(iid, "virt_auto_boot", 0, token)
   server.modify_image(iid, "virt_cpus", 1, token)
   server.modify_image(iid, "virt_file_size", 5, token)
   server.modify_image(iid, "virt_bridge", "virbr0", token)
   server.modify_image(iid, "virt_path", "VolGroup01", token)
   server.modify_image(iid, "virt_ram", 1024, token)
   server.modify_image(iid, "virt_type", "xenpv", token)
   server.modify_image(iid, "comment", "...", token)
   server.save_image(iid, token)

   api.deserialize() 
   assert api.find_image("image1") != None
   # FIXME: add some checks on object contents
   
   # FIXME: repo adds
   rid = server.new_repo(token)
   server.modify_repo(rid, "name", "repo1", token)
   server.modify_repo(rid, "arch", "x86_64", token)
   server.modify_repo(rid, "mirror", "http://example.org/foo/x86_64", token)
   server.modify_repo(rid, "keep_updated", True, token)
   server.modify_repo(rid, "priority", "50", token)
   server.modify_repo(rid, "rpm_list", [], token)
   server.modify_repo(rid, "createrepo_flags", "--verbose", token)
   server.modify_repo(rid, "yumopts", {}, token)
   server.modify_repo(rid, "owners", [ "slash", "axl" ], token)
   server.modify_repo(rid, "mirror_locally", True, token)
   server.modify_repo(rid, "environment", {}, token)
   server.modify_repo(rid, "comment", "...", token)
   server.save_repo(rid, token)
   
   api.deserialize() 
   assert api.find_repo("repo1") != None
   # FIXME: add some checks on object contents

   # test handle lookup

   did = server.get_distro_handle("distro1", token)
   assert did != None
   rid = server.get_repo_handle("repo1", token)
   assert rid != None
   iid = server.get_image_handle("image1", token)
   assert iid != None

   # test renames
   rc = server.rename_distro(did, "distro2", token)
   assert rc == True
   # object has changed due to parent rename, get a new handle
   pid = server.get_profile_handle("profile1", token)
   assert pid != None
   rc = server.rename_profile(pid, "profile2", token)
   assert rc == True
   # object has changed due to parent rename, get a new handle
   sid = server.get_system_handle("system1", token)
   assert sid != None
   rc = server.rename_system(sid, "system2", token)
   assert rc == True
   rc = server.rename_repo(rid, "repo2", token)
   assert rc == True
   rc = server.rename_image(iid, "image2", token)
   assert rc == True
   
   # FIXME: make the following code unneccessary
   api.clear()
   api.deserialize()

   assert api.find_distro("distro2") != None
   assert api.find_profile("profile2") != None
   assert api.find_repo("repo2") != None
   assert api.find_image("image2") != None
   assert api.find_system("system2") != None

   # BOOKMARK: currently here in terms of test testing.

   for d in api.distros():
      print "FOUND DISTRO: %s" % d.name


   assert api.find_distro("distro1") == None
   assert api.find_profile("profile1") == None
   assert api.find_repo("repo1") == None
   assert api.find_image("image1") == None
   assert api.find_system("system1") == None
   
   did = server.get_distro_handle("distro2", token)
   assert did != None
   pid = server.get_profile_handle("profile2", token)
   assert pid != None
   rid = server.get_repo_handle("repo2", token)
   assert rid != None
   sid = server.get_system_handle("system2", token)
   assert sid != None
   iid = server.get_image_handle("image2", token)
   assert iid != None

   # test copies
   server.copy_distro(did, "distro1", token)
   server.copy_profile(pid, "profile1", token)
   server.copy_repo(rid, "repo1", token)
   server.copy_image(iid, "image1", token)
   server.copy_system(sid, "system1", token)

   api.deserialize()
   assert api.find_distro("distro2") != None
   assert api.find_profile("profile2") != None
   assert api.find_repo("repo2") != None
   assert api.find_image("image2") != None
   assert api.find_system("system2") != None

   assert api.find_distro("distro1") != None
   assert api.find_profile("profile1") != None
   assert api.find_repo("repo1") != None
   assert api.find_image("image1") != None
   assert api.find_system("system1") != None
  
   assert server.last_modified_time() > 0
   print server.get_distros_since(2)
   assert len(server.get_distros_since(2)) > 0
   assert len(server.get_profiles_since(2)) > 0
   assert len(server.get_systems_since(2)) > 0
   assert len(server.get_images_since(2)) > 0
   assert len(server.get_repos_since(2)) > 0
   assert len(server.get_distros_since(2)) > 0

   now = time.time()
   the_future = time.time() + 99999
   assert len(server.get_distros_since(the_future)) == 0
 
   # it would be cleaner to do this from the distro down
   # and the server.update calls would then be unneeded.
   server.remove_system("system1", token)
   server.update()
   server.remove_profile("profile1", token)
   server.update()
   server.remove_distro("distro1", token)
   server.remove_repo("repo1", token)
   server.remove_image("image1", token)

   server.remove_system("system2", token)
   # again, calls are needed because we're deleting in the wrong
   # order.  A fix is probably warranted for this.
   server.update()
   server.remove_profile("profile2", token)
   server.update()
   server.remove_distro("distro2", token)
   server.remove_repo("repo2", token)
   server.remove_image("image2", token)

   # have to update the API as it has changed
   api.update()
   d1 = api.find_distro("distro1")
   assert d1 is None
   assert api.find_profile("profile1") is None
   assert api.find_repo("repo1") is None
   assert api.find_image("image1") is None
   assert api.find_system("system1") is None

   for x in api.distros():
      print "DISTRO REMAINING: %s" % x.name

   assert api.find_distro("distro2") is None
   assert api.find_profile("profile2") is None
   assert api.find_repo("repo2") is None
   assert api.find_image("image2") is None
   assert api.find_system("system2") is None

   # FIXME: should not need cleanup as we've done it above 
   _test_remove_objects()

