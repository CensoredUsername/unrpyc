# Copyright (c) 2015-2024 CensoredUsername
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

    def __reduce__(self):
        cls, args, state = super().__reduce__()
        return (set, args, state)


oldset.__name__ = "set"
SPECIAL_CLASSES.append(oldset)


class oldfrozenset(frozenset):
    __module__ = "__builtin__"

    def __reduce__(self):
        cls, args, state = super().__reduce__()
        return (frozenset, args, state)


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
class PyExpr(magic.FakeStrict, str):
    __module__ = "renpy.astsupport"

    def __new__(cls, s, filename, linenumber, py=None, hashcode=None, column=None):
        self = str.__new__(cls, s)
        self.filename = filename
        self.linenumber = linenumber
        self.py = py
        self.hashcode = hashcode
        self.column = None
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
            self.hashcode = None
            self.col_offset = None
        elif len(state) == 5:
            (_, self.source, self.location, self.mode, self.py) = state
            self.hashcode = None
            self.col_offset = None
        elif len(state) == 6:
            (_, self.source, self.location, self.mode, self.py, self.hashcode) = state
            self.col_offset = None
        else:
            (_, self.source, self.location, self.mode, self.py, self.hashcode, self.col_offset) = state
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

# Before ren'py 7.5/8.0 they lived in renpy.python, so for compatibility we keep it here.
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


# as of ren'py 8.4, default properties of many classes are not stored in the pickle anymore.
# so we define prototypes of these classes here, so we don't end up with a soup of hasattr checks.
# rules: unless otherwise stated, int properties default to 0, anything else is None

# ast classes

@SPECIAL_CLASSES.append
class Say(magic.FakeStrict):
    __module__ = "renpy.ast"

    who = None
    with_ = None
    interact = True
    attributes = None
    arguments = None
    temporary_attributes = None
    identifier = None
    explicit_identifier = None


@SPECIAL_CLASSES.append
class Init(magic.FakeStrict):
    __module__ = "renpy.ast"

    priority = 0


@SPECIAL_CLASSES.append
class Label(magic.FakeStrict):
    __module__ = "renpy.ast"

    translation_relevant = True
    parameters = None
    hide = False

    # shenanigans have begotten shenanigans
    @property
    def name(self):
        if "name" in self.__dict__:
            return self.__dict__["name"]
        else:
            return self._name


@SPECIAL_CLASSES.append
class Python(magic.FakeStrict):
    __module__ = "renpy.ast"

    store = "store"
    hide = False


@SPECIAL_CLASSES.append
class EarlyPython(magic.FakeStrict):
    __module__ = "renpy.ast"

    store = "store"
    hide = False


@SPECIAL_CLASSES.append
class Image(magic.FakeStrict):
    __module__ = "renpy.ast"

    code = None
    atl = None


@SPECIAL_CLASSES.append
class Transform(magic.FakeStrict):
    __module__ = "renpy.ast"

    parameters = None
    store = "store"


@SPECIAL_CLASSES.append
class Show(magic.FakeStrict):
    __module__ = "renpy.ast"

    atl = None
    warp = True


@SPECIAL_CLASSES.append
class ShowLayer(magic.FakeStrict):
    __module__ = "renpy.ast"

    atl = None
    warp = True
    layer = "master"


@SPECIAL_CLASSES.append
class Camera(magic.FakeStrict):
    __module__ = "renpy.ast"

    atl = None
    warp = True
    layer = "master"


@SPECIAL_CLASSES.append
class Scene(magic.FakeStrict):
    __module__ = "renpy.ast"

    atl = None
    warp = True
    layer = "master"


@SPECIAL_CLASSES.append
class Hide(magic.FakeStrict):
    __module__ = "renpy.ast"

    warp = True


@SPECIAL_CLASSES.append
class With(magic.FakeStrict):
    __module__ = "renpy.ast"

    paired = None


@SPECIAL_CLASSES.append
class Call(magic.FakeStrict):
    __module__ = "renpy.ast"

    arguments = None
    expression = False
    global_label = ""


@SPECIAL_CLASSES.append
class Return(magic.FakeStrict):
    __module__ = "renpy.ast"

    expression = None


@SPECIAL_CLASSES.append
class Menu(magic.FakeStrict):
    __module__ = "renpy.ast"

    translation_relevant = True
    set = None
    with_ = None
    has_caption = False
    arguments = None
    item_arguments = None
    rollback = "force"


@SPECIAL_CLASSES.append
class Jump(magic.FakeStrict):
    __module__ = "renpy.ast"

    expression = False
    global_label = ""


@SPECIAL_CLASSES.append
class UserStatement(magic.FakeStrict):
    __module__ = "renpy.ast"

    block = []
    translatable = False
    code_block = None
    translation_relevant = False
    rollback = "normal"
    subparses = []
    init_priority = 0
    atl = None


@SPECIAL_CLASSES.append
class Define(magic.FakeStrict):
    __module__ = "renpy.ast"

    store = "store"
    operator = "="
    index = None


@SPECIAL_CLASSES.append
class Default(magic.FakeStrict):
    __module__ = "renpy.ast"

    store = "store"


@SPECIAL_CLASSES.append
class Style(magic.FakeStrict):
    __module__ = "renpy.ast"

    parent = None
    clear = False
    take = None
    variant = None


@SPECIAL_CLASSES.append
class Translate(magic.FakeStrict):
    __module__ = "renpy.ast"

    rollback = "never"
    translation_relevant = True
    alternate = None
    language = None
    after = None


@SPECIAL_CLASSES.append
class TranslateSay(magic.FakeStrict):
    __module__ = "renpy.ast"

    translatable = True
    translation_relevant = True
    alternate = None
    language = None

    # inherited from Say
    who = None
    with_ = None
    interact = True
    attributes = None
    arguments = None
    temporary_attributes = None
    identifier = None
    explicit_identifier = None


@SPECIAL_CLASSES.append
class EndTranslate(magic.FakeStrict):
    __module__ = "renpy.ast"

    rollback = "never"


@SPECIAL_CLASSES.append
class TranslateString(magic.FakeStrict):
    __module__ = "renpy.ast"

    translation_relevant = True



@SPECIAL_CLASSES.append
class TranslatePython(magic.FakeStrict):
    __module__ = "renpy.ast"

    translation_relevant = True



@SPECIAL_CLASSES.append
class TranslateBlock(magic.FakeStrict):
    __module__ = "renpy.ast"

    translation_relevant = True


@SPECIAL_CLASSES.append
class TranslateEarlyBlock(magic.FakeStrict):
    __module__ = "renpy.ast"

    translation_relevant = True


# end of the declarative data section

CLASS_FACTORY = magic.FakeClassFactory(SPECIAL_CLASSES, magic.FakeStrict)


def pickle_safe_loads(buffer: bytes):
    return magic.safe_loads(
        buffer, CLASS_FACTORY, {"collections"}, encoding="ASCII", errors="strict")


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
