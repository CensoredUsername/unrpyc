#!/usr/bin/env python

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

import zlib
import argparse
import os, sys
import minimize
import base64
from os import path

parser = argparse.ArgumentParser(description="Pack unpryc into un.rpyc which can be ran from inside renpy")

parser.add_argument("-d", "--debug", dest="debug", action="store_true", help="Create debug files")

parser.add_argument("-m", "--magic-path", dest="magic", action="store", default="picklemagic",
                    help="In case picklemagic isn't in the python search path you can specify its folder here")

parser.add_argument("-p", "--protocol", dest="protocol", action="store", default="1",
                    help="The pickle protocol used for packing the pickles. default is 1, options are 0, 1 and 2")

parser.add_argument("-r", "--raw", dest="minimize", action="store_false",
                    help="Don't minimize the compiler modules")

parser.add_argument("-o", "--obfuscate", dest="obfuscate", action="store_true",
                    help="Enable extra minification measures which do not really turn down the filesize but make the source a lot less readable")

args = parser.parse_args()

sys.path.append(path.abspath(args.magic))
protocol = int(args.protocol)

try:
    import pickleast as p
except ImportError:
    exit("Could not import pickleast. Are you sure it's in pythons module search path?")

def Module(name, filename, munge_globals=True, retval=False):
    with open(filename, "rb" if p.PY2 else "r") as f:
        code = f.read()
    if args.minimize:
        # in modules only locals are worth optimizing
        code = minimize.minimize(code, True, args.obfuscate and munge_globals, args.obfuscate, args.obfuscate)
    return p.Module(name, code, retval=retval)

def Exec(code):
    if args.minimize:
        # In exec, we should always munge globals
        code = minimize.minimize(code, True, True, args.obfuscate, args.obfuscate)
    return p.Exec(code)


pack_folder = path.dirname(path.abspath(__file__))
base_folder = path.dirname(pack_folder)

base = """
# Set up the namespace
from os.path import join
from os import getcwd
from sys import modules, meta_path
from renpy.loader import listdirfiles

# and some things we store in the global namespace so we can access them inside exec
global basepath
global files
global __package__

# an easter egg
exec '''
import StringIO
try:
    import renpy
except Exception:
    raise _Stop(({"version": "broken", "key": "thrown away"}, []))
''' in globals()

basepath = join(getcwd(), "game")
files = listdirfiles()

exec '''
import os, sys, renpy, zlib
sys.init_offset = renpy.version_tuple >= (6, 99, 10, 1224)
sys.files = []
for (dir, fn) in files:
    if fn.endswith((".rpyc", ".rpymc")):
        if dir and dir.endswith("common"):
            continue
        elif fn == "un.rpyc":
            continue
        elif (dir, fn[:-1]) not in files:
            abspath = os.path.join(dir, fn) if dir else os.path.join(basepath, fn)
            with renpy.loader.load(fn) as file:
                bindata = renpy.game.script.read_rpyc_data(file, 1)
                sys.files.append((abspath, fn, dir, bindata))
''' in globals()

_0 # util
_1 # magic
_2 # codegen

renpy_modules = modules.copy()

exec '''
import sys
for i in sys.modules.copy():
    if "renpy" in i and not "renpy.execution" in i:
        sys.modules.pop(i)
''' in globals()

renpy_loader = meta_path.pop()
package = __package__
__package__ = ""

import traceback as traceback
import codecs as codecs

from magic import fake_package, FakeModule, remove_fake_package
# fake the prescense of renpy
fake_package("renpy")
# astdump and translate are unused
FakeModule("astdump")
FakeModule("translate")

_3 # testcasedecompiler
_4 # screendecompiler
_5 # sl2decompiler
_6 # decompiler
_7 # unrpyc

from unrpyc import decompile_game
decompile_game()
remove_fake_package("renpy")

modules.update(renpy_modules)
meta_path.append(renpy_loader)
__package__ = package
"""

decompiler_rpyc = p.ExecTranspile(base + """
from renpy import script_version
from renpy.game import script
({'version': script_version, 'key': script.key}, [])
""", (
    Module("util", path.join(base_folder, "decompiler/util.py")),
    Module("magic", path.join(base_folder, "decompiler/magic.py"), False),
    Module("codegen", path.join(base_folder, "decompiler/codegen.py")),
    Module("testcasedecompiler", path.join(base_folder, "decompiler/testcasedecompiler.py")),
    Module("screendecompiler", path.join(base_folder, "decompiler/screendecompiler.py")),
    Module("sl2decompiler", path.join(base_folder, "decompiler/sl2decompiler.py")),
    Module("decompiler", path.join(base_folder, "decompiler/__init__.py")),
    Module("unrpyc", path.join(pack_folder, "unrpyc-compile.py"))
))

