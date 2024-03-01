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
from os import path, walk
import codecs
import glob
import itertools
import traceback
import struct
import zlib
from operator import itemgetter

try:
    from multiprocessing import Pool, Lock, cpu_count
except ImportError:
    # Mock required support when multiprocessing is unavailable
    def cpu_count():
        return 1

    class Lock:
        def __enter__(self):
            pass
        def __exit__(self, type, value, traceback):
            pass
        def acquire(self, block=True, timeout=None):
            pass
        def release(self):
            pass

import decompiler
import deobfuscate
from decompiler import astdump, translate
from decompiler.renpycompat import (pickle_safe_loads, pickle_safe_dumps, pickle_safe_dump,
                                    pickle_loads)


printlock = Lock()


# API

def read_ast_from_file(in_file):
    # .rpyc files are just zlib compressed pickles of a tuple of some data and the actual AST of the file
    raw_contents = in_file.read()
    if raw_contents.startswith("RENPY RPC2"):
        # parse the archive structure
        position = 10
        chunks = {}
        while True:
            slot, start, length = struct.unpack("III", raw_contents[position: position + 12])
            if slot == 0:
                break
            position += 12

            chunks[slot] = raw_contents[start: start + length]

        raw_contents = chunks[1]

    raw_contents = zlib.decompress(raw_contents)
    _, stmts = pickle_safe_loads(raw_contents)
    return stmts


def decompile_rpyc(input_filename, overwrite=False, dump=False, decompile_python=False,
                   comparable=False, no_pyexpr=False, translator=None, tag_outside_block=False,
                   init_offset=False, try_harder=False, sl_custom_names=None):

    # Output filename is input filename but with .rpy extension
    filepath, ext = path.splitext(input_filename)
    if dump:
        out_filename = filepath + ".txt"
    elif ext == ".rpymc":
        out_filename = filepath + ".rpym"
    else:
        out_filename = filepath + ".rpy"

    with printlock:
        print("Decompiling %s to %s..." % (input_filename, out_filename))

        if not overwrite and path.exists(out_filename):
            print("Output file already exists. Pass --clobber to overwrite.")
            return False # Don't stop decompiling if one file already exists

    with open(input_filename, 'rb') as in_file:
        if try_harder:
            ast = deobfuscate.read_ast(in_file)
        else:
            ast = read_ast_from_file(in_file)

    with codecs.open(out_filename, 'w', encoding='utf-8') as out_file:
        if dump:
            astdump.pprint(out_file, ast, decompile_python=decompile_python, comparable=comparable,
                                          no_pyexpr=no_pyexpr)
        else:
            options = decompiler.Options(printlock=printlock, decompile_python=decompile_python, translator=translator,
                                         tag_outside_block=tag_outside_block, init_offset=init_offset, sl_custom_names=sl_custom_names)

            decompiler.pprint(out_file, ast, options)
    return True

def extract_translations(input_filename, language):
    with printlock:
        print("Extracting translations from %s..." % input_filename)

    with open(input_filename, 'rb') as in_file:
        ast = read_ast_from_file(in_file)

    translator = translate.Translator(language, True)
    translator.translate_dialogue(ast)
    # we pickle and unpickle this manually because the regular unpickler will choke on it
    return pickle_safe_dumps(translator.dialogue), translator.strings


def parse_sl_custom_names(unparsed_arguments):
    # parse a list of strings in the format
    # classname=name-nchildren into {classname: (name, nchildren)}
    parsed_arguments = {}
    for argument in unparsed_arguments:
        content = argument.split("=")
        if len(content) != 2:
            raise Exception("Bad format in custom sl displayable registration: '{}'".format(argument))

        classname, name = content
        split = name.split("-")
        if len(split) == 1:
            amount = "many"

        elif len(split) == 2:
            name, amount = split
            if amount == "0":
                amount = 0
            elif amount == "1":
                amount = 1
            elif amount == "many":
                pass
            else:
                raise Exception("Bad child node count in custom sl displayable registration: '{}'".format(argument))

        else:
            raise Exception("Bad format in custom sl displayable registration: '{}'".format(argument))

        parsed_arguments[classname] = (name, amount)

    return parsed_arguments

def worker(t):
    (args, filename, filesize) = t
    try:
        if args.write_translation_file:
            return extract_translations(filename, args.language)
        else:
            if args.translation_file is not None:
                translator = translate.Translator(None)
                translator.language, translator.dialogue, translator.strings = (
                    pickle_loads(args.translations))
            else:
                translator = None
            return decompile_rpyc(filename, args.clobber, args.dump, decompile_python=args.decompile_python,
                                  no_pyexpr=args.no_pyexpr, comparable=args.comparable, translator=translator,
                                  tag_outside_block=args.tag_outside_block, init_offset=args.init_offset,
                                  try_harder=args.try_harder, sl_custom_names=args.sl_custom_names)
    except Exception as e:
        with printlock:
            print("Error while decompiling %s:" % filename)
            print(traceback.format_exc())
        return False

def sharelock(lock):
    global printlock
    printlock = lock

