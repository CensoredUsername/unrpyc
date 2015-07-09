#!/usr/bin/env python2

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

import argparse
import os.path as path
import codecs
import glob
import itertools
import traceback
from multiprocessing import Pool, Lock, cpu_count
from operator import itemgetter

import decompiler
from decompiler import magic, astdump

# special definitions for special classes

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

class_factory = magic.FakeClassFactory((PyExpr, PyCode), magic.FakeStrict)

printlock = Lock()

# API

def read_ast_from_file(in_file):
    # .rpyc files are just zlib compressed pickles of a tuple of some data and the actual AST of the file
    raw_contents = in_file.read().decode('zlib')
    data, stmts = magic.safe_loads(raw_contents, class_factory, {"_ast"})
    return stmts

def decompile_rpyc(input_filename, overwrite=False, dump=False, decompile_python=False,
                   comparable=False, no_pyexpr=False):
    # Output filename is input filename but with .rpy extension
    filepath, ext = path.splitext(input_filename)
    out_filename = filepath + ('.txt' if dump else '.rpy')

    printlock.acquire()
    print "Decompiling %s to %s..." % (input_filename, out_filename)

    if not overwrite and path.exists(out_filename):
        print "Output file already exists. Pass --clobber to overwrite."
        printlock.release()
        return False # Don't stop decompiling if one file already exists

    printlock.release()

    with open(input_filename, 'rb') as in_file:
        ast = read_ast_from_file(in_file)

    with codecs.open(out_filename, 'w', encoding='utf-8') as out_file:
        if dump:
            astdump.pprint(out_file, ast, decompile_python=decompile_python, comparable=comparable,
                                          no_pyexpr=no_pyexpr)
        else:
            decompiler.pprint(out_file, ast, decompile_python=decompile_python, printlock=printlock)
    return True

def worker(t):
    (args, filename, filesize) = t
    try:
        return decompile_rpyc(filename, args.clobber, args.dump, decompile_python=args.decompile_python, no_pyexpr=args.no_pyexpr,
                                                                comparable=args.comparable)
    except Exception as e:
        printlock.acquire()
        print traceback.format_exc()
        printlock.release()
        return False

def sharelock(lock):
    global printlock
    printlock = lock

def main():
    # python27 unrpyc.py [-c] [-d] [--python-screens|--ast-screens|--no-screens] file [file ...]
    parser = argparse.ArgumentParser(description="Decompile .rpyc files")

    parser.add_argument('-c', '--clobber', dest='clobber', action='store_true',
                        help="overwrites existing output files")

    parser.add_argument('-d', '--dump', dest='dump', action='store_true',
                        help="instead of decompiling, pretty print the ast to a file")

    parser.add_argument('-p', '--processes', dest='processes', action='store', default=cpu_count(),
                        help="use the specified number of processes to decompile")

    parser.add_argument('--sl1-as-python', dest='decompile_python', action='store_true',
                        help="Only dumping and for decompiling screen language 1 screens. "
                        "Convert SL1 Python AST to Python code instead of dumping it or converting it to screenlang.")

    parser.add_argument('--comparable', dest='comparable', action='store_true',
                        help="Only for dumping, remove several false differences when comparing dumps. "
                        "This suppresses attributes that are different even when the code is identical, such as file modification times. ")

    parser.add_argument('--no-pyexpr', dest='no_pyexpr', action='store_true',
                        help="Only for dumping, disable special handling of PyExpr objects, instead printing them as strings. "
                        "This is useful when comparing dumps from different versions of Ren'Py. "
                        "It should only be used if necessary, since it will cause loss of information such as line numbers.")

    parser.add_argument('file', type=str, nargs='+',
                        help="The filenames to decompile")

    args = parser.parse_args()

    # Expand wildcards
    files = map(glob.glob, args.file)
    # Concatenate lists
    files = list(itertools.chain(*files))

    # Check if we actually have files
    if len(files) == 0:
        parser.print_help();
        parser.error("No script files given.")

    files = map(lambda x: (args, x, path.getsize(x)), files)
    processes = int(args.processes)
    if processes > 1:
        # If a big file starts near the end, there could be a long time with
        # only one thread running, which is inefficient. Avoid this by starting
        # big files first.
        files = sorted(files, key=itemgetter(2), reverse=True)
        results = Pool(int(args.processes), sharelock, [printlock]).map(worker, files, 1)
    else:
        results = map(worker, files)

    # Check per file if everything went well and report back
    good = results.count(True)
    bad = results.count(False)

    if bad == 0:
        print "Decompilation of %d script file%s successful" % (good, 's' if good>1 else '')
    elif good == 0:
        print "Decompilation of %d file%s failed" % (bad, 's' if bad>1 else '')
    else:
        print "Decompilation of %d file%s successful, but decompilation of %d file%s failed" % (good, 's' if good>1 else '', bad, 's' if bad>1 else '')

if __name__ == '__main__':
    main()