#!/usr/bin/env python

# Copyright (c) 2014-2024 CensoredUsername
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
import base64
from pathlib import Path
from corrupy import pickleast as p, minimize

parser = argparse.ArgumentParser(
    description="Pack unrpyc into un.rpyc which can be ran from inside renpy")

parser.add_argument(
    "-d",
    "--debug",
    dest="debug",
    action="store_true",
    help="Create debug files")

parser.add_argument(
    "-p",
    "--protocol",
    dest="protocol",
    action="store",
    default="1",
    help="The pickle protocol used for packing the pickles. Default is 1, options "
    "are 0, 1 and 2")

parser.add_argument(
    "-r",
    "--raw",
    dest="minimize",
    action="store_false",
    help="Don't minimize the compiler modules")

parser.add_argument(
    "-o",
    "--obfuscate",
    dest="obfuscate",
    action="store_true",
    help="Enable extra minification measures which do not really turn down the filesize but "
    "make the source a lot less readable")

args = parser.parse_args()

protocol = int(args.protocol)

def Module(name, filename, munge_globals=True, retval=False, package=None):
    with open(filename, "rb" if p.PY2 else "r") as f:
        code = f.read()
    if args.minimize:
        # in modules only locals are worth optimizing
        code = minimize.minimize(
            code, True, args.obfuscate and munge_globals, args.obfuscate, args.obfuscate)
    if package:
        return p.Sequence(
            p.DeclareModule(name, retval=retval),
            p.SetItem(p.Imports(name, "__dict__"), "__package__", package),
            p.DefineModule(name, code),
            reversed=True)
    else:
        return p.Module(name, code, retval=retval)

def Exec(code):
    if args.minimize:
        # In exec, we should always munge globals
        code = minimize.minimize(code, True, True, args.obfuscate, args.obfuscate)
    return p.Exec(code)


PACK_FOLDER = Path(__file__).parent
BASE_FOLDER = PACK_FOLDER.parent

base = """
# Set up the namespace
from os.path import join
from os import getcwd
from sys import modules, meta_path
from renpy.loader import listdirfiles
from builtins import exec

# and some things we store in the global namespace so we can access them inside exec
global basepath
global files
global __package__

# backup the local environment
renpy_modules = modules.copy()
renpy_meta_path = meta_path.copy()
pickle_package = __package__
__package__ = ""

# an easter egg
exec('''
try:
    import renpy
except Exception:
    raise _Stop(({"version": "broken", "key": "thrown away"}, []))
''', globals())

# figure out the files we need to process and load their contents in memory
basepath = join(getcwd(), "game")
files = listdirfiles()

exec('''
import os, sys, renpy, zlib, pathlib
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
                sys.files.append((pathlib.Path(abspath), bindata))
''', globals())

# tear down the renpy environment
exec('''
import sys
for i in sys.modules.copy():
    if "renpy" in i and not "renpy.execution" in i:
        sys.modules.pop(i)
sys.meta_path[:] = [i for i in sys.meta_path if "renpy" not in i.__class__.__module__]
''', globals())

# decompiler injection
_0

from unrpyc import decompile_game
decompile_game()

from decompiler.magic import remove_fake_package
remove_fake_package("renpy")

modules.clear()
modules.update(renpy_modules)
meta_path[:] = renpy_meta_path
__package__ = pickle_package
"""

decompiler_items = p.GetItem(p.Sequence(
    p.DeclareModule("decompiler"),
    p.DeclareModule("decompiler.translate"),
    p.DeclareModule("decompiler.astdump"),
    Module("decompiler.util", BASE_FOLDER / "decompiler/util.py"),
    Module("decompiler.magic", BASE_FOLDER / "decompiler/magic.py", False),
    Module("decompiler.renpycompat", BASE_FOLDER / "decompiler/renpycompat.py"),
    Module("decompiler.testcasedecompiler", BASE_FOLDER / "decompiler/testcasedecompiler.py"),
    Module("decompiler.atldecompiler", BASE_FOLDER / "decompiler/atldecompiler.py"),
    Module("decompiler.sl2decompiler", BASE_FOLDER / "decompiler/sl2decompiler.py"),
    Module("decompiler", BASE_FOLDER / "decompiler/__init__.py", package="decompiler"),
    Module("unrpyc", PACK_FOLDER / "unrpyc-compile.py")
), "unrpyc")

decompiler_rpyc = p.ExecTranspile(base + """
from renpy import script_version
from renpy.game import script
({'version': script_version, 'key': script.key}, [])
""", (decompiler_items,))

decompiler_rpyb = p.ExecTranspile(base + "(None, [])", (decompiler_items,))

rpy_base = """\
python early hide:

    import sys
    renpy_modules = sys.modules.copy()
    renpy_meta_path = sys.meta_path.copy()

    # Set up the namespace
    import os
    import os.path
    import renpy
    import renpy.loader
    import base64
    import pickle
    import zlib
    import pathlib

    basepath = os.path.join(os.getcwd(), "game")
    files = renpy.loader.listdirfiles()

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
                    sys.files.append((pathlib.Path(abspath), bindata))

    for i in renpy_modules:
        if "renpy" in i and not "renpy.execution" in i:
            sys.modules.pop(i)
    sys.meta_path[:] = [i for i in sys.meta_path if "renpy" not in i.__class__.__module__]

    # ?????????
    unrpyc = pickle.loads(base64.b64decode({}))
    unrpyc.decompile_game()

    from decompiler.magic import remove_fake_package
    remove_fake_package("renpy")

    sys.modules.clear()
    sys.modules.update(renpy_modules)
    sys.meta_path[:] = renpy_meta_path
"""

unrpyc = zlib.compress(
    p.optimize(p.dumps(decompiler_rpyc, protocol), protocol), 9)

bytecoderpyb = zlib.compress(
    p.optimize(p.dumps(decompiler_rpyb, protocol), protocol), 9)

unrpy = rpy_base.format(repr(base64.b64encode(
    p.optimize(p.dumps(decompiler_items, protocol), protocol))))


with (PACK_FOLDER / "un.rpyc").open("wb") as f:
    f.write(unrpyc)

with (PACK_FOLDER / "bytecode-39.rpyb").open("wb") as f:
    f.write(bytecoderpyb)

with (PACK_FOLDER / "un.rpy").open("w", encoding="utf-8") as f:
    f.write(unrpy)

if args.debug:
    print(f'File length = {len(unrpyc)}')

    import pickletools

    data = zlib.decompress(unrpyc)

    with (PACK_FOLDER / "un.dis").open("w", encoding="utf-8") as f:
        pickletools.dis(data, f)

    for com, arg, _ in pickletools.genops(data):
        if arg and (isinstance(arg, str)
                    or p.PY3 and isinstance(arg, bytes)) and len(arg) > 1000:

            if p.PY3 and isinstance(arg, str):
                arg = arg.encode("latin1")

            data = zlib.decompress(arg)
            break
    else:
        raise Exception("didn't find the gzipped blob inside")

    with (PACK_FOLDER / "un.dis2").open("w", encoding="utf-8") as f:
        pickletools.dis(data, f)

    with (PACK_FOLDER / "un.dis3").open("w", encoding="utf-8") as f:
        p.pprint(decompiler_rpyc, f)

    with (PACK_FOLDER / "un.rpy.dis").open("w", encoding="utf-8") as f:
        pickletools.dis(p.dumps(decompiler_items, protocol), f)