def main():
    # python27 unrpyc.py [-c] [-d] [--python-screens|--ast-screens|--no-screens] file [file ...]
    cc_num = cpu_count()
    parser = argparse.ArgumentParser(description="Decompile .rpyc/.rpymc files")

    parser.add_argument('-c', '--clobber', dest='clobber', action='store_true',
                        help="overwrites existing output files")

    parser.add_argument('-d', '--dump', dest='dump', action='store_true',
                        help="instead of decompiling, pretty print the ast to a file")

    parser.add_argument('-p', '--processes', dest='processes', action='store', type=int,
                        choices=range(1, cc_num), default=cc_num - 1 if cc_num > 2 else 1,
                        help="use the specified number or processes to decompile."
                        "Defaults to the amount of hw threads available minus one, disabled when muliprocessing is unavailable.")

    parser.add_argument('-t', '--translation-file', dest='translation_file', action='store', default=None,
                        help="use the specified file to translate during decompilation")

    parser.add_argument('-T', '--write-translation-file', dest='write_translation_file', action='store', default=None,
                        help="store translations in the specified file instead of decompiling")

    parser.add_argument('-l', '--language', dest='language', action='store', default='english',
                        help="if writing a translation file, the language of the translations to write")

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

    parser.add_argument('--tag-outside-block', dest='tag_outside_block', action='store_true',
                        help="Always put SL2 'tag's on the same line as 'screen' rather than inside the block. "
                        "This will break compiling with Ren'Py 7.3 and above, but is needed to get correct line numbers "
                        "from some files compiled with older Ren'Py versions.")

    parser.add_argument('--init-offset', dest='init_offset', action='store_true',
                        help="Attempt to guess when init offset statements were used and insert them. "
                        "This is always safe to enable if the game's Ren'Py version supports init offset statements, "
                        "and the generated code is exactly equivalent, only less cluttered.")

    parser.add_argument('file', type=str, nargs='+',
                        help="The filenames to decompile. "
                        "All .rpyc files in any directories passed or their subdirectories will also be decompiled.")

    parser.add_argument('--try-harder', dest="try_harder", action="store_true",
                        help="Tries some workarounds against common obfuscation methods. This is a lot slower.")

    parser.add_argument('--register-sl-displayable', dest="sl_custom_names", type=str, nargs='+',
                        help="Accepts mapping separated by '=', "
                        "where the first argument is the name of the user-defined displayable object, "
                        "and the second argument is a string containing the name of the displayable,"
                        "potentially followed by a '-', and the amount of children the displayable takes"
                        "(valid options are '0', '1' or 'many', with 'many' being the default)")

    args = parser.parse_args()

    if args.write_translation_file and not args.clobber and path.exists(args.write_translation_file):
        # Fail early to avoid wasting time going through the files
        print("Output translation file already exists. Pass --clobber to overwrite.")
        return

    if args.translation_file:
        with open(args.translation_file, 'rb') as in_file:
            args.translations = in_file.read()

    if args.sl_custom_names is not None:
        try:
            args.sl_custom_names = parse_sl_custom_names(args.sl_custom_names)
        except Exception as e:
            print("\n".join(e.args))
            return

    # Expand wildcards
    def glob_or_complain(s):
        retval = glob.glob(s)
        if not retval:
            print("File not found: " + s)
        return retval
    filesAndDirs = map(glob_or_complain, args.file)
    # Concatenate lists
    filesAndDirs = list(itertools.chain(*filesAndDirs))

    # Recursively add .rpyc files from any directories passed
    files = []
    for i in filesAndDirs:
        if path.isdir(i):
            for dirpath, dirnames, filenames in walk(i):
                files.extend(path.join(dirpath, j) for j in filenames if len(j) >= 5 and j.endswith(('.rpyc', '.rpymc')))
        else:
            files.append(i)

    # Check if we actually have files. Don't worry about
    # no parameters passed, since ArgumentParser catches that
    if len(files) == 0:
        print("No script files to decompile.")
        return

    files = map(lambda x: (args, x, path.getsize(x)), files)
    processes = int(args.processes)
    if processes > 1:
        # If a big file starts near the end, there could be a long time with
        # only one thread running, which is inefficient. Avoid this by starting
        # big files first.
        files.sort(key=itemgetter(2), reverse=True)
        results = Pool(int(args.processes), sharelock, [printlock]).map(worker, files, 1)
    else:
        # Decompile in the order Ren'Py loads in
        files.sort(key=itemgetter(1))
        results = map(worker, files)

    if args.write_translation_file:
        print("Writing translations to %s..." % args.write_translation_file)
        translated_dialogue = {}
        translated_strings = {}
        good = 0
        bad = 0
        for result in results:
            if not result:
                bad += 1
                continue
            good += 1
            translated_dialogue.update(pickle_loads(result[0]))
            translated_strings.update(result[1])
        with open(args.write_translation_file, 'wb') as out_file:
            pickle_safe_dump((args.language, translated_dialogue, translated_strings), out_file)

    else:
        # Check per file if everything went well and report back
        good = results.count(True)
        bad = results.count(False)

    if bad == 0:
        print("Decompilation of %d script file%s successful" % (good, 's' if good>1 else ''))
    elif good == 0:
        print("Decompilation of %d file%s failed" % (bad, 's' if bad>1 else ''))
    else:
        print("Decompilation of %d file%s successful, but decompilation of %d file%s failed" % (good, 's' if good>1 else '', bad, 's' if bad>1 else ''))

if __name__ == '__main__':
    main()
