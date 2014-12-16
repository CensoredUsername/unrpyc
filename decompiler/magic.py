# Copyright (c) 2014 CensoredUsername
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# This module provides tools for safely analyizing pickle files programmatically
# and constructing special pickles

import sys
import types
import pickle
from cStringIO import StringIO

# the main API

def load(file, class_factory=None):
    return FakeUnpickler(file, class_factory).load()

def loads(string, class_factory=None):
    return FakeUnpickler(StringIO(string), class_factory).load()

def safe_load(file, class_factory=None, safe_modules=()):
    return SafeUnpickler(file, class_factory, safe_modules).load()

def safe_loads(string, class_factory=None, safe_modules=()):
    return SafeUnpickler(StringIO(string), class_factory, safe_modules).load()

def fake_package(name):
    # Mount a fake package tree. This means that any request to import
    # From a submodule of this package will be served a fake package.
    # Next to this any real module which would be somewhere
    # within this package will be ignored in favour of a fake one
    if name in sys.modules and isinstance(sys.modules[name], FakePackage):
        return sys.modules[name]
    else:
        loader = FakePackageLoader(name)
        sys.meta_path.insert(0, loader)
        return __import__(name)

def remove_fake_package(name):
    # Remove a mounted package tree and all fake packages it has generated

    # Get the package entry via its entry in sys.modules
    package = sys.modules.get(name, None)
    if package is None:
        raise Exception("No fake package with the name {0} found".format(name))

    if not isinstance(package, FakePackage):
        raise Exception("The module {0} is not a fake package".format(name))

    # Attempt to remove the loader from sys.meta_path

    loaders = [i for i in sys.meta_path if isinstance(i, FakePackageLoader) and i.root == name]
    for loader in loaders:
        sys.meta_path.remove(loader)

    # Remove all module and submodule entries from sys.modules
    package._remove()

    # It is impossible to kill references to the modules, but all traces
    # of it have been removed from the import machinery and the submodule
    # tree structure has been broken up. 

# Fake class implementation

class FakeClassType(type):
    """
    As the metaclass for FakeClasses this class defines a set of equality methods.

    By default classes equality commparison is limited by id(self) == id(other)
    For fakeclasses however it's necessary that they compare positively with
    Other FakeClasses, actual classes with the same __module__ and __name__
    #nd modules/FakeModules with a matching __name__.
    """

    def __eq__(self, other):
        if not hasattr(other, "__name__"):
            return False
        if hasattr(other, "__module__"):
            return self.__module__ == other.__module__ and self.__name__ == other.__name__
        else:
            return self.__module__ + "." + self.__name__ == other.__name__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__module__ + "." + self.__name__)

    def __instancecheck__(self, instance):
        return self.__subclasscheck__(instance.__class__)

    def __subclasscheck__(self, subclass):
        return (self.__eq__(subclass) or
                (bool(subclass.__bases__) and
                 any(self.__subclasscheck__(base) for base in subclass.__bases__)))


# Default FakeClass instance methods

def _strict_new(cls, *args):
    self = cls.__bases__[0].__new__(cls)
    if args:
        raise ValueError("{0} was instantiated with unexpected arguments {1}".format(cls, args))
    return self

def _warning_new(cls, *args):
    self = cls.__bases__[0].__new__(cls)
    if args:
        print "{0} was instantiated with unexpected arguments {1}".format(cls, args)
        self._new_args = args
    return self

def _ignore_new(cls, *args):
    return cls.__bases__[0].__new__(cls)

def _strict_setstate(self, state):
    slotstate = None

    if (isinstance(state, tuple) and len(state) == 2 and 
        (state[0] is None or isinstance(state[0], dict)) and
        (state[1] is None or isinstance(state[1], dict))):
        state, slotstate = state
    
    if state:
        # Don't have to check for slotstate here since it's either None or a dict
        if not isinstance(state, dict):
            raise ValueError("{0}.__setstate__() got unexpected arguments {1}".format(self.__class__, state))
        else:
            self.__dict__.update(state)
        
    if slotstate:
        self.__dict__.update(slotstate)

