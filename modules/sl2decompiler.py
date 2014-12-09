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

import re
from screendecompiler import indent
import decompiler

# default config
class Config:
    EXTRACT_PYTHON_AST     = True
    DECOMPILE_PYTHON_AST   = True
    FORCE_MULTILINE_KWARGS = True
    DECOMPILE_SCREENCODE   = True
    
def print_screen(f, children, indent_level=0, configoverride=Config()):
    # This function should be called from the outside. It does some general cleanup in advance.
    global config
    config = configoverride
    for child in children:
        print_node(f, child, indent_level+1)

def print_node(f, node, indent_level):
    statement_printer_dict.get(type(node), print_unknown)(f, node, indent_level)

def print_unknown(f, node, indent_level):
    print "Unknown AST node: %s" % (type(node).__name__, )
    indent(f, indent_level)
    f.write(u"<<<UNKNOWN NODE %s>>>\n" % (type(stmt).__name__, ))

def print_if(f, node, indent_level):
    _print_if(f, node, indent_level, "if ")

def print_showif(f, node, indent_level):
    _print_if(f, node, indent_level, "showif ")

def _print_if(f, node, indent_level, first):
    text = first
    for condition, block in node.entries:
        if condition is None:
            text = "else"
        indent(f, indent_level)
        f.write(u"%s%s:\n" % (text, condition or ""))
        print_block(f, block, indent_level)
        text = "elif "

def print_block(f, node, indent_level):
    for child in node.children:
        print_node(f, child, indent_level+1)

def print_for(f, node, indent_level):
    if node.variable == "_sl2_i":
        # Tuple unpacking is hard apparently
        variable = node.children[0].code.source[:-9].strip()
        children = node.children[1:]
    else:
        variable = node.variable.strip()
        children = node.children

    indent(f, indent_level)
    f.write(u"for %s in %s:\n" % (variable, node.expression))

    for child in children:
        print_node(f, child, indent_level+1)

def print_python(f, node, indent_level):
    code = node.code.source
    if "\n" in code:
        indent(f, indent_level)
        f.write(u"python:")
        lines = code.splitlines()
        for line in lines:
            indent(f, indent_level+1)
            f.write(line + u"\n")
    else:
        indent(f, indent_level)
        f.write(u"$ %s\n" % code)

def print_pass(f, node, indent_level):
    indent(f, indent_level)
    f.write(u"pass\n")

def print_use(f, node, indent_level):
    indent(f, indent_level)
    f.write(u"use %s" % node.target)
    decompiler.print_args(f, node.args)
    f.write(u"\n")

def print_default(f, node, indent_level):
    indent(f,indent_level)
    f.write(u"default %s = %s\n" % (node.variable, node.expression))

def print_displayable(f, node, indent_level):
    # This is responsible for printing any screen language statement which is a displayable
    # aka:
    # Add, Bar, Button, Fixed, Frame, Grid, Hbox, Imagebutton, 
    # Input, Label, Null, Mousearea, Side, Text, Textbutton, 
    # Transform, Vbar, Vbox, Viewport and Window
    indent(f, indent_level)

    func, name = displayable_printer_dict.get((node.displayable, node.style), (None, None))
    if func is None:
        print_unknown(f, node, indent_level)

    func(f, node, name, indent_level)

def print_arguments(f, args, kwargs, indent_level, multiline=True):
    if args: 
        f.write(u' ')
        f.write(u' '.join(['(%s)' % i if ' ' in i else i for i in args]) )
    kwargs = dict(kwargs)
    for key in kwargs:
        if ' ' in kwargs[key]:
            kwargs[key] = '(%s)' % kwargs[key]
    if multiline or (config.FORCE_MULTILINE_KWARGS and kwargs):
        f.write(u':\n')
        for arg in kwargs:
            indent(f, indent_level+1)
            f.write(u'%s %s\n' % (arg, kwargs[arg]))
    else:
        for arg in kwargs:
            f.write(u' %s %s' % (arg, kwargs[arg]))
        f.write(u'\n')

