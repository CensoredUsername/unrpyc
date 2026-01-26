# Unrpyc, the Ren'Py script decompiler
[![Python Version][py]][l_py] [![Python Version][renpy]][l_renpy] [![MIT][b_licence]][l_licence] ![Downloads][b_downloads]<br>
**Unrpyc** is a tool to decompile Ren'Py (http://www.renpy.org) compiled .rpyc script files. It will
not extract files from .rpa archives. For that, use [rpatool](https://github.com/Shizmob/rpatool) or [UnRPA](https://github.com/Lattyware/unrpa).

## Status
![Python Version][b_py3] [![Latest Version][b_release_2]][l_releases] [![check][b_check_master]][l_workflow] [![check][b_check_dev]][l_workflow]<br>
![Python Version][b_py2] [![Latest Version][b_release_1]][l_releases] [![check][b_check_legacy]][l_workflow] [![check][b_check_legacy_dev]][l_workflow]

<!-- Badge-link prefixe: b_ = badge source; l_ = link source -->

[py]: https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff&style=flat-square
[l_py]: https://python.org
[renpy]: https://img.shields.io/badge/Ren'Py-ac6464?logo=renpy&logoColor=fff&style=flat-square
[l_renpy]: https://renpy.org
<!-- Licence -->
[b_licence]: https://img.shields.io/badge/license-MIT-yellow?style=flat-square&color=darkred
[l_licence]: LICENSE
<!-- Download count -->
[b_downloads]: https://img.shields.io/github/downloads/CensoredUsername/unrpyc/total?style=flat-square&color=darkgreen
<!-- Python minimal version info -->
[b_py3]: https://img.shields.io/badge/3.9-gold?style=flat-square&logo=python&logoColor=fff&labelColor=3776AB
[b_py2]: https://img.shields.io/badge/2.7-gold?style=flat-square&logo=python&logoColor=fff&labelColor=3776AB
<!-- Release version info -->
[b_release_2]: https://img.shields.io/github/v/release/CensoredUsername/unrpyc?style=flat-square
[b_release_1]: https://img.shields.io/github/v/release/CensoredUsername/unrpyc?filter=v1*&style=flat-square
[l_releases]: https://github.com/CensoredUsername/unrpyc/releases
<!-- Tests -->
[b_check_master]: https://img.shields.io/github/actions/workflow/status/CensoredUsername/unrpyc/python-app.yaml?branch=master&style=flat-square&logo=github&label=Tests:%20master
[b_check_dev]: https://img.shields.io/github/actions/workflow/status/CensoredUsername/unrpyc/python-app.yaml?branch=dev&style=flat-square&logo=github&label=Tests:%20dev
[b_check_legacy]: https://img.shields.io/github/actions/workflow/status/CensoredUsername/unrpyc/python-app.yaml?branch=legacy&style=flat-square&logo=github&label=Tests:%20legacy
[b_check_legacy_dev]: https://img.shields.io/github/actions/workflow/status/CensoredUsername/unrpyc/python-app.yaml?branch=legacy-dev&style=flat-square&logo=github&label=Tests:%20legacy-dev
[l_workflow]: https://github.com/CensoredUsername/unrpyc/actions/workflows/python-app.yaml

## Usage
This tool can either be ran as a command line tool, as a library, or injected into the game itself.
To use it as a command line tool, a local python installation is required. To use it for its
default function (decompiling) you can simply pass it the files you want to decompile as arguments,
or pass it the folder containing them. For example, `python unrpyc.py file1.rpyc file2.rpyc` or
`python unrpyc.py folder/`.

### Additional features
#### Translation:
For easier reading of decompiled script files, unrpyc can use translation data contained in a game
to automatically convert the emitted script files to another language. You can find the supported
languages for a game by looking in the `game/tl` folder of said game (`None` being the default)

To use this feature, simply pass the name of the target language (which has to match the name found
in the tl folder) with the `-t`/`--translate` option. For example, if a game has a folder
`path/to/renpyapp/game/tl/french`, then you can run the command:
`python unrpyc.py /path/to/renpyapp/ -t french`

#### Raw ast view:
Instead of decompiling, the tool can simply show the contents of a rpyc file. This is mainly useful
for bug reports and the development of unrpyc. You can pass the `-d`/`--dump` flag to activate this
feature.

Note: this generates a _lot_ of output.

## Compatibility
You are currently reading the documentation for the `master` branch of this tool. *Ren'Py* switched
to using Python 3 in *Ren'Py 8*. This required significant changes to the decompiler, and
necessitated splitting it into two to maintain support for older games. Development and releases
for this tool are now split into the `master` branch (Unrpyc v2.x, using Python 3) and the
`legacy` branch (Unrpyc v1.x, using Python 2). Additionally, support for some very ancient *Ren'Py*
features has been dropped from the `master` branch to simplify continued development of unrpyc.
In practice this means that games before Ren'Py `6.18.0` are no longer supported by the
`master` branch, and games from before `6.99.10` should use the `--no-init-offset` option. Any
game using *Ren'Py* versions before `6.18.0` should instead use the `legacy` branch of unrpyc,
which supports up to and including *Ren'Py 7*.

When using the injectors (`un.rpyc`, `un.rpy`, `bytecode.rpyb`), compatibility is more stringent,
as these tools use the python version bundled by *Ren'Py*. Use un.rpyc v2 (`2.*.*`) for Ren'Py 8
games, and un.rpyc v1 (`1.*.*`) for *Ren'Py* 7 and 6.

Summarized:
- unrpyc v2:
  - Requires python `3.9` or above to work.
  - Releases use version numbers `2.x`
  - Uses branches `master` for the last release, and `dev` for development.
  - Command line supports *Ren'Py* `8.x` (most recent) down to `6.18.0` (below `6.99.10` requires
  option --no-init-offset)*
    - Injectors (`un.rpyc` and friends) support only *Ren'Py* `8.x`

