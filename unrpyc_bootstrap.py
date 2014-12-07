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

# The bootstrapping script for unrpyc,
# instead of relying on the installed python interpreter, it simply passes execution
# on to the python intepreter included in renpy.

import argparse
import os.path as path
import os, sys
import subprocess
import itertools, glob

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

    # Figure out what platform we're on
    if sys.platform.startswith("win32"):
        librarypath = "windows-i686"
        pydpath = "Lib"
        executablename = "python.exe"
        pathsep = ";"
    elif sys.platform == "darwin":
        librarypath = "darwin-x86_64"
        pydpath = "lib/python2.7"
        executablename = "python"
        pathsep = ":"
    else: #linux, other osses
        if sys.maxsize > 2**32: # if 64 bit python
            librarypath = "linux86_64"
        else:
            librarypath = "linux-686"
        pydpath = "lib/python2.7"
        executablename = "python"
        pathsep = ":"

    # The directory containing /renpy and /lib
    base_dir = path.abspath(args.basedir)

    if not path.isdir(path.join(base_dir, "renpy")):
        raise Exception("Could not find the 'renpy' folder in the base directory")
    if not path.isdir(path.join(base_dir, "lib")):
        raise Exception("Could not find the 'lib' folder in the base directory")

    # The folder in which the actual renpy python executable lies
    executable_folder = path.join(base_dir if args.basedir else os.getcwd(), 
                                  "lib",
                                  librarypath)

    if not path.isdir(executable_folder):
        raise Exception("Could not locate the folder containing ren'py's python executable for your platform")

    # the location 
    unrpyc = path.join(path.dirname(path.abspath(__file__)), "unrpyc.py")

    # the executable itself
    executable = path.join(executable_folder, executablename)

    if not path.isfile(executable):
        raise Exception"Could not locate the ren'py python executable for your platform")

    # forward arguments
    argv = [executable, "-sSO", unrpyc, "-b", base_dir]
    if args.clobber:
        argv.append("-c")
    if args.dump:
        argv.append("-d")
    if args.pythonscreens:
        argv.append("--python-screens")
    if args.astscreens:
        argv.append("--ast-screens")
    if args.noscreens:
        argv.append("--no-screens")
    if args.screenkwargs:
        argv.append("--single-line-screen-kwargs")

    # generate absolute paths to the files to decompile
    argv.extend(
        map(path.abspath,
            itertools.chain(
                *map(glob.glob, args.file)
            )
        )
    )

    # Now we move the current working directory 
    os.chdir(executable_folder)

    # Set up the PYTHONPATH environment variable correctly so python knows where to find its libs
    os.environ["PYTHONPATH"] = path.join(base_dir, "lib", "pythonlib2.7") + pathsep + path.join(executable_folder, pydpath)

    # and call the proper python executable
    subprocess.call(argv)

if __name__ == '__main__':
    main()