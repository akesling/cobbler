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

class TestStore(unittest.TestCase):
    def setUp(self):
        self.tearDown()
    
    def tearDown(self):
        store.handlers.test_flush()

    def test_undefined_type(self):
        self.assertRaises(TypeNotFound, store.new, 'foo')
    
    def test_invalid_item(self):
        self.assertRaises(ItemNotFound, store.get, 'foo')

    def test_find_slicing(self):
        class CheeseShop(store.objects.BaseItem):
            employees = store.objects.ListField(required=True)
            cheeses = store.objects.ListField(required=True)            
         
        uids = []
        employees = ('Larry', 'Moe', 'Curly')
        cheeses = ('Limburger', 'Gruyer', 'Camembert')
        for e,c in zip(employees, cheeses):
            i = store.new('CheeseShop')
            i.employees.set([e])
            i.cheeses.set([c])
            self.assertTrue(store.set(i))
            uids.append(i._uid.get())
        for e,c in zip(employees[::-1], cheeses[::-1]):
            i = store.new('CheeseShop')
            i.employees.set([e])
            i.cheeses.set([c])
            self.assertTrue(store.set(i))
            uids.append(i._uid.get())
        
        cheeseshops = store.find({'_type':'CheeseShop'}, ['employees', 'cheeses', '_uid'])
        self.assertEqual(len(cheeseshops), 6)
        for shop in cheeseshops:
            self.assertEqual(len(shop), 3)
            self.assertTrue(shop[1][0] in employees)
            self.assertTrue(shop[2][0] in cheeses)
    
    def test_invalid_handler_source(self):
        self.assertRaises(InvalidSource, store.new, 'foo', source='bar')
        self.assertRaises(InvalidSource, store.new, 'Distro', source='bar')
        
        self.assertRaises(InvalidSource, store.find, {'name':'Test_Distro', '_type':'Distro'}, source='bar')
        self.assertRaises(InvalidSource, store.find, {'name':'foo', '_type':'baz'}, source='bar')
        
        i = store.new('Repo')
        i.name.set('Test_Repo')
        store.set(i)
        uid = store.find({'name':'Test_Repo', '_type':'Repo'})[0]
        self.assertRaises(InvalidSource, store.get, uid, source='bar')
        
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

    def test_signature(self):
        class Pizza(store.objects.BaseItem):
            _requirements = []
            
            toppings = store.objects.ListField()
            sauce = store.objects.ChoiceField(
                default='Tomato',
                choices=('None', 'Tomato', 'Basil Pesto', 'White'))
            cheese = store.objects.BoolField(default=True)
            
            _requirements.append(store.objects.require_n_of(
                'toppings', 'sauce', 'cheese', grouping=2)
            )

        i = store.new('Pizza')
        self.assertEqual(i.get_signature(),
                        (('_mtime',
                          ((u'class', u'TimeField'),
                           (u'default', u'None'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'True'),
                           (u'editable', u'False'),
                           (u'tags', u'[]'))),
                         ('_type',
                          ((u'class', u'StrField'),
                           (u'default', u'Pizza'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'False'),
                           (u'editable', u'False'),
                           (u'tags', u'[]'))),
                         ('_ctime',
                          ((u'class', u'TimeField'),
                           (u'default', u'None'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'True'),
                           (u'editable', u'False'),
                           (u'tags', u'[]'))),
                         ('_uid',
                          ((u'class', u'StrField'),
                           (u'default', u'None'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'True'),
                           (u'editable', u'False'),
                           (u'tags', u'[]'))),
                         ('cheese',
                          ((u'class', u'BoolField'),
                           (u'default', u'True'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'False'),
                           (u'editable', u'True'),
                           (u'tags', u'[]'))),
                         ('_type',
                          ((u'class', u'StrField'),
                           (u'default', u'Pizza'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'False'),
                           (u'editable', u'False'),
                           (u'tags', u'[]'))),
                         ('toppings',
                          ((u'class', u'ListField'),
                           (u'default', u'[]'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'False'),
                           (u'editable', u'True'),
                           (u'tags', u'[]'))),
                         ('sauce',
                          ((u'class', u'ChoiceField'),
                           (u'default', u'Tomato'),
                           (u'visible', u'True'),
                           (u'inherit', u'False'),
                           (u'required', u'False'),
                           (u'editable', u'True'),
                           (u'tags', u'[]')))))
        
    
    def test_inter_item_inheritance(self):
        self.test_distro_store()
        
        parent = store.new('Profile')
        parent.name.set('parent')
        parent.distro.set('Test_Distro')
        self.assertTrue(store.set(parent))
        
        #print 'distro', parent.distro.get_uid()
        #print 'profile', parent._uid.get()
        
        child = store.new('Profile')
        child.name.set('child')
        child.profile.set('parent')
        child.validate()
        print child._errors
        self.asserTrue(False)
        self.assertTrue(store.set(child))
    
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

    def test_set(self):
        # Standard case
        f = store.objects.IntField()
        self.assertFalse(f.is_set())
        f.set(1)
        self.assertTrue(f.is_set())
        
        # With simple coercion
        f = store.objects.IntField()
        f.set('1')
        self.assertTrue(f.is_set())
        
        # Does the inheritance clause work?
        f = store.objects.IntField(inherit=True)
        f.set('<<inherit>>')
        self.assertTrue(f.is_set())
    
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
    
    def test_datetime_field(self):
        # At the moment, this was just added for test coverage... 
        # XXX: NEED TO TEST MORE... like whether this properly serializes
        #       (last time I checked, it didn't).
        f = store.objects.DateTimeField()
        
    def test_item_field(self):
        i = store.new('Repo')
        i.name.set('Test_Repo')
        store.set(i)
        
        f = store.objects.ItemField('Repo')
        self.assertFalse(f.get_uid())
        self.assertTrue(f.validate())
        f.set('Test_Repo')
        self.assertTrue(f.validate())
        self.assertEqual(f.get_uid(), i._uid.get())
        
        f = store.objects.ItemField('Repo', required=True)
        
        # Since we aren't actually accessing this field correctly (it isn't 
        # properly bound to an Item), we need to do a couple things to make
        # this more kosher.
        f._name = 'foo'
        
        self.assertFalse(f.get_uid())
        self.assertRaises(InvalidItem, f.validate)
        f.set('Test_Repo')
        self.assertTrue(f.validate())
        self.assertEqual(f.get_uid(), i._uid.get())
        

class TestRequirements(unittest.TestCase):
    def tearDown(self):
        store.handlers.test_flush()
    
    def test_laziness(self):
        foo = [True, False, False]
        class TestReqMagic(store.objects.BaseItem):
            _requirements = []
            _requirements.append(store.objects.GroupRequirement(
                        ( lambda:foo[0], lambda:foo[1], lambda:foo[2] )))
        i = store.new('TestReqMagic')
        self.assertFalse(i.validate())
        

if __name__ == '__main__':
    unittest.main()
