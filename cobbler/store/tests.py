import unittest
import doctest
import sys
import os
import __init__ as store
import config

#Because we want everything to use the testing handlers...
config.default_source = 'test'

#TODO: 
#       Write a basic test for each provided field type
#       Test inheritance on all provided inheriting Items

class TestItem(unittest.TestCase):
#    def test_find(self):
#        d = store.new('Distro')
#        #d.name = 'Hello'
#        if not d.validate():
#            for i in d._errors:
#                print i
#        store.set(d)
#        print store.find({'name':'Hello'})
    def tearDown(self):
        store.handlers.test_flush()
    
    def test_distro_store(self):
        # Make our fake files so that the LocalFileFields will be happy
        fake_initrd = '/tmp/temp_initrd.tmp'
        fake_kernel = '/tmp/temp_kernel.tmp'
        f = open(fake_initrd, 'w')
        f.write('')
        f.close()
        f = open(fake_kernel, 'w')
        f.write('')
        f.close()
        
        d = store.new('Distro')
        self.assertFalse(d.validate())
        ERRORS = dict(d._errors)
        self.assertEqual(len(d._errors), 3)
        self.assertTrue('kernel' in ERRORS)
        self.assertTrue('initrd' in ERRORS)
        self.assertTrue('name' in ERRORS)
        d.name.set('Test_Distro')
        d.kernel.set(fake_kernel)
        d.initrd.set(fake_initrd)
        self.assertTrue(d.validate())
        self.assertTrue(store.set(d))
        self.assertEqual(store.find({'name':'Test_Distro', '_type':'Distro'}),
             [(d._uid.get(),)])
        self.assertEqual(store.get(d._uid.get()).deflate(), d.deflate())
    
    def test_image_store(self):
        i = store.new('Image')
        self.assertFalse(i.validate())
        ERRORS = dict(i._errors)
        self.assertEqual(len(i._errors), 1)
        self.assertTrue('name' in ERRORS)
        i.name.set('Test_Image')
        self.assertTrue(i.validate())
        self.assertTrue(store.set(i))
        self.assertEqual(store.find({'name':'Test_Image', '_type':'Image'}),
             [(i._uid.get(),)])
        self.assertEqual(store.get(i._uid.get()).deflate(), i.deflate())
    
    def test_profile_store(self):
        self.test_distro_store()
        i = store.new('Profile')
        self.assertFalse(i.validate())
        ERRORS = dict(i._errors)
        self.assertEqual(len(i._errors), 2)
        self.assertTrue('name' in ERRORS)
        self.assertTrue('distro' in ERRORS)
        i.name.set('Test_Profile')
        i.distro.set('Test_Distro')
        self.assertTrue(i.validate())
        self.assertTrue(store.set(i))
        self.assertEqual(store.find({'name':'Test_Profile', '_type':'Profile'}),
             [(i._uid.get(),)])
        self.assertEqual(store.get(i._uid.get()).deflate(), i.deflate())
    
    def test_system_store(self):
        self.test_profile_store()
        i = store.new('System')
        self.assertFalse(i.validate())
        ERRORS = dict(i._errors)
        self.assertEqual(len(i._errors), 2)
        self.assertTrue('Require One of: profile, image' in ERRORS)
        self.assertTrue('name' in ERRORS)
        i.name.set('Test_System')
        i.profile.set('Test_Profile')
        self.assertTrue(i.validate())
        self.assertTrue(store.set(i))
        self.assertEqual(store.find({'name':'Test_System', '_type':'System'}),
             [(i._uid.get(),)])
        self.assertEqual(store.get(i._uid.get()).deflate(), i.deflate())

    def test_repo_store(self):
        i = store.new('Repo')
        self.assertFalse(i.validate())
        ERRORS = dict(i._errors)
        self.assertEqual(len(i._errors), 1)
        self.assertTrue('name' in ERRORS)
        i.name.set('Test_Repo')
        self.assertTrue(i.validate())
        self.assertTrue(store.set(i))
        self.assertEqual(store.find({'name':'Test_Repo', '_type':'Repo'}),
             [(i._uid.get(),)])
        self.assertEqual(store.get(i._uid.get()).deflate(), i.deflate())

class TestFields(unittest.TestCase):
    def tearDown(self):
        store.handlers.test_flush()
    
    def test_str_field(self):
        s = store.objects.StrField()
        self.assertEqual(s.get(), u'')
        s.set('foo')
        self.assertEqual(s.get(), u'foo')
        s.set(134.7)
        self.assertEqual(s.get(), u'134.7')
        s.set(None)
        self.assertEqual(s.get(), u'None')
        
        s = store.objects.StrField(default='boo')
        self.assertEqual(s.get(), u'boo')
        self.assertTrue(s.validate())
        s.set('foo')
        self.assertEqual(s.get(), u'foo')
        self.assertTrue(s.validate())
        s.set(134.7)
        self.assertEqual(s.get(), u'134.7')
        self.assertTrue(s.validate())
        s.set(None)
        self.assertEqual(s.get(), u'None')
        self.assertTrue(s.validate())

    def test_int_field(self):
        i = store.objects.IntField()
        self.assertEqual(i.get(), 0)
        self.assertTrue(i.validate())
        
        i.set(189.2)
        self.assertEqual(i.get(), 189)
        self.assertTrue(i.validate())
        
        self.assertRaises(TypeError, i.set, None)
        self.assertRaises(ValueError, i.set, 'foo')
        
        self.assertEqual(i.get(), 189)
        self.assertTrue(i.validate())

if __name__ == '__main__':
    unittest.main()
