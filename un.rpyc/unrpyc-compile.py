# Copyright (c) 2012 Yuri K. Schlesner
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

import os
import os.path as path
import codecs
import traceback
import struct

import decompiler
import magic

# special new and setstate methods for special classes

class PyExpr(magic.FakeStrict, unicode):
    __module__ = "renpy.ast"
    def __new__(cls, s, filename, linenumber):
        self = unicode.__new__(cls, s)
        self.filename = filename
        self.linenumber = linenumber
        return self

class PyCode(magic.FakeStrict):
    __module__ = "renpy.ast"
    def __setstate__(self, state):
        (_, self.source, self.location, self.mode) = state
        self.bytecode = None

class RevertableList(magic.FakeStrict, list):
    __module__ = "renpy.python"
    def __new__(cls):
        return list.__new__(cls)

class RevertableDict(magic.FakeStrict, dict):
    __module__ = "renpy.python"
    def __new__(cls):
        return dict.__new__(cls)

class RevertableSet(magic.FakeStrict, set):
    __module__ = "renpy.python"
    def __new__(cls):
        return set.__new__(cls)

    def __setstate__(self, state):
        if isinstance(state, tuple):
            self.update(state[0].keys())
        else:
            self.update(state)

class Sentinel(magic.FakeStrict, object):
    __module__ = "renpy.object"
    def __new__(cls, name):
        obj = object.__new__(cls)
        obj.name = name
        return obj

factory = magic.FakeClassFactory((PyExpr, PyCode, RevertableList, RevertableDict, RevertableSet, Sentinel), magic.FakeStrict)

def read_ast_from_file(raw_contents):
    data, stmts = magic.safe_loads(raw_contents, factory, {"_ast", "collections"})
    return stmts

def ensure_dir(filename):
    dir = path.dirname(filename)
    if dir and not path.exists(dir):
        os.makedirs(dir)

def decompile_rpyc(data, abspath, init_offset):
    # Output filename is input filename but with .rpy extension
    filepath, ext = path.splitext(abspath)
    out_filename = filepath + ('.rpym' if ext == ".rpymc" else ".rpy")

    ast = read_ast_from_file(data)

    ensure_dir(out_filename)
    with codecs.open(out_filename, 'w', encoding='utf-8') as out_file:
        decompiler.pprint(out_file, ast, init_offset=init_offset)
    return True

def decompile_game():
    import sys

    logfile = path.join(os.getcwd(), "game/unrpyc.log.txt")
    ensure_dir(logfile)
    with open(logfile, "w") as f:
        f.write("Beginning decompiling\n")

        for abspath, fn, dir, data in sys.files:
            try:
                decompile_rpyc(data, abspath, sys.init_offset)
            except Exception, e:
                f.write("\nFailed at decompiling {0}\n".format(abspath))
                traceback = sys.modules['traceback']
                traceback.print_exc(None, f)
            else:
                f.write("\nDecompiled {0}\n".format(abspath))

        f.write("\nend decompiling\n")

    return