def _warning_setstate(self, state):
    slotstate = None

    if (isinstance(state, tuple) and len(state) == 2 and 
        (state[0] is None or isinstance(state[0], dict)) and
        (state[1] is None or isinstance(state[1], dict))):
        state, slotstate = state
    
    if state:
        # Don't have to check for slotstate here since it's either None or a dict
        if not isinstance(state, dict):
            print "{0}.__setstate__() got unexpected arguments {1}".format(self.__class__, state)
            self._setstate_args = state 
        else:
            self.__dict__.update(state)
        
    if slotstate:
        self.__dict__.update(slotstate)

def _ignore_setstate(self, state):
    slotstate = None

    if (isinstance(state, tuple) and len(state) == 2 and 
        (state[0] is None or isinstance(state[0], dict)) and
        (state[1] is None or isinstance(state[1], dict))):
        state, slotstate = state
    
    if state and isinstance(state, dict):
        self.__dict__.update(state)
        
    if slotstate:
        self.__dict__.update(slotstate)

class FakeClassFactory(object):
    """
    A factory which instantiates FakeClasses which inherit from given bases 
    with given methods and attributes
    """

    def __init__(self, special_cases, errors='strict', fake_metaclass=FakeClassType, default_bases=(object,)):
        """
        `special_cases` should be a dict with a mapping of name to a tuple of a tuple of 
        classes the special case should inherit from and a dict of attribute name to attribute
        value. 

        e.g. special_cases = {"foo.bar": ((object, ), {"__str__": lambda self: "baz"})}

        To mimic another class would require the equivalent of this:
        special_cases = {class.__module__ + "." + class.__name__: (class.__bases__, class.__dict__)}

        `errors` determines how errors around object instatiation from the pickle will be 
        handled by the default __new__ and __setstate__ methods used by FakeClasses.

        There are three possible cases. 'strict', the default, will raise a ValueError
        when the default methods do not know how to handle the given arguments. 'warning'
        will print a warning and assign the given arguments to temporary variables. 'ignore'
        will simply ignore the arguments.

        `fake_meta_class` is the metaclass used to create the FakeClass. It should inherit from type
        """
        self.special_cases = special_cases
        self.metaclass = fake_metaclass
        self.default_bases = default_bases

        self.class_cache = {}

        if errors == 'strict':
            self.default_attributes = {"__new__": _strict_new, "__setstate__": _strict_setstate}
        elif errors == 'warning':
            self.default_attributes = {"__new__": _warning_new, "__setstate__": _warning_setstate}
        elif errors == 'ignore':
            self.default_attributes = {"__new__": _ignore_new, "__setstate__": _ignore_setstate}
        else:
            raise ValueError("Unknown error handling directive '{0}' given".format(errors))

    def __call__(self, name, module):
        """
        Constructs a class with the name `name` and __module__ set to module
        with the bases, attributes and metaclass set to the parameters given
        to the factory
        """
        # Check if we've got this class cached
        klass = self.class_cache.get((module, name), None)
        if klass is not None:
            return klass

        special = self.special_cases.get(module + "." + name, None)

        attributes = self.default_attributes.copy()
        if special:
            bases, new_attributes = special
            attributes.update(new_attributes)
        else:
            bases = self.default_bases

        klass = self.metaclass(name, bases, attributes)
        # By default __module__ gets set to the global __name__
        klass.__module__ = module
        self.class_cache[(module, name)] = klass
        return klass

# Fake module implementation

