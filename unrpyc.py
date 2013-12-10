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
import os.path
import sys
import cPickle as pickle
import codecs
import glob
import itertools
import astdump

# we store some configuration in here so we can easily pass it around.
class config:
    EXTRACT_PYTHON_AST     = True
    DECOMPILE_PYTHON_AST   = True
    FORCE_MULTILINE_KWARGS = True
    DECOMPILE_SCREENCODE   = True

class Dummy:
    # This is necessary for unpickling the AST's, they expect an instance of this class to be
    # in renpy.game.script, however this is only added at runtime by renpy normally
    def record_pycode(self,*args,**kwargs):
        return
    all_pycode = []

def import_renpy(basedir=None):
    #import renpy from another location.
    if basedir:
        sys.path.append(basedir)
    global renpy
    global decompiler
    global astdump
    
    # Needed for pickle to read the AST
    try:
        import renpy
    except ImportError:
        print "\nFailed at importing renpy. Are you sure that the renpy directory can be found in sys.path or the current working directory?\n"
        raise
    # try to import as much renpy modules as possible, but some modules might not exist
    # in older ren'py versions. 
    try: import renpy.log
    except: pass
    try: import renpy.display
    except: pass
    try: import renpy.object
    except: pass
    try: 
        import renpy.game
        renpy.game.script = Dummy()
    except: pass
    try: import renpy.loader
    except: pass
    try: import renpy.ast
    except: pass
    try: import renpy.atl
    except: pass
    try: import renpy.curry
    except: pass
    try: import renpy.easy
    except: pass
    try: import renpy.execution
    except: pass
    try: import renpy.loadsave
    except: pass
    try: import renpy.parser
    except: pass
    try: import renpy.python
    except: pass
    try: import renpy.script
    except: pass
    try: import renpy.statements
    except: pass
    try: import renpy.style
    except: pass

    # We can only import the decompiler when we've imported renpy's insides
    import decompiler
    if basedir:
        sys.path.remove(basedir)


def read_ast_from_file(in_file):
    # .rpyc files are just zlib compressed pickles of a tuple of some data and the actual AST of the file
    raw_contents = in_file.read().decode('zlib')
    data, stmts = pickle.loads(raw_contents)
    return stmts

def decompile_rpyc(input_filename, overwrite=False, dump=False):
    # Output filename is input filename but with .rpy extension
    path, ext = os.path.splitext(input_filename)
    out_filename = path + ('.txt' if dump else '.rpy')

    print "Decompiling %s to %s..." % (input_filename, out_filename)
    
    if not overwrite and os.path.exists(out_filename):
        print "Output file already exists. Pass --clobber to overwrite."
        return False # Don't stop decompiling if one file already exists

    with open(input_filename, 'rb') as in_file:
        ast = read_ast_from_file(in_file)

    with codecs.open(out_filename, 'w', encoding='utf-8') as out_file:
        if dump:
            astdump.pprint(out_file, ast, config)
        else:
            decompiler.pretty_print_ast(out_file, ast, config)
            
    return True

def main():
    # python27 unrpyc.py [-c] [-b BASEDIR] [-d] [--python-screens|--ast-screens|--no-screens|--single-line-screen-kwargs] file [file ...]
    parser = argparse.ArgumentParser(description="Decompile .rpyc files")

    parser.add_argument('-c', '--clobber', dest='clobber', action='store_true',
                        help="overwrites existing output files")

    parser.add_argument('-b', '--basedir', dest='basedir', action='store',
                        help="specify the game base directory in which the 'renpy' directory is located") 

    parser.add_argument('-d', '--dump', dest='dump', action='store_true',
                        help="instead of decompiling, pretty print the ast to a file")

    configscreen = parser.add_mutually_exclusive_group()

    configscreen.add_argument('--python-screens', dest='pythonscreens', action='store_true',
                        help="only for decompiling, don't decompile screens back to screen language")

    configscreen.add_argument('--ast-screens', dest='astscreens', action='store_true',
                        help="only for dumping, prints the entire screen ast instead of decompiling")

    configscreen.add_argument('--no-screens', dest='noscreens', action='store_true',
                        help="don't extract screens at all")

    configscreen.add_argument('--single-line-screen-kwargs', dest='screenkwargs', action='store_true',
                        help="don't force all keyword arguments from screencode to different lines")

    parser.add_argument('file', type=str, nargs='+', 
                        help="The filenames to decompile")

    args = parser.parse_args()

    # set config according to the passed options
    if args.pythonscreens:
        config.DECOMPILE_SCREENCODE=False
    elif args.noscreens:
        config.EXTRACT_PYTHON_AST=False
    elif args.astscreens:
        config.DECOMPILE_PYTHON_AST=False
    elif args.screenkwargs:
        config.FORCE_MULTILINE_KWARGS=False

    # try to import renpy
    if args.basedir:
        import_renpy(args.basedir)
    else:
        import_renpy()

    # Expand wildcards
    files = map(glob.glob, args.file)
    # Concatenate lists
    files = list(itertools.chain(*files))

    # Check if we actually have files
    if len(files) == 0:
        parser.print_help();
        parser.error("No script files given.")

    # Check per file if everything went well and report back
    good = bad = 0
    for filename in files:
        try:
            a = decompile_rpyc(filename, args.clobber, args.dump)
        except Exception as e:
            print e
            bad += 1
        else:
            if a:
                good += 1
            else:
                bad += 1
    if bad == 0:
        print "Decompilation of %d script file%s successful" % (good, 's' if good>1 else '')
    elif good == 0:
        print "Decompilation of %d file%s failed" % (bad, 's' if bad>1 else '')
    else:
        print "Decompilation of %d file%s successful, but decompilation of %d file%s failed" % (good, 's' if good>1 else '', bad, 's' if bad>1 else '')

if __name__ == "__main__":
    main()
else:
    # We're just being imported, assume sys.path already makes renpy accessible
    import_renpy()