- unrpyc v1:
  - Requires python `2.7` to work.
  - Releases use version numbers `1.x`
  - Uses branches `legacy` for the last release, and `legacy-dev` for development.
  - Command line supports Ren'Py `7.x` (most recent) and *Ren'Py* `6.x`.
  - Injectors (`un.rpyc` and friends) support *Ren'Py* `6.x` and `7.x`.

*Ren'Py 5* or earlier are not supported currently.

### Command line tool usage
Depending on your system setup, you should use one of the following commands to run the tool:
```
python unrpyc.py [options] script1 script2 ...
python3 unrpyc.py [options] script1 script2 ...
py -3 unrpyc.py [options] script1 script2 ...
./unrpyc.py [options] script1 script2 ...
```

Options:
```
$ py -3 unrpyc.py --help
usage: unrpyc.py [-h] [-c] [--try-harder] [-p {int}] [-d]
                 [--comparable] [--no-pyexpr] [--no-init-offset]
                 [--register-sl-displayable SL_CUSTOM_NAMES [SL_CUSTOM_NAMES ...]] [-t TRANSLATE]
                 [--version]
                 file [file ...]

Decompile .rpyc/.rpymc files

positional arguments:
  file                  The filenames to decompile. All .rpyc files in any sub-/directories passed
                        will also be decompiled.

options:
  -h, --help            show this help message and exit
  -c, --clobber         Overwrites output files if they already exist.
  --try-harder          Tries some workarounds against common obfuscation methods. This is a lot
                        slower.
  -p, --processes {int}
                        Use the specified number or processes to decompile. Defaults to the amount
                        of hw threads available minus one, disabled when muliprocessing is
                        unavailable.
  --no-init-offset      By default, unrpyc attempts to guess when init offset statements were used
                        and insert them. This is always safe to do for ren'py 8, but as it is
                        based on a heuristic it can be disabled. The generated code is exactly
                        equivalent, only slightly more cluttered.
  --register-sl-displayable SL_CUSTOM_NAMES [SL_CUSTOM_NAMES ...]
                        Accepts mapping separated by '=', where the first argument is the name of
                        the user-defined displayable object, and the second argument is a string
                        containing the name of the displayable, potentially followed by a '-', and
                        the amount of children the displayable takes(valid options are '0', '1' or
                        'many', with 'many' being the default)
  -t, --translate TRANSLATE
                        Changes the dialogue language in the decompiled script files, using a
                        translation already present in the tl dir.
  --version             show program's version number and exit

astdump options:
  All unrpyc options related to ast-dumping.

  -d, --dump            Instead of decompiling, pretty print the ast to a file
  --comparable          Only for dumping, remove several false differences when comparing dumps.
                        This suppresses attributes that are different even when the code is
                        identical, such as file modification times.
  --no-pyexpr           Only for dumping, disable special handling of PyExpr objects, instead
                        printing them as strings. This is useful when comparing dumps from
                        different versions of Ren'Py. It should only be used if necessary, since
                        it will cause loss of information such as line numbers.

```