class FakeModule(types.ModuleType):
    """
    A dynamically created fake module object. This object
    will compare equal to anything with the same __name__ (modules)
    or the same __module__ + "." + __name__ (classes) so it can
    be compared with fake classes, allowing you to code as if the classes
    Already existed before they were created during unpickling
    """
    def __init__(self, name):
        super(FakeModule, self).__init__(name)
        sys.modules[name] = self

    def __repr__(self):
        return "<module '{0}' (fake)>".format(self.__name__)

    def __str__(self):
        return self.__repr__()

    def __setattr__(self, name, value):
        # If a fakemodule is removed we need to remove its entry from sys.modules
        if name in self.__dict__ and isinstance(self.__dict__[name], FakeModule) and not isinstance(value, FakeModule):
            self.__dict__[name]._remove()
        self.__dict__[name] = value

    def __delattr__(self, name):
        if isinstance(self.__dict__[name], FakeModule):
            self.__dict__[name]._remove()
        del self.__dict__[name]

    def _remove(self):
        for i in self.__dict__.keys()[:]:
            if isinstance(self.__dict__[i], FakeModule):
                self.__dict__[i]._remove()
                del self.__dict__[i]
        del sys.modules[self.__name__]

    def __eq__(self, other):
        if not hasattr(other, "__name__"):
            return False
        othername = other.__name__
        if hasattr(other, "__module__"):
            othername = other.__module__ + "." + other.__name__

        return self.__name__ == othername

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__name__)

    def __instancecheck__(self, instance):
        return self.__subclasscheck__(instance.__class__)

    def __subclasscheck__(self, subclass):
        return (self.__eq__(subclass) or
                (bool(subclass.__bases__) and
                 any(self.__subclasscheck__(base) for base in subclass.__bases__)))

class FakePackage(FakeModule):
    """
    A FakeModule which presents FakePackages at any attribute, allowing
    you to request any object in this module or any submodule.
    """
    __path__ = []

    def __getattr__(self, name):
        modname = self.__name__ + "." + name
        mod = sys.modules.get(modname, None)
        if mod is None:
            try: 
                __import__(modname)
            except:
                mod = FakePackage(modname)
            else:
                mod = sys.modules[modname]
        return mod

class FakePackageLoader(object):
    """
    A loader for FakePackage modules. This is mounted at a certain root, 
    and from that point on any module imported which is that root or
    would be a submodule from that root will be a FakePackage
    """
    def __init__(self, root):
        self.root = root

    def find_module(self, fullname, path=None):
        if fullname == self.root or fullname.startswith(self.root + "."):
            return self
        else:
            return None

    def load_module(self, fullname):
        return FakePackage(fullname)

# Fake unpickler implementation

class FakeUnpickler(pickle.Unpickler):
    """
    This unpickler behaves like a normal unpickler as long as it can import
    the modules and classes that are requested in the pickle. If however it 
    encounters an unknown module or class it will insert FakeModules and 
    FakeClasses where necessary.

    This means that this pickle is as close to the original data as possible,
    but it still suffers from the dangers of unpickling untrusted data.
    """
    def __init__(self, file, class_factory=None):
        pickle.Unpickler.__init__(self, file)
        self.class_factory = class_factory or FakeClassFactory({}, 'strict')

    def find_class(self, module, name):
        mod = sys.modules.get(module, None)
        if mod is None:
            try:
                __import__(module)
            except:
                mod = FakeModule(module)
                print "Created module {0}".format(str(mod))
            else:
                mod = sys.modules[module]

        klass = getattr(mod, name, None)
        if klass is None or isinstance(klass, FakeModule):
            klass = self.class_factory(name, module)
            setattr(mod, name, klass)

        return klass

class SafeUnpickler(FakeUnpickler):
    """
    This unpickler does not attempt to import any module or class definitions unless
    they're marked as safe by entering their names as a set of strings into `safe_modules`.
    It will attempt to unpickle the given file as close to the original datastructure
    as possible, replacing any pickled objects by FakeClasses.

    This means that this unpickler does not suffer from the unpickling untrusted
    data vulnerabilities and that it can be used to inspect pickles if they
    contain such vulnerabilities.

    It should be noted though that if a module is marked as safe but an attribute
    in that module is not found, it will not insert a FakeClass there, instead it will
    raise an UnpicklingError
    """

    def __init__(self, file, class_factory=None, safe_modules=()):
        FakeUnpickler.__init__(self, file, class_factory)
        # A set of modules which are safe to load
        self.safe_modules = set(safe_modules)

    def find_class(self, module, name):
        if module in self.safe_modules:
            __import__(module)
            mod = sys.modules[module]
            klass = getattr(mod, name)
            return klass

        else:
            return self.class_factory(name, module)
