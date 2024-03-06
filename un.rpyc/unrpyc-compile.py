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

import sys
from pathlib import Path
import traceback
import struct

import decompiler
from decompiler.renpycompat import pickle_safe_loads

def read_ast_from_file(raw_contents):
    _, stmts = pickle_safe_loads(raw_contents)
    return stmts

def ensure_dir(filename):
    dir_name = Path(filename).parent
    if dir_name:
        dir_name.mkdir(parents=True, exist_ok=True)

def decompile_rpyc(data, fullpath):
    # Output filename is input filename but with .rpy extension
    out_filename = fullpath.with_suffix('.rpy' if fullpath.suffix == '.rpyc' else '.rpym')

    ast = read_ast_from_file(data)

    ensure_dir(out_filename)
    with out_filename.open('w', encoding='utf-8') as out_file:
        options = decompiler.Options(init_offset=True)
        decompiler.pprint(out_file, ast, options)
    return True

def decompile_game():

    logfile = Path.cwd().joinpath("game/unrpyc.log.txt")
    ensure_dir(logfile)
    with logfile.open("w", encoding="utf-8") as f:
        f.write("Beginning decompiling\n")

        for fullpath, data in sys.files:
            try:
                decompile_rpyc(data, fullpath)
            except Exception as e:
                f.write("\nFailed at decompiling {0}\n".format(fullpath))
                traceback = sys.modules['traceback']
                traceback.print_exc(None, f)
            else:
                f.write("\nDecompiled {0}\n".format(fullpath))

        f.write("\nend decompiling\n")

    return
