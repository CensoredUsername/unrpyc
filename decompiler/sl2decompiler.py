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

from __future__ import unicode_literals
import sys

from util import DecompilerBase, First, reconstruct_paraminfo, reconstruct_arginfo, split_logical_lines

from renpy import ui, sl2
from renpy.text import text
from renpy.sl2 import sldisplayables as sld
from renpy.display import layout, behavior, im, motion, dragdrop

# Main API

def pprint(out_file, ast, indent_level=0, linenumber=1,
           force_multiline_kwargs=True, decompile_screencode=True,
           comparable=False, skip_indent_until_write=False):
    return SL2Decompiler(out_file,
                  force_multiline_kwargs=force_multiline_kwargs,
                  decompile_screencode=decompile_screencode, comparable=comparable).dump(
                      ast, indent_level, linenumber, skip_indent_until_write)

# Implementation

class SL2Decompiler(DecompilerBase):
    """
    An object which handles the decompilation of renpy screen language 2 screens to a given stream
    """

    # This dictionary is a mapping of Class: unbound_method, which is used to determine
    # what method to call for which slast class
    dispatch = {}

    displayable_names = {}

    def __init__(self, out_file=None, force_multiline_kwargs=True, decompile_screencode=True, indentation='    ', comparable=False):
        super(SL2Decompiler, self).__init__(out_file, indentation, comparable)
        self.force_multiline_kwargs = force_multiline_kwargs
        self.decompile_screencode = decompile_screencode

    def print_node(self, ast):
        self.advance_to_line(ast.location[1])
        # Find the function which can decompile this node
        func = self.dispatch.get(type(ast), None)
        if func:
            func(self, ast)
        else:
            # This node type is unknown
            self.print_unknown(ast)

    def print_screen(self, ast):

        # Print the screen statement and create the block
        self.indent()
        self.write("screen %s" % ast.name)
        # If we have parameters, print them.
        if ast.parameters:
            self.write(reconstruct_paraminfo(ast.parameters))
        # Print any keywords
        if ast.tag:
            self.write(" tag %s" % ast.tag)
        for key, value in ast.keyword:
            self.write(" %s %s" % (key, value))
        self.write(":")
        self.indent_level += 1

        # If we're decompiling screencode, print it. Else, insert a pass statement
        if self.decompile_screencode:
            self.print_nodes(ast.children)
        else:
            self.indent()
            self.write("pass # Screen code not decompiled")

        self.indent_level -= 1
    dispatch[sl2.slast.SLScreen] = print_screen

    def print_if(self, ast):
        # if and showif share a lot of the same infrastructure
        self._print_if(ast, "if")
    dispatch[sl2.slast.SLIf] = print_if

    def print_showif(self, ast):
        # so for if and showif we just call an underlying function with an extra argument
        self._print_if(ast, "showif")
    dispatch[sl2.slast.SLShowIf] = print_showif

    def _print_if(self, ast, keyword):
        # the first condition is named if or showif, the rest elif
        keyword = First(keyword, "elif")
        for condition, block in ast.entries:
            self.advance_to_line(block.location[1])
            self.indent()
            # if condition is None, this is the else clause
            if condition is None:
                self.write("else:")
            else:
                self.write("%s %s:" % (keyword(), condition))

            # Every condition has a block of type slast.SLBlock
            if block.keyword or block.children:
                self.print_block(block)
            else:
                self.indent_level += 1
                self.indent()
                self.write("pass")
                self.indent_level -= 1

    def print_block(self, ast):
        # A block contains possible keyword arguments and a list of child nodes
        # this is the reason if doesn't keep a list of children but special Blocks
        self.indent_level += 1

        if self.force_multiline_kwargs and not self.comparable:
            for key, value in ast.keyword:
                self.indent()
                self.write("%s %s" % (key, value))
        elif ast.keyword:
            self.indent()
            self.write(" ".join(("%s %s" % (key, value)) for key, value in ast.keyword))

        self.print_nodes(ast.children)
        self.indent_level -= 1
    dispatch[sl2.slast.SLBlock] = print_block

    def print_for(self, ast):
        # Since tuple unpickling is hard, renpy just gives up and inserts a
        # $ a,b,c = _sl2_i after the for statement if any tuple unpacking was
        # attempted in the for statement. Detect this and ignore this slast.SLPython entry
        if ast.variable == "_sl2_i":
            variable = ast.children[0].code.source[:-9].strip()
            children = ast.children[1:]
        else:
            variable = ast.variable.strip()
            children = ast.children

        self.indent()
        self.write("for %s in %s:" % (variable, ast.expression))

        # Interestingly, for doesn't contain a block, but just a list of child nodes
        self.print_nodes(children, 1)
    dispatch[sl2.slast.SLFor] = print_for

    def print_python(self, ast):
        self.indent()

        # Extract the source code from the slast.SLPython object. If it starts with a
        # newline, print it as a python block, else, print it as a $ statement
        code = ast.code.source
        if code[0] == "\n":
            code = code[1:]
            self.write("python:")
            self.indent_level += 1
            for line in split_logical_lines(code):
                self.indent()
                self.write(line)
            self.indent_level -= 1
        else:
            self.write("$ %s" % code)
    dispatch[sl2.slast.SLPython] = print_python

    def print_pass(self, ast):
        # A pass statement
        self.indent()
        self.write("pass")
    dispatch[sl2.slast.SLPass] = print_pass

    def print_use(self, ast):
        # A use statement requires reconstructing the arguments it wants to pass
        self.indent()
        self.write("use %s%s" % (ast.target, reconstruct_arginfo(ast.args)))
    dispatch[sl2.slast.SLUse] = print_use

    def print_default(self, ast):
        # A default statement
        self.indent()
        self.write("default %s = %s" % (ast.variable, ast.expression))
    dispatch[sl2.slast.SLDefault] = print_default

    def print_displayable(self, ast):
        # slast.SLDisplayable represents a variety of statements. We can figure out
        # what statement it represents by analyzing the called displayable and style
        # attributes.
        name = self.displayable_names.get((ast.displayable, ast.style))
        if name is None:
            self.print_unknown(ast)
        else:
            self.indent()
            self.write(name)
            self.print_arguments(ast.positional, ast.keyword, ast.children)
            self.print_nodes(ast.children, 1)
    dispatch[sl2.slast.SLDisplayable] = print_displayable

    displayable_names[(behavior.OnEvent, None)]          = "on"
    displayable_names[(behavior.OnEvent, 0)]             = "on"
    displayable_names[(behavior.MouseArea, 0)]           = "mousearea"
    displayable_names[(sld.sl2add, None)]                = "add"
    displayable_names[(ui._hotbar, "hotbar")]            = "hotbar"
    displayable_names[(sld.sl2vbar, None)]               = "vbar"
    displayable_names[(sld.sl2bar, None)]                = "bar"
    displayable_names[(ui._label, "label")]              = "label"
    displayable_names[(ui._textbutton, 0)]               = "textbutton"
    displayable_names[(ui._imagebutton, "image_button")] = "imagebutton"
    displayable_names[(im.image, "default")]             = "image"
    displayable_names[(behavior.Input, "input")]         = "input"
    displayable_names[(behavior.Timer, "default")]       = "timer"
    displayable_names[(ui._key, None)]                   = "key"
    displayable_names[(text.Text, "text")]               = "text"
    displayable_names[(layout.Null, "default")]          = "null"
    displayable_names[(dragdrop.Drag, None)]             = "drag"
    displayable_names[(motion.Transform, "transform")]   = "transform"
    displayable_names[(ui._hotspot, "hotspot")]          = "hotspot"
    displayable_names[(sld.sl2viewport, "viewport")]     = "viewport"
    displayable_names[(behavior.Button, "button")]       = "button"
    displayable_names[(layout.Window, "frame")]          = "frame"
    displayable_names[(layout.Window, "window")]         = "window"
    displayable_names[(dragdrop.DragGroup, None)]        = "draggroup"
    displayable_names[(ui._imagemap, "imagemap")]        = "imagemap"
    displayable_names[(layout.Side, "side")]             = "side"
    displayable_names[(layout.Grid, "grid")]             = "grid"
    displayable_names[(layout.MultiBox, "fixed")]        = "fixed"
    displayable_names[(layout.MultiBox, "vbox")]         = "vbox"
    displayable_names[(layout.MultiBox, "hbox")]         = "hbox"

    def print_arguments(self, args, kwargs, multiline=True):
        # This function prints the arguments and keyword arguments
        # Used in a displayable screen statement
        if args:
            self.write(" " + " ".join(args))

        if self.force_multiline_kwargs and not self.comparable and kwargs:
            self.write(":")
            self.indent_level += 1
            for key, value in kwargs:
                self.indent()
                self.write("%s %s" % (key, value))
            self.indent_level -= 1
        else:
            for key, value in kwargs:
                self.write(" %s %s" % (key, value))
            if multiline:
                self.write(":")
