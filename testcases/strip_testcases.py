# Takes the testcases in the originals folder, and strips any comments.

from pathlib import Path


def normalize(infile: Path, outfile: Path):
    with infile.open("r", encoding="utf-8-sig") as fin:
        with outfile.open("w", encoding="utf-8", newline="\n") as fout:
            for line in fin:
                if line.lstrip().startswith("#"):
                    fout.write("\n")
                elif not line.strip():
                    fout.write("\n")
                else:
                    fout.write(line.rstrip())
                    fout.write("\n")

            fout.write("# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc\n")

def main():
    # Originals are stored as originals/*/*.orig.rpyc
    # strip comments and store the result as stripped/*/*.rpyc

    orig_folder = Path(__file__).parent / "originals"
    stripped_folder = Path(__file__).parent / "stripped"
    stripped_folder.mkdir(exist_ok=True)

    for folder in orig_folder.iterdir():
        # ensure the destination directories exist
        destfolder = stripped_folder / folder.name
        destfolder.mkdir(exist_ok=True)

        for file in folder.iterdir():
            if file.name.endswith(".rpy"):
                destfile = destfolder / file.name
                normalize(file, destfile)

if __name__ == '__main__':
    main()