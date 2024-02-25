#!/usr/bin/env python3

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
import argparse
from pathlib import Path as pt
from functools import partial
import traceback
import struct
import zlib

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
from decompiler import magic, astdump, translate, special
# needs special.class_factory
import deobfuscate  # noqa


printlock = Lock()


def sharelock(lock):
    global printlock
    printlock = lock


# API
def read_ast_from_file(in_file):
    # .rpyc files are just zlib compressed pickles of a tuple of some data and the actual AST of the file
    raw_contents = in_file.read()

    # ren'py 8 only uses RPYC 2 files
    if not raw_contents.startswith(b"RENPY RPC2"):
        raise Exception("This isn't a normal rpyc file")

    # parse the archive structure
    position = 10
    chunks = {}
    while True:
        slot, start, length = struct.unpack("III", raw_contents[position: position + 12])
        if slot == 0:
            break
        position += 12

        chunks[slot] = raw_contents[start: start + length]

    raw_contents = zlib.decompress(chunks[1])
    data, stmts = magic.safe_loads(raw_contents, special.class_factory, {"_ast", "collections"})
    return stmts


def decompile_rpyc(input_filename, overwrite=False, dump=False, 
                   comparable=False, no_pyexpr=False, translator=None,
                   init_offset=False, try_harder=False, sl_custom_names=None):

    if dump:
        ext = '.txt'
    elif input_filename.suffix == ('.rpyc'):
        ext = '.rpy'
    elif input_filename.suffix == ('.rpymc'):
        ext = '.rpym'
    out_filename = input_filename.with_suffix(ext)

    with printlock:
        print(f"Decompiling {input_filename} to {out_filename}...")

        if not overwrite and out_filename.exists():
            print("Output file already exists and is skipped. Pass --clobber"
                  " to overwrite.")

    with input_filename.open('rb') as in_file:
        if try_harder:
            ast = deobfuscate.read_ast(in_file)
        else:
            ast = read_ast_from_file(in_file)

    # NOTE: PY3 'codecs' is not necessary
    with out_filename.open('w', encoding='utf-8') as out_file:
        if dump:
            astdump.pprint(out_file, ast, comparable=comparable,
                                          no_pyexpr=no_pyexpr)
        else:
            options = decompiler.Options(printlock=printlock, translator=translator,
                                         init_offset=init_offset, sl_custom_names=sl_custom_names)

            decompiler.pprint(out_file, ast, options)
    return True

def extract_translations(input_filename, language):
    with printlock:
        print(f"Extracting translations from {input_filename}...")

    with input_filename.open('rb') as in_file:
        ast = read_ast_from_file(in_file)

    translator = translate.Translator(language, True)
    translator.translate_dialogue(ast)
    # we pickle and unpickle this manually because the regular unpickler will choke on it
    return magic.safe_dumps(translator.dialogue), translator.strings

def parse_sl_custom_names(unparsed_arguments):
    # parse a list of strings in the format
    # classname=name-nchildren into {classname: (name, nchildren)}
    parsed_arguments = {}
    for argument in unparsed_arguments:
        content = argument.split("=")
        if len(content) != 2:
            raise Exception(f"Bad format in custom sl displayable registration: '{argument}'")

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
                raise Exception(
                    f"Bad child node count in custom sl displayable registration: '{argument}'")

        else:
            raise Exception(f"Bad format in custom sl displayable registration: '{argument}'")

        parsed_arguments[classname] = (name, amount)

    return parsed_arguments


def worker(args, filename):

    try:
        if args.write_translation_file:
            return extract_translations(filename, args.language)
        else:
            if args.translation_file is not None:
                translator = translate.Translator(None)
                translator.language, translator.dialogue, translator.strings = magic.loads(args.translations, special.class_factory)
            else:
                translator = None
            return decompile_rpyc(filename, args.clobber, args.dump, no_pyexpr=args.no_pyexpr,
                                  comparable=args.comparable, translator=translator,
                                  init_offset=args.init_offset, try_harder=args.try_harder,
                                  sl_custom_names=args.sl_custom_names)
    except Exception:
        with printlock:
            print(f"Error while decompiling {filename}: \n{traceback.format_exc()}")
        return False


def set_cpu_num():
    """Sets the number of used CPUs.
    3/4 of available, 1 if cores below 3. Overall max is 8."""
    num_cpu = cpu_count()
    return round(num_cpu * 0.75) if 2 < num_cpu < 11 else 8 if num_cpu > 10 else 1


def check_inpath(inp, strict=True):
    """Helper to check if given path exists and cast it to pathlikes."""
    return pt(inp).resolve(strict)