You can give several .rpyc files on the command line. Each script will be decompiled to a
corresponding .rpy on the same directory. Additionally, you can pass directories. All .rpyc files
in these directories or their subdirectories will be decompiled. By default, the program will not
overwrite existing files, use option `-c` to do that.

This script will try to disassemble all AST nodes. In the case it encounters an unknown node type,
which may be caused by an update to *Ren'Py* somewhere in the future, a warning will be printed and
a placeholder inserted in the script when it finds a node it doesn't know how to handle. If you
encounter this, please open an issue to alert us of the problem.

For the script to run correctly it is required for the unrpyc.py file to be in the same directory
as the modules directory.

### Game injection
The tool can be injected directly into a running game by placing either the `un.rpyc` file or the
`bytecode.rpyb` file from the most recent release into the `game` directory inside a Ren'Py game.
When the game is then ran the tool will automatically extract and decompile all game script files
into the `game` directory. The tool writes logs to the file `unrpyc.log.txt`.

### Library usage
You can import the module from python and call unrpyc.decompile_rpyc(filename, ...) directly.

warning: this has changed with python 3 and might not work. This is under active development.

## Notes on support
The *Ren'Py* engine has changed a lot through the years. While this tool tries to support all
available *Ren'Py* versions since the creation of this tool, we do not actively test it against
every engine release. Furthermore the engine does not have perfect backwards compatibility itself,
so issues can occur if you try to run decompiled files with different engine releases. Most
attention is given to recent engine versions so if you encounter an issues with older games, please
report it.

Additionally, with the jump to python 3 in *Ren'Py 8*, it became difficult to support all *Ren'Py*
versions with a single tool. Therefore, please consult the compatibility section above to find out
which version of the tool you need.

## Issue reports
As *Ren'Py* is being continuously developed itself it often occurs that this tool might break on
newer engine releases. This is most likely due to us not being aware of these features existing in
the first place. To get this fixed you can make an issue report to this repository. However, we
work on this tool in our free time and therefore we strongly request performing the following steps
when making an issue report.

### Before making an issue report:
If you are making an issue report because decompilation errors out, please do the following.
(If there's simply an error in the decompiled file, you can skip these steps.)

1. Test your .rpyc files with the command line tool and both game injection methods. Please do this
directly, do not use wrapper tools incorporating unrpyc for the report.
2. Run the command line tool with the anti-obfuscation option `--try-harder`.

### When making an issue report:
1. List the used version of unrpyc and the version of *Ren'Py* used to create the .rpyc file you're
trying to decompile (and if applicable, what game).
2. Describe exactly what you're trying to do, and what the issue is (is it not decompiling at all,
is there an omission in the decompiled file, or is the decompiled file invalid).
3. Attach any relevant output produced by the tool (full command line output is preferred, if
output is generated attach that as well).
4. Attach the .rpyc file that is failing to decompile properly.

Please perform all these steps, and write your issue report in legible English. Otherwise it is
likely that your issue report will just receive a reminder to follow these steps.

## Feature and pull requests
Feature and pull requests are welcome. Feature requests will be handled whenever we feel like it,
so if you really want a feature in the tool a pull request is usually the right way to go. Please
do your best to conform to the style used by the rest of the code base and only affect what's
absolutely necessary, this keeps the process smooth.

### Notes on deobfuscation
Recently a lot of modifications of *Ren'Py* have turned up that slightly alter the *Ren'Py* file
format to block this tool from working. The tool now includes a basic framework for deobfuscation,
but feature requests to create deobfuscation support for specific games are not likely to get a
response from us as this is essentially just an arms race, and it's trivial to figure out a way to
obfuscate the file that blocks anything that is supported right now. If you make a pull request
with it we'll happily put it in mainline or a game-specific branch depending on how many games it
affects, but we have little motivation ourselves to put time in this arms race.

https://github.com/CensoredUsername/unrpyc