def print_oneline(f, node, name, indent_level):
    f.write(name)
    print_arguments(f, node.positional, node.keyword, indent_level, False)
    
def print_onechild(f, node, name, indent_level):
    f.write(name)
    print_arguments(f, node.positional, node.keyword, indent_level)
    for child in node.children:
        print_node(f, child, indent_level+1)
    # if 'ui.child_or_fixed()' in code.splitlines()[1]:
    #     print_block(f, '\n'.join(code.splitlines()[2:]), indent_level+1)
    # else:
    #     print_block(f, '\n'.join(code.splitlines()[1:]), indent_level+1)
    
def print_manychildren(f, node, name, indent_level):
    f.write(name)
    print_arguments(f, node.positional, node.keyword, indent_level)
    for child in node.children:
        print_node(f, child, indent_level+1)
    #print_block(f, '\n'.join(code.splitlines()[1:]), indent_level+1)


from renpy import sl2
statement_printer_dict = {
    sl2.slast.SLIf: print_if,
    sl2.slast.SLBlock: print_block,
    sl2.slast.SLFor: print_for,
    sl2.slast.SLPython: print_python,
    sl2.slast.SLPass: print_pass,
    sl2.slast.SLUse: print_use,
    sl2.slast.SLDefault: print_default,
    sl2.slast.SLDisplayable: print_displayable,
    sl2.slast.SLShowIf: print_showif
}

from renpy.display import layout, behavior, im, motion, dragdrop
from renpy.text import text
from renpy import ui
from renpy.sl2 import sldisplayables as sld
# this dict maps (displayable, style) to print_func and name
displayable_printer_dict = {
    (layout.Null, "default"):           (print_oneline, "null"),
    (text.Text, "text"):                (print_oneline, "text"),
    (layout.MultiBox, "hbox"):          (print_manychildren, "hbox"),
    (layout.MultiBox, "vbox"):          (print_manychildren, "vbox"),
    (layout.MultiBox, "fixed"):         (print_manychildren, "fixed"),
    (layout.Grid, "grid"):              (print_manychildren, "grid"),
    (layout.Side, "side"):              (print_manychildren, "side"),
    (layout.Window, "window"):          (print_onechild, "window"),
    (layout.Window, "frame"):           (print_onechild, "frame"),
    (ui._key, None):                    (print_oneline, "key"),
    (behavior.Timer, "default"):        (print_oneline, "timer"),
    (behavior.Input, "input"):          (print_oneline, "input"),
    (im.image, "default"):              (print_oneline, "image"),
    (behavior.Button, "button"):        (print_onechild, "button"),
    (ui._imagebutton, "image_button"):  (print_oneline, "imagebutton"),
    (ui._textbutton, 0):                (print_oneline, "textbutton"),
    (ui._label, "label"):               (print_oneline, "label"),
    (sld.sl2bar, None):                 (print_oneline, "bar"),
    (sld.sl2vbar, None):                (print_oneline, "vbar"),
    (sld.sl2viewport, "viewport"):      (print_onechild, "viewport"),
    (ui._imagemap, "imagemap"):         (print_manychildren, "imagemap"),
    (ui._hotspot, "hotspot"):           (print_onechild, "hotspot"),
    (ui._hotbar, "hotbar"):             (print_oneline, "hotbar"),
    (motion.Transform, "transform"):    (print_onechild, "transform"),
    (sld.sl2add, None):                 (print_oneline, "add"),
    (dragdrop.Drag, None):              (print_onechild, "drag"),
    (dragdrop.DragGroup, None):         (print_manychildren, "draggroup"),
    (behavior.MouseArea, 0):            (print_oneline, "mousearea"),
    (behavior.OnEvent, None):           (print_oneline, "on")
}