def _parse_args():
    """python3 unrpyc.py [-c] [-d] [--python-screens|--ast-screens|--no-screens] file [file ...]"""

    _cc_num = set_cpu_num()
    _ap = argparse.ArgumentParser(description="Decompile .rpyc/.rpymc files")

    _ap.add_argument(
        'file',
        type=check_inpath,
        nargs='+',
        help="The filenames to decompile. "
        "All .rpyc files in any sub-/directories passed will also be decompiled.")

    _ap.add_argument(
        '--try-harder',
        dest="try_harder",
        action="store_true",
        help="Tries some workarounds against common obfuscation methods. This is a lot slower.")

    _ap.add_argument(
        '-c',
        '--clobber',
        dest='clobber',
        action='store_true',
        help="overwrites existing output files")

    _ap.add_argument(
        '-d',
        '--dump',
        dest='dump',
        action='store_true',
        help="instead of decompiling, pretty print the ast to a file")

    _ap.add_argument(
        '-p',
        '--processes',
        dest='processes',
        action='store',
        type=int,
        choices=list(range(1, _cc_num)),
        default=_cc_num,
        help="use the specified number or processes to decompile."
        "Defaults to the amount of hw threads available minus one, disabled when muliprocessing "
        "unavailable is.")

    _ap.add_argument(
        '-t',
        '--translation-file',
        dest='translation_file',
        action='store',
        default=None,
        help="use the specified file to translate during decompilation")

    _ap.add_argument(
        '-T',
        '--write-translation-file',
        dest='write_translation_file',
        action='store',
        default=None,
        help="store translations in the specified file instead of decompiling")

    _ap.add_argument(
        '-l',
        '--language',
        dest='language',
        action='store',
        default='english',
        help="if writing a translation file, the language of the translations to write")

    _ap.add_argument(
        '--comparable',
        dest='comparable',
        action='store_true',
        help="Only for dumping, remove several false differences when comparing dumps. "
        "This suppresses attributes that are different even when the code is identical, such as "
        "file modification times. ")

    _ap.add_argument(
        '--no-pyexpr',
        dest='no_pyexpr',
        action='store_true',
        help="Only for dumping, disable special handling of PyExpr objects, instead printing them "
        "as strings. This is useful when comparing dumps from different versions of Ren'Py. It "
        "should only be used if necessary, since it will cause loss of information such as line "
        "numbers.")

    _ap.add_argument(
        '--no-init-offset',
        dest='init_offset',
        action='store_false',
        help="By default, unrpyc attempt to guess when init offset statements were used and insert "
        "them. This is always safe to do for ren'py 8, but as it is based on a heuristic it can be "
        "disabled. The generated code is exactly equivalent, only slightly more cluttered.")

    _ap.add_argument(
        '--register-sl-displayable',
        dest="sl_custom_names",
        type=str,
        nargs='+',
        help="Accepts mapping separated by '=', "
        "where the first argument is the name of the user-defined displayable object, "
        "and the second argument is a string containing the name of the displayable,"
        "potentially followed by a '-', and the amount of children the displayable takes"
        "(valid options are '0', '1' or 'many', with 'many' being the default)")

    return _ap.parse_args()


def main(args):
    """Main execution..."""
    # NOTE: Code for file/dir work refactored to pathlib usage
    if not sys.version_info[:2] >= (3, 6):
        raise Exception("Must be executed in Python 3.6 or later.\n"
                        "You are running {}".format(sys.version))

    if (args.write_translation_file and not args.clobber and args.write_translation_file.exists()):
        # Fail early to avoid wasting time going through the files
        print("Output translation file already exists. Pass --clobber to overwrite.")
        return

    if args.translation_file:
        with args.translation_file.open('rb') as in_file:
            args.translations = in_file.read()

    if args.sl_custom_names is not None:
        try:
            args.sl_custom_names = parse_sl_custom_names(args.sl_custom_names)
        except Exception as e:
            print("\n".join(e.args))
            return

    def rpyc_check(inp):
        return bool(inp.suffix in ('.rpyc', '.rpymc') and inp.is_file())

    files = list()
    for item in args.file:
        if item.is_dir():
            for entry in item.rglob('*'):
                if rpyc_check(entry):
                    files.append(entry)
        elif rpyc_check(item):
            files.append(item)

    # Check if we actually have files. Don't worry about no parameters passed,
    # since ArgumentParser catches that
    if not files:
        print("Found no script files to decompile.")
        return

    files.sort(key=lambda x: x.stat().st_size, reverse=True)

    # changes: contextmanager; passing filesize over is unneeded; only use multiprocessing if
    # enough work
    if len(files) > 5:
        with Pool(args.processes, sharelock, [printlock]) as pool:
            results = pool.map(partial(worker, args), files, 1)

    else:
        results = list(map(partial(worker, args), files))

    if args.write_translation_file:
        print(f"Writing translations to {args.write_translation_file}...")
        translated_dialogue = {}
        translated_strings = {}
        good = 0
        bad = 0
        for result in results:
            if not result:
                bad += 1
                continue
            good += 1
            translated_dialogue.update(magic.loads(result[0], special.class_factory))
            translated_strings.update(result[1])
        with open(args.write_translation_file, 'wb') as out_file:
            magic.safe_dump((args.language, translated_dialogue, translated_strings), out_file)

    else:
        # Check per file if everything went well and report back
        good = results.count(True)
        bad = results.count(False)

    def numeri(inp):
        return 's' if inp > 1 else ''

    if bad == 0:
        print(f"Decompilation of {good} script file{numeri(good)} successful.")
    elif good == 0:
        print(f"Decompilation of {bad} file{numeri(bad)} failed.")
    else:
        print(f"Decompilation of {good} file{numeri(good)} successful,"
              f" but decompilation of {bad} file{numeri(bad)} failed.")

if __name__ == '__main__':
    main(_parse_args())
