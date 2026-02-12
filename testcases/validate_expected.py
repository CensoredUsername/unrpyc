# Takes the testcases in the originals folder, and strips any comments.

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

from pathlib import Path
import argparse
import shutil
import subprocess

ROOT = Path(__file__).parent
ORIGINAL = ROOT / "originals"  # original .rpy files
EXPECTED = ROOT / "expected"  # expected result from decompiling .rpyc files
COMPILED = ROOT / "compiled"  # .rpyc files from compiling original

def normalize(source: Path, dest: Path):
    with source.open("r", encoding="utf-8-sig") as fin:
        with dest.open("w", encoding="utf-8", newline="\n") as fout:
            for line in fin:
                # strip out empty lines or comments
                l = line.strip()
                if not l or l.startswith("#"):
                    continue

                # strip any comments in general (yes this ignores that they might be inside
                # a string)
                if "#" in line:
                    line, _ = line.split("#", 1)

                # strip any trailing whitespace
                fout.write(line.rstrip() + "\n")

def copy_rpy(source: Path, dest: Path):
    if source.name.endswith(".rpy"):
        with source.open("r", encoding="utf-8-sig") as fin:
            with dest.open("w", encoding="utf-8", newline="\n") as fout:
                fout.write(fin.read())

def process_recursively(source_dir, dest_dir, function):
    # Recursively traverses source_dir and ensures dest_dir has the same folder structure.
    # Then, calls `function(source_file, dest_file) for every file in source_dir.
    dest_dir.mkdir(exist_ok=True)
    for source_item in source_dir.iterdir():
        dest_item = dest_dir / source_item.name

        if source_item.is_dir():
            process_recursively(source_item, dest_item, function)

        elif source_item.is_file():
            function(source_item, dest_item)

def main():
    parser = argparse.ArgumentParser(
        description="Testcase utilities. Compares `expected` with `originals`")

    parser.add_argument(
        '-u',
        '--update',
        dest='update',
        action='store_true',
        help="Update the contents of 'expected' with .rpy files found in 'compiled' before "
        "running")
    args = parser.parse_args()


    if args.update:
        process_recursively(COMPILED, EXPECTED, copy_rpy)


    temp_original = ROOT / "temp-originals"
    temp_expected = ROOT / "temp-expected"

    process_recursively(ORIGINAL, temp_original, normalize)
    process_recursively(EXPECTED, temp_expected, normalize)

    subprocess.run(["diff", "-ur", temp_original, temp_expected])

    shutil.rmtree(temp_original)
    shutil.rmtree(temp_expected)


if __name__ == '__main__':
    main()
