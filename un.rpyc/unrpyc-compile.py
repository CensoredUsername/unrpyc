# Copyright (c) 2012-2024 Yuri K. Schlesner, CensoredUsername, Jackmcbarn
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
from decompiler.renpycompat import pickle_safe_loads

def read_ast_from_file(raw_contents):
    _, stmts = pickle_safe_loads(raw_contents)
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
        options = decompiler.Options(init_offset=init_offset)
        decompiler.pprint(out_file, ast, options)
    return options.log

def decompile_game():
    import sys

    logfile = path.join(os.getcwd(), "game/unrpyc.log.txt")
    ensure_dir(logfile)
    with open(logfile, "w") as f:
        f.write("Beginning decompiling\n")

        for abspath, data in sys.files:
            try:
                log = decompile_rpyc(data, abspath, sys.init_offset)
            except Exception, e:
                f.write("\nFailed at decompiling {0}\n".format(abspath))
                traceback = sys.modules['traceback']
                traceback.print_exc(None, f)
            else:
                f.write("\nDecompiled {0}\n".format(abspath))
                for line in log:
                    f.write(line)

        f.write("\nend decompiling\n")

    return