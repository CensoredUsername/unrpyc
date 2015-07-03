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

from __future__ import unicode_literals
from util import DecompilerBase, First, WordConcatenator, reconstruct_paraminfo, \
                 reconstruct_arginfo, string_escape, split_logical_lines, Dispatcher

from operator import itemgetter

import magic
magic.fake_package(b"renpy")
import renpy

import screendecompiler
import sl2decompiler
import codegen
import astdump

__all__ = ["astdump", "codegen", "magic", "screendecompiler", "sl2decompiler", "util", "pprint", "Decompiler"]

# Main API

def pprint(out_file, ast, indent_level=0,
           decompile_python=False, line_numbers=False):
    Decompiler(out_file,
               decompile_python=decompile_python,
               match_line_numbers=line_numbers).dump(ast, indent_level)

# Implementation

class Decompiler(DecompilerBase):
    """
    An object which hanldes the decompilation of renpy asts to a given stream
    """

    # This dictionary is a mapping of Class: unbount_method, which is used to determine
    # what method to call for which ast class
    dispatch = Dispatcher()

    def __init__(self, out_file=None, decompile_python=False,
                 indentation = '    ', match_line_numbers=False):
        super(Decompiler, self).__init__(out_file, indentation, match_line_numbers)
        self.decompile_python = decompile_python

        self.paired_with = False
        self.say_inside_menu = None
        self.label_inside_menu = None

    def dump(self, ast, indent_level=0):
        if not self.match_line_numbers:
            self.write("# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc")
        # Avoid an initial blank line if we don't write out the above banner
        super(Decompiler, self).dump(ast, indent_level, skip_indent_until_write=self.match_line_numbers)
        self.write("\n") # end file with a newline

    def print_node(self, ast):
        # We special-case line advancement for TranslateString in its print
        # method, so don't advance lines for it here.
        if hasattr(ast, 'linenumber') and not isinstance(ast, renpy.ast.TranslateString):
            self.advance_to_line(ast.linenumber)
        # It doesn't matter what line "block:" is on. The loc of a RawBlock
        # refers to the first statement inside the block, which we advance
        # to from print_atl.
        elif hasattr(ast, 'loc') and not isinstance(ast, renpy.atl.RawBlock):
            self.advance_to_line(ast.loc[1])
        func = self.dispatch.get(type(ast), None)
        if func:
            func(self, ast)
        else:
            # This node type is unknown
            self.print_unknown(ast)

    # ATL printing functions

    def print_atl(self, ast):
        self.advance_to_line(ast.loc[1])
        self.indent_level += 1
        if ast.statements:
            self.print_nodes(ast.statements)
        # If a statement ends with a colon but has no block after it, loc will
        # get set to ('', 0). That isn't supposed to be valid syntax, but it's
        # the only thing that can generate that.
        elif not self.match_line_numbers or ast.loc != ('', 0):
            self.indent()
            self.write("pass")
        self.indent_level -= 1

    @dispatch(renpy.atl.RawMultipurpose)
    def print_atl_rawmulti(self, ast):
        self.indent()
        words = WordConcatenator(False) # TODO: Make this allow reordering too

        # warpers
        if ast.warp_function:
            words.append("warp", ast.warp_function, ast.duration)
        elif ast.warper:
            words.append(ast.warper, ast.duration)
        elif ast.duration != "0":
            words.append("pause", ast.duration)

        # revolution
        if ast.revolution:
            words.append(ast.revolution)

        # circles
        if ast.circles != "0":
            words.append("circles", ast.circles)

        # splines
        for name, expressions in ast.splines:
            words.append(name)
            for expression in expressions:
                words.append("knot", expression)

        # properties
        for key, value in ast.properties:
            words.append(key, value)

        # with
        for (expression, with_expression) in ast.expressions:
            words.append(expression)
            if with_expression:
                words.append("with", with_expression)

        self.write(words.join())

    @dispatch(renpy.atl.RawBlock)
    def print_atl_rawblock(self, ast):
        self.indent()
        self.write("block:")
        self.print_atl(ast)

    @dispatch(renpy.atl.RawChild)
    def print_atl_rawchild(self, ast):
        for child in ast.children:
            self.indent()
            self.write("contains:")
            self.print_atl(child)

    @dispatch(renpy.atl.RawChoice)
    def print_atl_rawchoice(self, ast):
        for chance, block in ast.choices:
            self.indent()
            self.write("choice")
            if chance != "1.0":
                self.write(" %s" % chance)
            self.write(":")
            self.print_atl(block)
        if (self.index + 1 < len(self.block) and
            isinstance(self.block[self.index + 1], renpy.atl.RawChoice)):
            self.indent()
            self.write("pass")

    @dispatch(renpy.atl.RawContainsExpr)
    def print_atl_rawcontainsexpr(self, ast):
        self.indent()
        self.write("contains %s" % ast.expression)

    @dispatch(renpy.atl.RawEvent)
    def print_atl_rawevent(self, ast):
        self.indent()
        self.write("event %s" % ast.name)

    @dispatch(renpy.atl.RawFunction)
    def print_atl_rawfunction(self, ast):
        self.indent()
        self.write("function %s" % ast.expr)

    @dispatch(renpy.atl.RawOn)
    def print_atl_rawon(self, ast):
        for name, block in sorted(ast.handlers.items(),
                                  key=lambda i: i[1].loc[1]):
            self.indent()
            self.write("on %s:" % name)
            self.print_atl(block)

    @dispatch(renpy.atl.RawParallel)
    def print_atl_rawparallel(self, ast):
        for block in ast.blocks:
            self.indent()
            self.write("parallel:")
            self.print_atl(block)
        if (self.index + 1 < len(self.block) and
            isinstance(self.block[self.index + 1], renpy.atl.RawParallel)):
            self.indent()
            self.write("pass")

    @dispatch(renpy.atl.RawRepeat)
    def print_atl_rawrepeat(self, ast):
        self.indent()
        self.write("repeat")
        if ast.repeats:
            self.write(" %s" % ast.repeats) # not sure if this is even a string

    @dispatch(renpy.atl.RawTime)
    def print_atl_rawtime(self, ast):
        self.indent()
        self.write("time %s" % ast.time)

    # Displayable related functions

    def print_imspec(self, imspec):
        if imspec[1] is not None:
            begin = "expression %s" % imspec[1]
        else:
            begin = " ".join(imspec[0])

        words = WordConcatenator(begin and begin[-1] != ' ', True)
        if imspec[2] is not None:
            words.append("as %s" % imspec[2])

        if len(imspec[6]) > 0:
            words.append("behind %s" % ', '.join(imspec[6]))

        if imspec[4] != "master":
            words.append("onlayer %s" % imspec[4])

        if imspec[5] is not None:
            words.append("zorder %s" % imspec[5])

        if len(imspec[3]) > 0:
            words.append("at %s" % ', '.join(imspec[3]))

        self.write(begin + words.join())
        return words.needs_space

    @dispatch(renpy.ast.Image)
    def print_image(self, ast):
        self.indent()
        self.write("image %s" % ' '.join(ast.imgname))
        if ast.code is not None:
            self.write(" = %s" % ast.code.source)
        else:
            if hasattr(ast, "atl") and ast.atl is not None:
                self.write(":")
                self.print_atl(ast.atl)

    @dispatch(renpy.ast.Transform)
    def print_transform(self, ast):
        self.indent()
        self.write("transform %s" % ast.varname)
        if ast.parameters is not None:
            self.write(reconstruct_paraminfo(ast.parameters))

        if hasattr(ast, "atl") and ast.atl is not None:
            self.write(":")
            self.print_atl(ast.atl)

    # Directing related functions

    @dispatch(renpy.ast.Show)
    def print_show(self, ast):
        self.indent()
        self.write("show ")
        needs_space = self.print_imspec(ast.imspec)

        if self.paired_with:
            if needs_space:
                self.write(" ")
            self.write("with %s" % self.paired_with)
            self.paired_with = True

        if hasattr(ast, "atl") and ast.atl is not None:
            self.write(":")
            self.print_atl(ast.atl)

    @dispatch(renpy.ast.ShowLayer)
    def print_showlayer(self, ast):
        self.indent()
        self.write("show layer %s" % ast.layer)

        if ast.at_list:
            self.write(" at %s" % ', '.join(ast.at_list))

        if hasattr(ast, "atl") and ast.atl is not None:
            self.write(":")
            self.print_atl(ast.atl)

    @dispatch(renpy.ast.Scene)
    def print_scene(self, ast):
        self.indent()
        self.write("scene")

        if ast.imspec is None:
            if ast.layer != "master":
                self.write(" onlayer %s" % ast.layer)
            needs_space = True
        else:
            self.write(" ")
            needs_space = self.print_imspec(ast.imspec)

        if self.paired_with:
            if needs_space:
                self.write(" ")
            self.write("with %s" % self.paired_with)
            self.paired_with = True

        if hasattr(ast, "atl") and ast.atl is not None:
            self.write(":")
            self.print_atl(ast.atl)

    @dispatch(renpy.ast.Hide)
    def print_hide(self, ast):
        self.indent()
        self.write("hide ")
        needs_space = self.print_imspec(ast.imspec)
        if self.paired_with:
            if needs_space:
                self.write(" ")
            self.write("with %s" % self.paired_with)
            self.paired_with = True

    @dispatch(renpy.ast.With)
    def print_with(self, ast):
        # the 'paired' attribute indicates that this with
        # and with node afterwards are part of a postfix
        # with statement. detect this and process it properly
        if hasattr(ast, "paired") and ast.paired is not None:
            # Sanity check. check if there's a matching with statement two nodes further
            if not(isinstance(self.block[self.index + 2], renpy.ast.With) and
                   self.block[self.index + 2].expr == ast.paired):
                raise Exception("Unmatched paired with {0} != {1}".format(
                                repr(self.paired_with), repr(ast.expr)))

            self.paired_with = ast.paired

        elif self.paired_with:
            # Check if it was consumed by a show/scene statement
            if self.paired_with is not True:
                self.write(" with %s" % ast.expr)
            self.paired_with = False
        else:
            self.indent()
            self.write("with %s" % ast.expr)
            self.paired_with = False

    # Flow control

    @dispatch(renpy.ast.Label)
    def print_label(self, ast):
        # If a Call block preceded us, it printed us as "from"
        if (self.index and isinstance(self.block[self.index - 1], renpy.ast.Call)):
            return
        remaining_blocks = len(self.block) - self.index
        # See if we're the label for a menu, rather than a standalone label.
        if remaining_blocks > 1 and not ast.block and ast.parameters is None:
            next_ast = self.block[self.index + 1]
            if isinstance(next_ast, renpy.ast.Menu) or (remaining_blocks > 2 and
                isinstance(next_ast, renpy.ast.Say) and
                self.say_belongs_to_menu(next_ast, self.block[self.index + 2])):
                self.label_inside_menu = ast
                return
        self.indent()
        self.write("label %s%s:" % (ast.name, reconstruct_paraminfo(ast.parameters)))
        self.print_nodes(ast.block, 1)

    @dispatch(renpy.ast.Jump)
    def print_jump(self, ast):
        self.indent()
        self.write("jump ")
        if ast.expression:
            self.write("expression %s" % ast.target)
        else:
            self.write(ast.target)

    @dispatch(renpy.ast.Call)
    def print_call(self, ast):
        self.indent()
        words = WordConcatenator(False)
        words.append("call")
        if ast.expression:
            words.append("expression")
        words.append(ast.label)

        if ast.arguments is not None:
            if ast.expression:
                words.append("pass")
            words.append(reconstruct_arginfo(ast.arguments))

        # We don't have to check if there's enough elements here,
        # since a Label or a Pass is always emitted after a Call.
        next_block = self.block[self.index + 1]
        if isinstance(next_block, renpy.ast.Label):
            words.append("from %s" % next_block.name)

        self.write(words.join())

    @dispatch(renpy.ast.Return)
    def print_return(self, ast):
        if (ast.expression is None and self.parent is None and
            self.index + 1 == len(self.block) and self.index and
            ast.linenumber == self.block[self.index - 1].linenumber):
            # As of Ren'Py commit 356c6e34, a return statement is added to
            # the end of each rpyc file. Don't include this in the source.
            return

        self.indent()
        self.write("return")

        if ast.expression is not None:
            self.write(" %s" % ast.expression)

    @dispatch(renpy.ast.If)
    def print_if(self, ast):
        statement = First("if %s:", "elif %s:")

        for i, (condition, block) in enumerate(ast.entries):
            # The non-Unicode string "True" is the condition for else:.
            if (i + 1) == len(ast.entries) and isinstance(condition, str):
                self.indent()
                self.write("else:")
            else:
                self.advance_to_line(condition.linenumber)
                self.indent()
                self.write(statement() % condition)

            self.print_nodes(block, 1)

    @dispatch(renpy.ast.While)
    def print_while(self, ast):
        self.indent()
        self.write("while %s:" % ast.condition)

        self.print_nodes(ast.block, 1)

    @dispatch(renpy.ast.Pass)
    def print_pass(self, ast):
        if (self.index and
            isinstance(self.block[self.index - 1], renpy.ast.Call)):
            return

        if (self.index > 1 and
            isinstance(self.block[self.index - 2], renpy.ast.Call) and
            isinstance(self.block[self.index - 1], renpy.ast.Label) and
            self.block[self.index - 2].linenumber == ast.linenumber):
            return

        self.indent()
        self.write("pass")

    def should_come_before(self, first, second):
        return self.match_line_numbers and first.linenumber < second.linenumber

    @dispatch(renpy.ast.Init)
    def print_init(self, ast):
        # A bunch of statements can have implicit init blocks
        # Define has a default priority of 0, screen of -500 and image of 990
        if len(ast.block) == 1 and (
            (ast.priority == -500 and isinstance(ast.block[0], renpy.ast.Screen)) or
            (ast.priority == 0 and isinstance(ast.block[0], (renpy.ast.Define,
                                                             renpy.ast.Transform,
                                                             renpy.ast.Style))) or
            (ast.priority == 990 and isinstance(ast.block[0], renpy.ast.Image))) and not (
            self.should_come_before(ast, ast.block[0])):
            # If they fulfil this criteria we just print the contained statement
            self.print_nodes(ast.block)

        # translatestring statements are split apart and put in an init block.
        elif (len(ast.block) > 0 and
                ast.priority == 0 and
                all(isinstance(i, renpy.ast.TranslateString) for i in ast.block) and
                all(i.language == ast.block[0].language for i in ast.block[1:])):
            self.print_nodes(ast.block)

        else:
            self.indent()
            self.write("init")
            if ast.priority:
                self.write(" %d" % ast.priority)

            if len(ast.block) == 1 and ast.linenumber >= ast.block[0].linenumber:
                self.write(" ")
                self.skip_indent_until_write = True
                self.print_nodes(ast.block)
            else:
                self.write(":")
                self.print_nodes(ast.block, 1)

    @dispatch(renpy.ast.Menu)
    def print_menu(self, ast):
        self.indent()
        self.write("menu")
        if self.label_inside_menu is not None:
            self.write(" %s" % self.label_inside_menu.name)
            self.label_inside_menu = None
        self.write(":")
        self.indent_level += 1

        if self.say_inside_menu is not None:
            self.print_say(self.say_inside_menu, inmenu=True)
            self.say_inside_menu = None

        if ast.with_ is not None:
            self.indent()
            self.write("with %s" % ast.with_)

        if ast.set is not None:
            self.indent()
            self.write("set %s" % ast.set)

        for label, condition, block in ast.items:
            if isinstance(condition, unicode):
                self.advance_to_line(condition.linenumber)
            self.indent()
            self.write('"%s"' % string_escape(label))

            if block is not None:
                if isinstance(condition, unicode):
                    self.write(" if %s" % condition)

                self.write(":")

                self.print_nodes(block, 1)

        self.indent_level -= 1

    # Programming related functions

    @dispatch(renpy.ast.Python)
    def print_python(self, ast, early=False):
        self.indent()

        code = ast.code.source
        if code[0] == '\n':
            code = code[1:]
            self.write("python")
            if early:
                self.write(" early")
            if ast.hide:
                self.write(" hide")
            if hasattr(ast, "store") and ast.store != "store":
                self.write(" in ")
                # Strip prepended "store."
                self.write(ast.store[6:])
            self.write(":")

            self.indent_level += 1
            self.write_lines(split_logical_lines(code))
            self.indent_level -= 1

        else:
            self.write("$ %s" % code)

    @dispatch(renpy.ast.EarlyPython)
    def print_earlypython(self, ast):
        self.print_python(ast, early=True)

    @dispatch(renpy.ast.Define)
    def print_define(self, ast):
        self.indent()
        if not hasattr(ast, "store") or ast.store == "store":
            self.write("define %s = %s" % (ast.varname, ast.code.source))
        else:
            self.write("define %s.%s = %s" % (ast.store[6:], ast.varname, ast.code.source))

    # Specials

    # Returns whether a Say statement immediately preceding a Menu statement
    # actually belongs inside of the Menu statement.
    def say_belongs_to_menu(self, say, menu):
        return (not say.interact and say.who is not None and
            say.with_ is None and say.attributes is None and
            isinstance(menu, renpy.ast.Menu) and
            menu.items[0][2] is not None and
            not self.should_come_before(say, menu))

    @dispatch(renpy.ast.Say)
    def print_say(self, ast, inmenu=False):
        if (not inmenu and self.index + 1 < len(self.block) and
            self.say_belongs_to_menu(ast, self.block[self.index + 1])):
            self.say_inside_menu = ast
            return
        self.indent()
        if ast.who is not None:
            self.write("%s " % ast.who)
        if hasattr(ast, 'attributes') and ast.attributes is not None:
            for i in ast.attributes:
                self.write("%s " % i)
        self.write('"%s"' % string_escape(ast.what))
        if not ast.interact and not inmenu:
            self.write(" nointeract")
        if ast.with_ is not None:
            self.write(" with %s" % ast.with_)

    @dispatch(renpy.ast.UserStatement)
    def print_userstatement(self, ast):
        self.indent()
        self.write(ast.line)

    @dispatch(renpy.ast.Style)
    def print_style(self, ast):
        keywords = {ast.linenumber: WordConcatenator(False, True)}

        # These don't store a line number, so just put them on the first line
        if ast.parent is not None:
            keywords[ast.linenumber].append("is %s" % ast.parent)
        if ast.clear:
            keywords[ast.linenumber].append("clear")
        if ast.take is not None:
            keywords[ast.linenumber].append("take %s" % ast.take)
        for delname in ast.delattr:
            keywords[ast.linenumber].append("del %s" % delname)

        # These do store a line number
        if ast.variant is not None:
            if ast.variant.linenumber not in keywords:
                keywords[ast.variant.linenumber] = WordConcatenator(False)
            keywords[ast.variant.linenumber].append("variant %s" % ast.variant)
        for key, value in ast.properties.iteritems():
            if value.linenumber not in keywords:
                keywords[value.linenumber] = WordConcatenator(False)
            keywords[value.linenumber].append("%s %s" % (key, value))

        keywords = sorted([(k, v.join()) for k, v in keywords.items()],
                          key=itemgetter(0))
        self.indent()
        self.write("style %s" % ast.style_name)
        if keywords[0][1]:
            self.write(" %s" % keywords[0][1])
        if len(keywords) > 1:
            self.write(":")
            self.indent_level += 1
            for i in keywords[1:]:
                self.advance_to_line(i[0])
                self.indent()
                self.write(i[1])
            self.indent_level -= 1

    # Translation functions

    @dispatch(renpy.ast.Translate)
    def print_translate(self, ast):
        self.indent()
        self.write("translate %s %s:" % (ast.language or "None", ast.identifier))

        self.print_nodes(ast.block, 1)

    @dispatch(renpy.ast.EndTranslate)
    def print_endtranslate(self, ast):
        # an implicitly added node which does nothing...
        pass

    @dispatch(renpy.ast.TranslateString)
    def print_translatestring(self, ast):
        # Was the last node a translatestrings node?
        if not(self.index and
               isinstance(self.block[self.index - 1], renpy.ast.TranslateString) and
               self.block[self.index - 1].language == ast.language):
            self.indent()
            self.write("translate %s strings:" % ast.language or "None")

        # TranslateString's linenumber refers to the line with "old", not to the
        # line with "translate %s strings:"
        self.advance_to_line(ast.linenumber)
        self.indent_level += 1

        self.indent()
        self.write('old "%s"' % string_escape(ast.old))
        self.indent()
        self.write('new "%s"' % string_escape(ast.new))

        self.indent_level -= 1

    @dispatch(renpy.ast.TranslateBlock)
    def print_translateblock(self, ast):
        self.indent()
        self.write("translate %s " % (ast.language or "None"))

        self.skip_indent_until_write = True
        self.print_nodes(ast.block)

    # Screens

    @dispatch(renpy.ast.Screen)
    def print_screen(self, ast):
        screen = ast.screen
        if isinstance(screen, renpy.screenlang.ScreenLangScreen):
            self.linenumber = screendecompiler.pprint(self.out_file, screen, self.indent_level,
                                    self.linenumber,
                                    self.decompile_python,
                                    self.match_line_numbers, self.skip_indent_until_write)
            self.skip_indent_until_write = False

        elif isinstance(screen, renpy.sl2.slast.SLScreen):
            self.linenumber = sl2decompiler.pprint(self.out_file, screen, self.indent_level,
                                    self.linenumber,
                                    self.match_line_numbers, self.skip_indent_until_write)
            self.skip_indent_until_write = False
        else:
            self.print_unknown(screen)
