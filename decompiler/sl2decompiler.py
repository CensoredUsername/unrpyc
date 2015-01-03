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

def pprint(out_file, ast, indent_level=0,
           force_multiline_kwargs=True, decompile_screencode=True):
    SL2Decompiler(out_file,
                  force_multiline_kwargs=force_multiline_kwargs,
                  decompile_screencode=decompile_screencode).dump(ast, indent_level)

# Implementation

class SL2Decompiler(DecompilerBase):
    """
    An object which handles the decompilation of renpy screen language 2 screens to a given stream
    """

    # This dictionary is a mapping of Class: unbound_method, which is used to determine
    # what method to call for which slast class
    dispatch = {}

    def __init__(self, out_file=None, force_multiline_kwargs=True, decompile_screencode=True, indentation='    '):
        super(SL2Decompiler, self).__init__(out_file, indentation)
        self.force_multiline_kwargs = force_multiline_kwargs
        self.decompile_screencode = decompile_screencode

    def print_node(self, ast):
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
        self.write(":")
        self.indent_level += 1

        # Print any keywords
        for key, value in ast.keyword:
            self.indent()
            self.write("%s %s" % (key, value))

        if ast.tag:
            self.indent()
            self.write("tag %s" % ast.tag)

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
            self.indent()
            # if condition is None, this is the else clause
            if condition is None:
                self.write("else:")
            else:
                self.write("%s %s:" % (keyword(), condition))

            # Every condition has a block of type slast.SLBlock
            self.print_block(block)

    def print_block(self, ast):
        # A block contains possible keyword arguments and a list of child nodes
        # this is the reason if doesn't keep a list of children but special Blocks
        self.indent_level += 1

        for key, value in ast.keyword:
            self.indent()
            self.write("%s %s" % (key, value))

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
        func, name = self.dispatch.get((ast.displayable, ast.style), (None, None))
        if func is None:
            self.print_unknown(ast)
        else:
            func(self, ast, name)
    dispatch[sl2.slast.SLDisplayable] = print_displayable

    def print_nochild(self, ast, name):
        # Print a displayable which does not take any children
        self.indent()
        self.write(name)
        self.print_arguments(ast.positional, ast.keyword, False)
    dispatch[(behavior.OnEvent, None)]          = (print_nochild, "on")
    dispatch[(behavior.MouseArea, 0)]           = (print_nochild, "mousearea")
    dispatch[(sld.sl2add, None)]                = (print_nochild, "add")
    dispatch[(ui._hotbar, "hotbar")]            = (print_nochild, "hotbar")
    dispatch[(sld.sl2vbar, None)]               = (print_nochild, "vbar")
    dispatch[(sld.sl2bar, None)]                = (print_nochild, "bar")
    dispatch[(ui._label, "label")]              = (print_nochild, "label")
    dispatch[(ui._textbutton, 0)]               = (print_nochild, "textbutton")
    dispatch[(ui._imagebutton, "image_button")] = (print_nochild, "imagebutton")
    dispatch[(im.image, "default")]             = (print_nochild, "image")
    dispatch[(behavior.Input, "input")]         = (print_nochild, "input")
    dispatch[(behavior.Timer, "default")]       = (print_nochild, "timer")
    dispatch[(ui._key, None)]                   = (print_nochild, "key")
    dispatch[(text.Text, "text")]               = (print_nochild, "text")
    dispatch[(layout.Null, "default")]          = (print_nochild, "null")

    def print_onechild(self, ast, name):
        # Print a displayable which takes one child
        # For now this does not have any differences from many children
        self.indent()
        self.write(name)
        self.print_arguments(ast.positional, ast.keyword)
        self.print_nodes(ast.children, 1)
    dispatch[(dragdrop.Drag, None)]             = (print_onechild, "drag")
    dispatch[(motion.Transform, "transform")]   = (print_onechild, "transform")
    dispatch[(ui._hotspot, "hotspot")]          = (print_onechild, "hotspot")
    dispatch[(sld.sl2viewport, "viewport")]     = (print_onechild, "viewport")
    dispatch[(behavior.Button, "button")]       = (print_onechild, "button")
    dispatch[(layout.Window, "frame")]          = (print_onechild, "frame")
    dispatch[(layout.Window, "window")]         = (print_onechild, "window")

    def print_manychildren(self, ast, name):
        # Print a displayable which takes many children
        self.indent()
        self.write(name)
        self.print_arguments(ast.positional, ast.keyword)
        self.print_nodes(ast.children, 1)
    dispatch[(dragdrop.DragGroup, None)]        = (print_manychildren, "draggroup")
    dispatch[(ui._imagemap, "imagemap")]        = (print_manychildren, "imagemap")
    dispatch[(layout.Side, "side")]             = (print_manychildren, "side")
    dispatch[(layout.Grid, "grid")]             = (print_manychildren, "grid")
    dispatch[(layout.MultiBox, "fixed")]        = (print_manychildren, "fixed")
    dispatch[(layout.MultiBox, "vbox")]         = (print_manychildren, "vbox")
    dispatch[(layout.MultiBox, "hbox")]         = (print_manychildren, "hbox")

    def print_arguments(self, args, kwargs, multiline=True):
        # This function prints the arguments and keyword arguments
        # Used in a displayable screen statement
        if args:
            self.write(" " + " ".join(args))

        if multiline or (self.force_multiline_kwargs and kwargs):
            self.write(":")
            self.indent_level += 1
            for key, value in kwargs:
                self.indent()
                self.write("%s %s" % (key, value))
            self.indent_level -= 1
        else:
            for key, value in kwargs:
                self.write(" %s %s" % (key, value))
