import unittest
import doctest
import sys
import os
import __init__ as store
import config
from store_exceptions import *
import simplejson

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
    def setUp(self):
        self.tearDown()
    
    def tearDown(self):
        store.handlers.test_flush()
    
    def test_undefined_type(self):
        self.assertRaises(TypeNotFound, store.new, 'foo')
    
    def test_invalid_item(self):
        self.assertRaises(ItemNotFound, store.get, 'foo')
    
    def test_invalid_handler_source(self):
        self.assertRaises(InvalidSource, store.new, 'foo', source='bar')
        self.assertRaises(InvalidSource, store.new, 'Distro', source='bar')
        
        self.assertRaises(InvalidSource, store.find, {'name':'Test_Distro', '_type':'Distro'}, source='bar')
        self.assertRaises(InvalidSource, store.find, {'name':'foo', '_type':'baz'}, source='bar')
        
        self.test_distro_store()
        uid = store.find({'name':'Test_Distro', '_type':'Distro'})[0]
        self.assertRaises(InvalidSource, store.get, uid, source='bar')
        
    def test_deflate(self):
        self.test_distro_store()
        uid = store.find({'name':'Test_Distro', '_type':'Distro'})[0][0]
        d = store.get(uid)
        #Just make sure everything is the same...
        self.assertEqual(d.deflate(), 
                            {
                            '_ctime': (d._ctime.get(), 1),
                            '_mtime': (d._mtime.get(), 1),
                            '_type': (u'Distro', 0),
                            '_uid': (d._uid.get(), 1),
                            'architecture': (u'i386', 0),
                            'breed': (u'redhat', 0),
                            'comment': (u'', 0),
                            'depth': (0, 0),
                            'distro': (u'', 0),
                            'initrd': (u'/tmp/temp_initrd.tmp', 1),
                            'kernel': (u'/tmp/temp_kernel.tmp', 1),
                            'kernel_options': ({}, 0),
                            'kernel_options_post': ({}, 0),
                            'kickstart_metadata': ({}, 0),
                            'mgmt_classes': ([], 0),
                            'mgmt_parameters': ('<<inherit>>', 0),
                            'name': (u'Test_Distro', 1),
                            'os_version': (u'generic26', 0),
                            'owners': ([], 0),
                            'red_hat_management_key': ('<<inherit>>', 0),
                            'red_hat_management_server': ('<<inherit>>', 0),
                            'source_repos': ([], 0),
                            'template_files': ({}, 0),
                            'template_remote_kickstarts': (False, 0),
                            'tree_build_time': (u'', 0)
                            }
                        )
        self.assertEqual(unicode(d.deflate()), unicode(d))
        self.assertEqual(str(d), unicode(d))
    
    def test_inflate(self):
        for item_type in store.get_types():
            item = store.new(item_type)
            if hasattr(item, 'name'):
                item.name.set('foo')
            blank_item = store.new(item_type)
            blank_item.inflate(item.deflate())
            self.assertEqual(item.deflate(), blank_item.deflate())
            blank_item = store.new(item_type)
            blank_item.inflate(simplejson.loads(
                                            simplejson.dumps(
                                                item.deflate())))
            self.assertEqual(item.deflate(), blank_item.deflate())
    
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
        self.assertFalse(store.set(d))
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
        self.assertFalse(store.set(i))
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
        self.assertFalse(store.set(i))
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
        self.assertFalse(store.set(i))
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
        self.assertFalse(store.set(i))
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
        self.assertEqual(unicode(s), u'')
        self.assertEqual(str(s), u'')
        s.set('foo')
        self.assertEqual(s.get(), u'foo')
        self.assertEqual(unicode(s), u'foo')
        self.assertEqual(str(s), u'foo')
        s.set(134.7)
        self.assertEqual(s.get(), u'134.7')
        self.assertEqual(unicode(s), u'134.7')
        self.assertEqual(str(s), u'134.7')
        s.set(None)
        self.assertEqual(s.get(), u'None')
        self.assertEqual(unicode(s), u'None')
        self.assertEqual(str(s), u'None')
        
        s = store.objects.StrField(default='boo')
        self.assertEqual(s.get(), u'boo')
        self.assertEqual(unicode(s), u'boo')
        self.assertEqual(str(s), u'boo')
        self.assertTrue(s.validate())
        s.set('foo')
        self.assertEqual(s.get(), u'foo')
        self.assertEqual(unicode(s), u'foo')
        self.assertEqual(str(s), u'foo')
        self.assertTrue(s.validate())
        s.set(134.7)
        self.assertEqual(s.get(), u'134.7')
        self.assertEqual(unicode(s), u'134.7')
        self.assertEqual(str(s), u'134.7')
        self.assertTrue(s.validate())
        s.set(None)
        self.assertEqual(s.get(), u'None')
        self.assertEqual(unicode(s), u'None')
        self.assertEqual(str(s), u'None')
        self.assertTrue(s.validate())

        self.assertEqual(s.get_signature(), ((u'class', u'StrField'),
                                             (u'default', u'boo'),
                                             (u'visible', u'True'),
                                             (u'inherit', u'False'),
                                             (u'required', u'False'),
                                             (u'editable', u'True'),
                                             (u'tags', u'[]'))
                                    )

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
        
        self.assertEqual(i.get_signature(), ((u'class', u'IntField'),
                                             (u'default', u'0'),
                                             (u'visible', u'True'),
                                             (u'inherit', u'False'),
                                             (u'required', u'False'),
                                             (u'editable', u'True'),
                                             (u'tags', u'[]'))
                            )
    
#    def test_datetime_field(self):
#        f = store.objects.DateTimeField()
        

if __name__ == '__main__':
    unittest.main()
