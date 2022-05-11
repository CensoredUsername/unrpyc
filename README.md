# Unrpyc, the Ren'py script decompiler.

Unrpyc is a tool to decompile Ren'Py (http://www.renpy.org/) compiled .rpyc
script files. It will not extract files from .rpa archives. For that, use
[rpatool](https://github.com/Shizmob/rpatool) or
[UnRPA](https://github.com/Lattyware/unrpa).


## Status

master:[![Build Status](https://github.com/CensoredUsername/unrpyc/actions/workflows/python-app.yaml/badge.svg?branch=master)](https://github.com/CensoredUsername/unrpyc/actions/workflows/python-app.yaml)

dev:[![Build Status](https://github.com/CensoredUsername/unrpyc/actions/workflows/python-app.yaml/badge.svg?branch=dev)](https://github.com/CensoredUsername/unrpyc/actions/workflows/python-app.yaml)

## Usage

This tool can either be ran as a command line tool, as a library, or injected into the game itself. It requires Python 2.7 to be installed to be used as a command line tool.

### Command line tool usage

Depending on your system setup, you should use one of the following commands to run the tool:
```
python unrpyc.py [options] script1 script2 ...
python2 unrpyc.py [options] script1 script2 ...
py -2 unrpyc.py [options] script1 script2 ...
./unrpyc.py [options] script1 script2 ...
```

Options:
```
$ py -2 unrpyc.py --help
usage: unrpyc.py [-h] [-c] [-d] [-p {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15}]
                 [-t TRANSLATION_FILE] [-T WRITE_TRANSLATION_FILE]
                 [-l LANGUAGE] [--sl1-as-python] [--comparable] [--no-pyexpr]
                 [--tag-outside-block] [--init-offset] [--try-harder]
                 file [file ...]

Decompile .rpyc/.rpymc files

positional arguments:
  file                  The filenames to decompile. All .rpyc files in any
                        directories passed or their subdirectories will also
                        be decompiled.

optional arguments:
  -h, --help            show this help message and exit
  -c, --clobber         overwrites existing output files
  -d, --dump            instead of decompiling, pretty print the ast to a file
  -p, --processes
                        use the specified number or processes to
                        decompile.Defaults to the amount of hw threads
                        available minus one, disabled when muliprocessing is
                        unavailable.
  -t TRANSLATION_FILE, --translation-file TRANSLATION_FILE
                        use the specified file to translate during
                        decompilation
  -T WRITE_TRANSLATION_FILE, --write-translation-file WRITE_TRANSLATION_FILE
                        store translations in the specified file instead of
                        decompiling
  -l LANGUAGE, --language LANGUAGE
                        if writing a translation file, the language of the
                        translations to write
  --sl1-as-python       Only dumping and for decompiling screen language 1
                        screens. Convert SL1 Python AST to Python code instead
                        of dumping it or converting it to screenlang.
  --comparable          Only for dumping, remove several false differences
                        when comparing dumps. This suppresses attributes that
                        are different even when the code is identical, such as
                        file modification times.
  --no-pyexpr           Only for dumping, disable special handling of PyExpr
                        objects, instead printing them as strings. This is
                        useful when comparing dumps from different versions of
                        Ren'Py. It should only be used if necessary, since it
                        will cause loss of information such as line numbers.
  --tag-outside-block   Always put SL2 'tag's on the same line as 'screen'
                        rather than inside the block. This will break
                        compiling with Ren'Py 7.3 and above, but is needed to
                        get correct line numbers from some files compiled with
                        older Ren'Py versions.
  --init-offset         Attempt to guess when init offset statements were used
                        and insert them. This is always safe to enable if the
                        game's Ren'Py version supports init offset statements,
                        and the generated code is exactly equivalent, only
                        less cluttered.
  --try-harder          Tries some workarounds against common obfuscation
                        methods. This is a lot slower.

```

You can give several .rpyc files on the command line. Each script will be
decompiled to a corresponding .rpy on the same directory. Additionally, you can
pass directories. All .rpyc files in these directories or their subdirectories
will be decompiled. By default, the program will not overwrite existing files,
use -c to do that.

This script will try to disassemble all AST nodes. In the case it encounters an
unknown node type, which may be caused by an update to Ren'Py somewhere in the
future, a warning will be printed and a placeholder inserted in the script when
it finds a node it doesn't know how to handle. If you encounter this, please
open an issue to alert us of the problem.

For the script to run correctly it is required for the unrpyc.py file to be in
the same directory as the modules directory.

### Game injection

The tool can be injected directly into a running game by placing either the
`un.rpyc` file or the `bytecode.rpyb` file from the most recent release into
the `game` directory inside a Ren'py game. When the game is then ran the tool
will automatically extract and decompile all game script files into the `game`
directory. The tool writes logs to the file `unrpyc.log.txt`.

### Library usage

You can import the module from python and call
unrpyc.decompile_rpyc(filename, ...) directly.

## Notes on support

The Ren'py engine has changed a lot through the years. While this tool tries to
support all available Ren'py versions since the creation of this tool, we do not
actively test it against every engine release. Furthermore the engine does
not have perfect backwards compatibility itself, so issues can occur if you try
to run decompiled files with different engine releases. Most attention is given
to recent engine versions so if you encounter an issues with older games, please
report it.

Supported:
* renpy version 6 and 7 (current)
* Windows, OSX and Linux

## Issue reports

As Ren'py is being continuously developed itself it often occurs that this tool might
break on newer engine releases. This is most likely due to us not being
aware of these features existing in the first place. To get this fixed
you can make an issue report to this repository. However, we work on this tool
in our free time and therefore we strongly request performing the following steps when
making an issue report.

### Before making an issue report:

If you are making an issue report because decompilation errors out, please do the following.
If there's simply an error in the decompiled file, you can skip these steps.

1. Test your .rpyc files with the command line tool and both game injection methods. Please
   do this directly, do not use wrapper tools incorporating unrpyc for the report.
2. Run the command line tool with the anti-obfuscation option `--try-harder`.

### When making an issue report:

1. List the used version of unrpyc and the version of ren'py used to create the .rpyc file
   you're trying to decompile (and if applicable, what game).
2. Describe exactly what you're trying to do, and what the issue is (is it not decompiling
   at all, is there an omission in the decompiled file, or is the decompiled file invalid).
3. Attach any relevant output produced by the tool (full command line output is preferred,
   if output is generated attach that as well).
4. Attach the .rpyc file that is failing to decompile properly.

Please perform all these steps, and write your issue report in legible English. Otherwise
it is likely that your issue report will just receive a reminder to follow these steps.

## Feature and pull requests

Feature and pull requests are welcome. Feature requests will be handled whenever we feel
like it, so if you really want a feature in the tool a pull request is usually the right
way to go. Please do your best to conform to the style used by the rest of the code base
and only affect what's absolutely necessary, this keeps the process smooth.

### Notes on deobfuscation

Recently a lot of modifications of Ren'py have turned up that slightly alter the Ren'py
file format to block this tool from working. The tool now includes a basic framework
for deobfuscation, but feature requests to create deobfuscation support for specific
games are not likely to get a response from us as this is essentially just an arms race,
and it's trivial to figure out a way to obfuscate the file that blocks anything that is
supported right now. If you make a pull request with it we'll happily put it in mainline
or a game-specific branch depending on how many games it affects, but we have little
motivation ourselves to put time in this arms race.

https://github.com/CensoredUsername/unrpyc
