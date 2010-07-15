import __init__ as store
d = store.new('Distro')
#d.name = 'Hello'
if not d.validate():
    for i in d._errors:
        print i
store.set(d)
print store.find({'name':'Hello'})
