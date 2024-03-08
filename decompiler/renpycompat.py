# This module holds some special classes and shorthand functions for support of renpy compatiblity.
# They're separate so there will be less code duplication, simpler dependencies between files and
# to avoid middle-of-file imports.

from . import magic
magic.fake_package("renpy")
import renpy  # noqa

import pickletools


# these named classes need some special handling for us to be able to reconstruct ren'py ASTs from
# pickles
SPECIAL_CLASSES = [set, frozenset]


# ren'py _annoyingly_ enables fix_imports even in ren'py v8 and still defaults to pickle protocol 2.
# so set/frozenset get mapped to the wrong location (__builtins__ instead of builtins)
# we don't want to enable that option as we want control over what the pickler is allowed to
# unpickle
# so here we define some proxies
class oldset(set):
    __module__ = "__builtin__"


oldset.__name__ = "set"
SPECIAL_CLASSES.append(oldset)


class oldfrozenset(frozenset):
    __module__ = "__builtin__"


oldfrozenset.__name__ = "frozenset"
SPECIAL_CLASSES.append(oldfrozenset)


@SPECIAL_CLASSES.append
class PyExpr(magic.FakeStrict, str):
    __module__ = "renpy.ast"

    def __new__(cls, s, filename, linenumber, py=None):
        self = str.__new__(cls, s)
        self.filename = filename
        self.linenumber = linenumber
        self.py = py
        return self

    def __getnewargs__(self):
        if self.py is not None:
            return str(self), self.filename, self.linenumber, self.py
        else:
            return str(self), self.filename, self.linenumber


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
class Sentinel(magic.FakeStrict):
    __module__ = "renpy.object"

    def __new__(cls, name):
        obj = object.__new__(cls)
        obj.name = name
        return obj


# These appear in the parsed contents of user statements.
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


def pickle_safe_loads(buffer: bytes):
    return magic.safe_loads(buffer, CLASS_FACTORY, {"collections",}, encoding="ASCII", errors="strict")


def pickle_safe_dumps(buffer: bytes):
    return magic.safe_dumps(buffer)


# if type hints: which one would be output file? bytesIO or bytes?
def pickle_safe_dump(buffer: bytes, outfile):
    return magic.safe_dump(buffer, outfile)


def pickle_loads(buffer: bytes):
    return magic.loads(buffer, CLASS_FACTORY)


def pickle_detect_python2(buffer: bytes):
    # When objects get pickled in protocol 2, python 2 will
    # normally emit BINSTRING/SHORT_BINSTRING opcodes for any attribute
    # names / binary strings.
    # protocol 2 in python 3 however, will never use BINSTRING/SHORT_BINSTRING
    # so presence of these opcodes is a tell that this file was not from renpy 8
    # even when recording a bytestring in python 3, it will not use BINSTRING/SHORT_BINSTRING
    # instead choosing to encode it into a BINUNICODE object
    #
    # caveat:
    # if a file uses `from __future__ import unicode_literals`
    # combined with __slots__ that are entered as plain "strings"
    # then attributes will use BINUNICODE instead (like py3)
    # Most ren'py AST classes do use __slots__ so that's a bit annoying

    for opcode, arg, pos in pickletools.genops(buffer):
        if opcode.code == "\x80":
            # from what I know ren'py for now always uses protocol 2,
            # but it might've been different in the past, and change in the future
            if arg < 2:
                return True

            elif arg > 2:
                return False

        if opcode.code in "TU":
            return True

    return False
