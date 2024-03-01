# This module holds some special classes and shorthand functions for support of renpy compatiblity.
# They're separate so there will be less code duplication, simpler dependencys between files and
# to avoid middle-of-file imports.

from . import magic
magic.fake_package("renpy")
import renpy  # noqa


# these named classes need some special handling for us to be able to reconstruct ren'py ASTs from
# pickles
SPECIAL_CLASSES = [set, frozenset]

@SPECIAL_CLASSES.append
class PyExpr(magic.FakeStrict, unicode):
    __module__ = "renpy.ast"

    def __new__(cls, s, filename, linenumber, py=None):
        self = unicode.__new__(cls, s)
        self.filename = filename
        self.linenumber = linenumber
        self.py = py
        return self

    def __getnewargs__(self):
        if self.py is not None:
            return unicode(self), self.filename, self.linenumber, self.py
        else:
            return unicode(self), self.filename, self.linenumber


@SPECIAL_CLASSES.append
class PyCode(magic.FakeStrict):
    __module__ = "renpy.ast"

    def __setstate__(self, state):
        if len(state) == 4:
            (_, self.source, self.location, self.mode) = state
            self.py = None
        else:
            (_, self.source, self.location, self.mode, self.py) = state
        self.bytecode = None


@SPECIAL_CLASSES.append
class Sentinel(magic.FakeStrict, object):
    __module__ = "renpy.object"

    def __new__(cls, name):
        obj = object.__new__(cls)
        obj.name = name
        return obj


# These used to live in renpy.python. They started appearing in ASTs after ren'py switched from
# putting the unparsed contents of a user statement into the AST to putting the parsed result,
# or when people define custom AST nodes in ren'py files.
@SPECIAL_CLASSES.append
class RevertableList(magic.FakeStrict, list):
    __module__ = "renpy.python"
    def __new__(cls):
        return list.__new__(cls)


@SPECIAL_CLASSES.append
class RevertableDict(magic.FakeStrict, dict):
    __module__ = "renpy.python"
    def __new__(cls):
        return dict.__new__(cls)


@SPECIAL_CLASSES.append
class RevertableSet(magic.FakeStrict, set):
    __module__ = "renpy.python"
    def __new__(cls):
        return set.__new__(cls)

    def __setstate__(self, state):
        if isinstance(state, tuple):
            self.update(state[0].keys())
        else:
            self.update(state)


# But since 7.5 they live in renpy.revertable, so we have both
@SPECIAL_CLASSES.append
class RevertableList(magic.FakeStrict, list):
    __module__ = "renpy.revertable"
    def __new__(cls):
        return list.__new__(cls)


@SPECIAL_CLASSES.append
class RevertableDict(magic.FakeStrict, dict):
    __module__ = "renpy.revertable"
    def __new__(cls):
        return dict.__new__(cls)


@SPECIAL_CLASSES.append
class RevertableSet(magic.FakeStrict, set):
    __module__ = "renpy.revertable"
    def __new__(cls):
        return set.__new__(cls)

    def __setstate__(self, state):
        if isinstance(state, tuple):
            self.update(state[0].keys())
        else:
            self.update(state)


CLASS_FACTORY = magic.FakeClassFactory(SPECIAL_CLASSES, magic.FakeStrict)


def pickle_safe_loads(buffer):
    return magic.safe_loads(buffer, CLASS_FACTORY, {"_ast", "collections"})


def pickle_safe_dumps(buffer):
    return magic.safe_dumps(buffer)


def pickle_safe_dump(buffer, outfile):
    return magic.safe_dump(buffer, outfile)


def pickle_loads(buffer):
    return magic.loads(buffer, CLASS_FACTORY)