decompiler_rpyb = p.ExecTranspile(base + "(None, [])\n", (
    Module("util", path.join(base_folder, "decompiler/util.py")),
    Module("magic", path.join(base_folder, "decompiler/magic.py"), False),
    Module("codegen", path.join(base_folder, "decompiler/codegen.py")),
    Module("testcasedecompiler", path.join(base_folder, "decompiler/testcasedecompiler.py")),
    Module("screendecompiler", path.join(base_folder, "decompiler/screendecompiler.py")),
    Module("sl2decompiler", path.join(base_folder, "decompiler/sl2decompiler.py")),
    Module("decompiler", path.join(base_folder, "decompiler/__init__.py")),
    Module("unrpyc", path.join(pack_folder, "unrpyc-compile.py"))
))

rpy_one = p.GetItem(p.Sequence(
    Module("util", path.join(base_folder, "decompiler/util.py")),
    Module("magic", path.join(base_folder, "decompiler/magic.py"), False),
    Module("codegen", path.join(base_folder, "decompiler/codegen.py")),
), "magic")

rpy_two = p.GetItem(p.Sequence(
    Module("testcasedecompiler", path.join(base_folder, "decompiler/testcasedecompiler.py")),
    Module("screendecompiler", path.join(base_folder, "decompiler/screendecompiler.py")),
    Module("sl2decompiler", path.join(base_folder, "decompiler/sl2decompiler.py")),
    Module("decompiler", path.join(base_folder, "decompiler/__init__.py")),
    Module("unrpyc", path.join(pack_folder, "unrpyc-compile.py"))
), "unrpyc")

rpy_base = """
init python early hide:

    # Set up the namespace
    import os
    import os.path
    import sys
    import renpy
    import renpy.loader
    import base64
    import pickle
    import zlib

    basepath = os.path.join(os.getcwd(), "game")
    files = renpy.loader.listdirfiles()

    sys.init_offset = renpy.version_tuple >= (6, 99, 10, 1224)
    sys.files = []
    for (dir, fn) in files:
        if fn.endswith((".rpyc", ".rpymc")):
            if dir and dir.endswith("common"):
                continue
            elif fn == "un.rpyc":
                continue
            elif (dir, fn[:-1]) not in files:
                abspath = os.path.join(dir, fn) if dir else os.path.join(basepath, fn)
                with renpy.loader.load(fn) as file:
                    bindata = renpy.game.script.read_rpyc_data(file, 1)
                    sys.files.append((abspath, fn, dir, bindata))

    # ???
    magic = pickle.loads(base64.b64decode({}))

    renpy_modules = sys.modules.copy()
    for i in renpy_modules:
        if b"renpy" in i and not b"renpy.execution" in i:
            sys.modules.pop(i)

    renpy_loader = sys.meta_path.pop()

    magic.fake_package(b"renpy")
    magic.FakeModule(b"astdump")
    magic.FakeModule(b"translate")

    # ?????????
    unrpyc = pickle.loads(base64.b64decode({}))
    unrpyc.decompile_game()

    magic.remove_fake_package(b"renpy")

    sys.modules.update(renpy_modules)
    sys.meta_path.append(renpy_loader)
"""

unrpyc = zlib.compress(
    p.optimize(
        p.dumps(decompiler_rpyc, protocol),
    protocol),
9)

bytecoderpyb = zlib.compress(
    p.optimize(
        p.dumps(decompiler_rpyb, protocol),
    protocol),
9)

unrpy = rpy_base.format(
    repr(base64.b64encode(p.optimize(p.dumps(rpy_one, protocol), protocol))),
    repr(base64.b64encode(p.optimize(p.dumps(rpy_two, protocol), protocol)))
)


with open(path.join(pack_folder, "un.rpyc"), "wb") as f:
    f.write(unrpyc)

with open(path.join(pack_folder, "bytecode.rpyb"), "wb") as f:
    f.write(bytecoderpyb)

with open(path.join(pack_folder, "un.rpy"), "wb") as f:
    f.write(unrpy)

if args.debug:
    print("File length = {0}".format(len(unrpyc)))

    import pickletools

    data = zlib.decompress(unrpyc)

    with open(path.join(pack_folder, "un.dis"), "wb" if p.PY2 else "w") as f:
        pickletools.dis(data, f)

    for com, arg, _ in pickletools.genops(data):
        if arg and (isinstance(arg, str) or
                    p.PY3 and isinstance(arg, bytes)) and len(arg) > 1000:

            if p.PY3 and isinstance(arg, str):
                arg = arg.encode("latin1")

            data = zlib.decompress(arg)
            break
    else:
        raise Exception("didn't find the gzipped blob inside")

    with open(path.join(pack_folder, "un.dis2"), "wb" if p.PY2 else "w") as f:
        pickletools.dis(data, f)

    with open(path.join(pack_folder, "un.dis3"), "wb" if p.PY2 else "w") as f:
        p.pprint(decompiler_rpyc, f)
