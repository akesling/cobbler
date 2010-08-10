import unittest
import sys
import os
sys.path.insert(0, os.path.abspath('..'))
import store

#Because we want everything to use the testing handlers...
store.default_source = 'test'

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
        d.name.set('Hello')
        d.kernel.set(fake_kernel)
        d.initrd.set(fake_initrd)
        self.assertTrue(d.validate())
        self.assertTrue(store.set(d))
        self.assertEqual(store.find({'name':'Hello', '_type':'Distro'}),
             [(d._uid.get(),)])
        self.assertEqual(store.get(d._uid.get()).deflate(), d.deflate())
    
    def test_image_store(self):
        i = store.new('Image')
        self.assertFalse(i.validate())
        ERRORS = dict(i._errors)
        self.assertEqual(len(i._errors), 1)
        self.assertTrue('name' in ERRORS)
        i.name.set('Hello')
        self.assertTrue(i.validate())
        self.assertTrue(store.set(i))
        self.assertEqual(store.find({'name':'Hello', '_type':'Image'}),
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
        i.name.set('Hello')
        i.distro.set('Hello')
        self.assertTrue(i.validate())
        self.assertTrue(store.set(i))
        self.assertEqual(store.find({'name':'Hello', '_type':'Profile'}),
             [(i._uid.get(),)])
        self.assertEqual(store.get(i._uid.get()).deflate(), i.deflate())

class TestFields(unittest.TestCase):
    def test_str_field(self):
        pass
        

if __name__ == '__main__':
    unittest.main()
