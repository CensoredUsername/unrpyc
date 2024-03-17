#!/usr/bin/env python

# Copyright (c) 2024 CensoredUsername
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

# It is hard to test un.rpyc with a full renpy instance. But some automated testing would be nice.
# Therefore, this file attempts to construct the absolute minimum renpy environment necessary to
# load un.rpyc

import types
import sys
import os
import zlib
import argparse
import glob
import struct
import pickle
import traceback

from StringIO import StringIO
from os import path


SCRIPT_VERSION = 5003000
SCRIPT_KEY = "somerandomnonsense"


def main():
    parser = argparse.ArgumentParser(description="un.rypc testing framework")
    parser.add_argument("file", type=str, nargs='+', help="The files to provide for the test")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--unrpyc", type=str, help="Selects the un.rpyc file to test")
    group.add_argument("--unrpy", type=str, help="Selects the un.rpy file to test")
    group.add_argument("--unrpyb", type=str, help="Selects the un.rpyb file to tes")
    args = parser.parse_args()

    # we need to mess with the working directory later, so resolve these paths
    if args.unrpyc:
        args.unrpyc = path.realpath(args.unrpyc)
    if args.unrpy:
        args.unrpy = path.realpath(args.unrpy)
    if args.unrpyb:
        args.unrpyb = path.realpath(args.unrpyb)

    # resolve any globs and create our file list
    filelist = []
    for file in args.file:
        globbed = [path.realpath(i) for i in glob.iglob(file)]
        if not globbed:
            raise Exception("File not found: {}".format(file))

        filelist.extend(globbed)

    # move to the `testcases` directory
    os.chdir(path.dirname(path.abspath(__file__)))

    # if the output file already exists, clear it for now
    output_path = "game/unrpyc.log.txt"
    if path.exists(output_path):
        os.unlink(output_path)

    # build our ren'py environment
    build_renpy_environment(filelist)

    # make some backups of the environment
    meta_path = sys.meta_path[:]
    modules = sys.modules.copy()
    cwd = os.getcwd()

    # run the respective test case
    if args.unrpyc:
        test_unrpyc(args.unrpyc)

    elif args.unrpyb:
        test_unrpyb(args.unrpyb)

    elif args.unrpy:
        test_unrpy(args.unrpy)

    # check if the environment was left clean
    assert meta_path == sys.meta_path, "sys.meta_path was changed"
    assert modules == sys.modules, "sys.modules was changed"
    assert cwd == os.getcwd()

    # validate the expected output
    if not path.exists(output_path):
        raise Exception("No output log file was created")

    with open("game/unrpyc.log.txt", "r") as f:
        lines = list(f)

    # validate the output format
    assert lines[0] == "Beginning decompiling\n"
    assert lines[-1] == "end decompiling\n"

    # rudinemtary parse of the log file contents
    success = []
    failure = []
    for line in lines[1:-1]:
        if line.startswith("Failed at decompiling "):
            failure.append(line[len("Failed at decompiling "):].rstrip())

        elif line.startswith("Decompiled "):
            success.append(line[len("Decompiled  "):].rstrip())

    assert len(failure) == 0, "{} files failed decompilation".format(len(failure))
    assert len(success) == len(filelist), "Not all files were decompiled"

    print("{} files successfully decompiled".format(len(success)))

# testing protocols for the different files

def test_unrpyc(unrpyc):
    from renpy.game import script
    from renpy import loader
    
    with loader.load(unrpyc) as f:
        contents = script.read_rpyc_data(f, 1)
    
    # magic happens here
    data, stmts = loads(contents)

    # verify expected output
    assert data == dict(version=SCRIPT_VERSION, key=SCRIPT_KEY)
    assert stmts == []

def test_unrpyb(unrpyb):
    from renpy import loader

    with loader.load(unrpyb) as f:
        contents = zlib.decompress(f.read())

    # magic happens here
    version, cache = loads(contents)

    # verify expected output
    assert version is None
    assert cache == []

