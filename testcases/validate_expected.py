# Takes the testcases in the originals folder, and strips any comments.

import os
from os import path
import io
import argparse
import shutil
import subprocess

ROOT = path.dirname(__file__)
ORIGINAL = path.join(ROOT, "originals") # original .rpy files
EXPECTED = path.join(ROOT, "expected") # expected result from decompiling .rpyc files
COMPILED = path.join(ROOT, "compiled") # .rpyc files from compiling original

def normalize(source, dest):
    with io.open(source, "r", encoding="utf-8-sig") as fin:
        with io.open(dest, "w", encoding="utf-8", newline="\n") as fout:
            for line in fin:
                # strip out empty lines or comments
                l = line.strip()
                if not l or l.startswith("#"):
                    continue

                # strip any comments in general (yes this ignores that they might be inside a string)
                if "#" in line:
                    line, _ = line.split("#", 1)

                # strip any trailing whitespace
                fout.write(line.rstrip() + "\n")

def copy_rpy(source, dest):
    if source.endswith(".rpy"):
        shutil.copyfile(source, dest)

def process_recursively(source_dir, dest_dir, function):
    # Recursively traverses source_dir and ensures dest_dir has the same folder structure.
    # Then, calls `function(source_file, dest_file) for every file in source_dir.
    if not path.isdir(dest_dir):
        os.mkdir(dest_dir)

    for source_name in os.listdir(source_dir):
        source_item = path.join(source_dir, source_name)
        dest_item = path.join(dest_dir, source_name)

        if path.isdir(source_item):
            process_recursively(source_item, dest_item, function)

        elif path.isfile(source_item):
            function(source_item, dest_item)

def main():
    parser = argparse.ArgumentParser(description="Testcase utilities. Compares `expected` with `originals`")

    parser.add_argument('-u', '--update', dest='update', action='store_true',
                        help="update the contents of 'expected' with .rpy files found in 'compiled' before running")
    args = parser.parse_args()


    if args.update:
        process_recursively(COMPILED, EXPECTED, copy_rpy)


    temp_original = path.join(ROOT, "temp-originals")
    temp_expected = path.join(ROOT, "temp-expected")

    process_recursively(ORIGINAL, temp_original, normalize)
    process_recursively(EXPECTED, temp_expected, normalize)

    subprocess.call(["diff", "-ur", temp_original, temp_expected])

    shutil.rmtree(temp_original)
    shutil.rmtree(temp_expected)


if __name__ == '__main__':
    main()