def test_unrpy(unrpy):
    # this one is the hardest to mockup properly, as we don't want to ship an entire ren'py runtime
    # luckily, this file basically is just a python file with a header.
    # so we strip the header and extra indentation, and then just compile -> execute it.
    from renpy import loader

    with loader.load(unrpy) as f:
        decoded = f.read()

    # need to strip the "init python early hide:" header and remove one layer of indentation
    contents = []
    for line in decoded.splitlines():
        if line.startswith("    "):
            # if indented, strip one layer of indentation
            contents.append(line[4:])
        elif not line.strip():
            # keep empty lines unchanged
            contents.append(line)
        else:
            # comment out "init python early hide""
            contents.append("#" + line)

        contents.append("\n")

    contents = "".join(contents)

    # compile unrpy
    code = compile(contents, unrpy, "exec")

    # run it
    exec code in {}

# utilies

def loads(buffer):
    # pickle wrapper that does the same thing as ren'py
    return pickle.loads(buffer)

def build_module(name, **items):
    # Construct a module with name `name`, and module contents `items`
    module = types.ModuleType(name, "totally legit module {}".format(name))
    module.__dict__.update(items)
    sys.modules[name] = module
    return module

class RenpyLoader:
    __module__ = "renpy.loader"

    # A meta path finder that does literally nothing.
    def find_module(self, fullname, path=None):
        return None

# shenanigans

def build_renpy_environment(filelist):
    # construct a module environment as it would be found in renpy
    # filelist: a list of path strings that will be returned
    # by renpy.loader.listdirfiles()

    def load(name, directory=None, tl=True):
        # renpy.loader.load
        # essentially ren'py's `open`

        # unrpyc doesn't use these
        assert directory is None
        assert tl is True

        return open(name, "rb")

    def listdirfiles(common=True):
        # renpy.loader.listdirfiles
        # returns a list of (directory, filename)
        # filename can be a longer relative path
        # directory is only the root directory from a search path
        # 
        # un.rpyc expects to be able to load a file just from its filename,
        # and uses either dirname/filename or ./filename to put it back
        #
        # if common is True: the list also contains common files
        # (engine files loaded by the game)
        root = os.getcwd()
        return [(root, path.relpath(p, root)) for p in filelist]

    class Script:
        # renpy.game.script = renpy.script.Script()
        def __init__(self):
            self.key = SCRIPT_KEY

        def read_rpyc_data(self, f, slot):
            # reads the data stored in slot `slot` of a rpyc file

            # adapted from unrpyc.py - read_ast_from_file

            raw_contents = f.read()

            # Support both rpyc v1 and v2
            if raw_contents.startswith("RENPY RPC2"):

                # parse the archive structure
                pos = 10
                chunks = {}
                while True:
                    slot_index, start, length = struct.unpack("III", raw_contents[pos: pos + 12])
                    if slot_index == 0:
                        break

                    pos += 12

                    chunks[slot_index] = raw_contents[start: start + length]

                slot_contents = chunks[slot]

            else:
                if slot != 1:
                    return None

                slot_contents = raw_contents

            return zlib.decompress(slot_contents)


    game = build_module(
        "renpy.game",
        script=Script(),
    )
    loader = build_module(
        "renpy.loader",
        load=load,
        listdirfiles=listdirfiles
    )
    renpy = build_module(
        "renpy",
        game=game,
        loader=loader,
        script_version=SCRIPT_VERSION,
        version_tuple = (7, 0, 0, 0)
    )

    # modern ren'py versions tend to have two loaders inserted at the start of sys.meta_path
    sys.meta_path.insert(0, RenpyLoader())
    sys.meta_path.insert(0, RenpyLoader())

    # older versions have a single one inserted at the end of sys.meta_path
    sys.meta_path.append(RenpyLoader())

    return renpy

if __name__ == '__main__':
    main()
