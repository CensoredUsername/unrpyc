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

import sys
from operator import itemgetter

from .util import DecompilerBase, First, reconstruct_paraminfo, \
                  reconstruct_arginfo, split_logical_lines, Dispatcher

from . import atldecompiler

from renpy import ui, sl2
from renpy.ast import PyExpr
from renpy.text import text
from renpy.sl2 import sldisplayables as sld
from renpy.display import layout, behavior, im, motion, dragdrop, transform

# Main API

def pprint(out_file, ast, options,
           indent_level=0, linenumber=1, skip_indent_until_write=False):
    return SL2Decompiler(out_file, options).dump(
        ast, indent_level, linenumber, skip_indent_until_write)

# Implementation

class SL2Decompiler(DecompilerBase):
    """
    An object which handles the decompilation of renpy screen language 2 screens to a given stream
    """

    def __init__(self, out_file, options):
        super(SL2Decompiler, self).__init__(out_file, options)

    # This dictionary is a mapping of Class: unbound_method, which is used to determine
    # what method to call for which slast class
    dispatch = Dispatcher()

    def print_node(self, ast):
        self.advance_to_line(ast.location[1])
        self.dispatch.get(type(ast), type(self).print_unknown)(self, ast)

    @dispatch(sl2.slast.SLScreen)
    def print_screen(self, ast):

        # Print the screen statement and create the block
        self.indent()
        self.write("screen %s" % ast.name)
        # If we have parameters, print them.
        if ast.parameters:
            self.write(reconstruct_paraminfo(ast.parameters))

        # print contents
        first_line, other_lines = self.sort_keywords_and_children(ast)

        # apparently, screen contents are optional.
        self.print_keyword_or_child(first_line, first_line=True, has_block=bool(other_lines))
        if other_lines:
            with self.increase_indent():
                for line in other_lines:
                    self.print_keyword_or_child(line)

    @dispatch(sl2.slast.SLIf)
    def print_if(self, ast):
        # if and showif share a lot of the same infrastructure
        self._print_if(ast, "if")

    @dispatch(sl2.slast.SLShowIf)
    def print_showif(self, ast):
        # so for if and showif we just call an underlying function with an extra argument
        self._print_if(ast, "showif")

    def _print_if(self, ast, keyword):
        # the first condition is named if or showif, the rest elif
        keyword = First(keyword, "elif")
        for condition, block in ast.entries:
            self.advance_to_line(block.location[1])
            self.indent()
            # if condition is None, this is the else clause
            if condition is None:
                self.write("else")
            else:
                self.write("%s %s" % (keyword(), condition))

            # Every condition has a block of type slast.SLBlock
            self.print_block(block, immediate_block=True)

    def print_block(self, ast, immediate_block=False):
        # represents an SLBlock node, which is a container of keyword arguments and children
        #
        # block is a child of showif, if, use, user-defined displayables.
        # for showif, if and use, no keyword properties on the same line are allowed
        # for custom displayables, they are allowed.
        #
        # immediate_block: boolean, indicates that no keyword properties are before the :, and that
        # a block is required
        first_line, other_lines = self.sort_keywords_and_children(ast, immediate_block=immediate_block)

        has_block = immediate_block or bool(other_lines)

        self.print_keyword_or_child(first_line, first_line=True, has_block=has_block)

        if other_lines:
            with self.increase_indent():
                for line in other_lines:
                    self.print_keyword_or_child(line)

            # special case, a block is forced, while there is no content
        elif immediate_block:
            with self.increase_indent():
                self.indent()
                self.write("pass")

    @dispatch(sl2.slast.SLFor)
    def print_for(self, ast):
        # Since tuple unpickling is hard, renpy just gives up and inserts a
        # $ a,b,c = _sl2_i after the for statement if any tuple unpacking was
        # attempted in the for statement. Detect this and ignore this slast.SLPython entry
        if ast.variable == "_sl2_i":
            variable = ast.children[0].code.source[:-9]
            children = ast.children[1:]
        else:
            variable = ast.variable.strip() + " "
            children = ast.children

        self.indent()
        if hasattr(ast, "index_expression") and ast.index_expression is not None:
            self.write("for %sindex %s in %s:" % (variable, ast.index_expression, ast.expression))

        else:
            self.write("for %sin %s:" % (variable, ast.expression))

        # for doesn't contain a block, but just a list of child nodes
        self.print_nodes(children, 1)

    @dispatch(sl2.slast.SLContinue)
    def print_continue(self, ast):
        self.indent()
        self.write("continue")

    @dispatch(sl2.slast.SLBreak)
    def print_break(self, ast):
        self.indent()
        self.write("break")

    @dispatch(sl2.slast.SLPython)
    def print_python(self, ast):
        self.indent()

        # Extract the source code from the slast.SLPython object. If it starts with a
        # newline, print it as a python block, else, print it as a $ statement
        code = ast.code.source
        if code.startswith("\n"):
            code = code[1:]
            self.write("python:")
            with self.increase_indent():
                self.write_lines(split_logical_lines(code))
        else:
            self.write("$ %s" % code)

    @dispatch(sl2.slast.SLPass)
    def print_pass(self, ast):
        # A pass statement
        self.indent()
        self.write("pass")

    @dispatch(sl2.slast.SLUse)
    def print_use(self, ast):
        # A use statement requires reconstructing the arguments it wants to pass
        self.indent()
        self.write("use ")
        args = reconstruct_arginfo(ast.args)
        if isinstance(ast.target, PyExpr):
            self.write("expression %s" % ast.target)
            if args:
                self.write(" pass ")
        else:
            self.write("%s" % ast.target)

        self.write("%s" % args)
        if hasattr(ast, 'id') and ast.id is not None:
            self.write(" id %s" % ast.id)

        if hasattr(ast, 'block') and ast.block:
            self.print_block(ast.block)

    @dispatch(sl2.slast.SLTransclude)
    def print_transclude(self, ast):
        self.indent()
        self.write("transclude")

    @dispatch(sl2.slast.SLDefault)
    def print_default(self, ast):
        # A default statement
        self.indent()
        self.write("default %s = %s" % (ast.variable, ast.expression))

    @dispatch(sl2.slast.SLDisplayable)
    def print_displayable(self, ast, has_block=False):
        # slast.SLDisplayable represents a variety of statements. We can figure out
        # what statement it represents by analyzing the called displayable and style
        # attributes.
        key = (ast.displayable, ast.style)
        nameAndChildren = self.displayable_names.get(key)

        if nameAndChildren is None and self.options.sl_custom_names:
            # check if we have a name registered for this displayable
            nameAndChildren = self.options.sl_custom_names.get(ast.displayable.__name__)
            self.print_debug("Substituted '{}' as the name for displayable {}".format(nameAndChildren[0], ast.displayable))

        if nameAndChildren is None:
            # This is a (user-defined) displayable we don't know about.
            # fallback: assume the name of the displayable matches the given style
            # this is rather often the case. However, as it may be wrong we have to
            # print a debug message
            nameAndChildren = (ast.style, 'many')
            self.print_debug(
 """Warning: Encountered a user-defined displayable of type '{}'.
    Unfortunately, the name of user-defined displayables is not recorded in the compiled file.
    For now the style name '{}' will be substituted.
    To check if this is correct, find the corresponding renpy.register_sl_displayable call.""".format(
                    ast.displayable, ast.style
                )
            )

        (name, children) = nameAndChildren
        self.indent()
        self.write(name)
        if ast.positional:
            self.write(" " + " ".join(ast.positional))

        atl_transform = getattr(ast, 'atl_transform', None)
        # The AST contains no indication of whether or not "has" blocks
        # were used. We'll use one any time it's possible (except for
        # directly nesting them, or if they wouldn't contain any children),
        # since it results in cleaner code.

        # if we're not already in a has block, and have a single child that's a displayable,
        # which itself has children, and the line number of this child is after any atl transform or keyword
        # we can safely use a has statement
        if (not has_block and children == 1 and len(ast.children) == 1 and
            isinstance(ast.children[0], sl2.slast.SLDisplayable) and
            ast.children[0].children and (not ast.keyword or
                ast.children[0].location[1] > ast.keyword[-1][1].linenumber) and
            (atl_transform is None or ast.children[0].location[1] > atl_transform.loc[1])):

            first_line, other_lines = self.sort_keywords_and_children(ast, ignore_children=True)
            self.print_keyword_or_child(first_line, first_line=True, has_block=True)

            with self.increase_indent():
                for line in other_lines:
                    self.print_keyword_or_child(line)

                self.advance_to_line(ast.children[0].location[1])
                self.indent()
                self.write("has ")

                self.skip_indent_until_write = True
                self.print_displayable(ast.children[0], True)

        elif has_block:
            # has block: for now, assume no block of any kind present
            first_line, other_lines = self.sort_keywords_and_children(ast)
            self.print_keyword_or_child(first_line, first_line=True, has_block=False)
            for line in other_lines:
                self.print_keyword_or_child(line)

        else:
            first_line, other_lines = self.sort_keywords_and_children(ast)
            self.print_keyword_or_child(first_line, first_line=True, has_block=bool(other_lines))

            with self.increase_indent():
                for line in other_lines:
                    self.print_keyword_or_child(line)

    displayable_names = {
        (behavior.AreaPicker, "default"):  ("areapicker", 1),
        (behavior.Button, "button"):       ("button", 1),
        (behavior.DismissBehavior, "default"): ("dismiss", 0),
        (behavior.Input, "input"):         ("input", 0),
        (behavior.MouseArea, 0):           ("mousearea", 0),
        (behavior.MouseArea, None):        ("mousearea", 0),
        (behavior.OnEvent, 0):             ("on", 0),
        (behavior.OnEvent, None):          ("on", 0),
        (behavior.Timer, "default"):       ("timer", 0),
        (dragdrop.Drag, "drag"):           ("drag", 1),
        (dragdrop.Drag, None):             ("drag", 1),
        (dragdrop.DragGroup, None):        ("draggroup", 'many'),
        (im.image, "default"):             ("image", 0),
        (layout.Grid, "grid"):             ("grid", 'many'),
        (layout.MultiBox, "fixed"):        ("fixed", 'many'),
        (layout.MultiBox, "hbox"):         ("hbox", 'many'),
        (layout.MultiBox, "vbox"):         ("vbox", 'many'),
        (layout.NearRect, "default"):      ("nearrect", 1),
        (layout.Null, "default"):          ("null", 0),
        (layout.Side, "side"):             ("side", 'many'),
        (layout.Window, "frame"):          ("frame", 1),
        (layout.Window, "window"):         ("window", 1),
        (motion.Transform, "transform"):   ("transform", 1),
        (sld.sl2add, None):                ("add", 0),
        (sld.sl2bar, None):                ("bar", 0),
        (sld.sl2vbar, None):               ("vbar", 0),
        (sld.sl2viewport, "viewport"):     ("viewport", 1),
        (sld.sl2vpgrid, "vpgrid"):         ("vpgrid", 'many'),
        (text.Text, "text"):               ("text", 0),
        (transform.Transform, "transform"):("transform", 1),
        (ui._add, None):                   ("add", 0),
        (ui._hotbar, "hotbar"):            ("hotbar", 0),
        (ui._hotspot, "hotspot"):          ("hotspot", 1),
        (ui._imagebutton, "image_button"): ("imagebutton", 0),
        (ui._imagemap, "imagemap"):        ("imagemap", 'many'),
        (ui._key, None):                   ("key", 0),
        (ui._label, "label"):              ("label", 0),
        (ui._textbutton, "button"):        ("textbutton", 0),
        (ui._textbutton, 0):               ("textbutton", 0),
    }

    def sort_keywords_and_children(self, node, immediate_block=False, ignore_children=False):
        # sorts the contents of a SL statement that has keywords and children
        # returns a list of sorted contents.
        # 
        # node is either a SLDisplayable, a SLScreen or a SLBlock
        # 
        # before this point, the name and any positional arguments of the statement have been
        # emitted, but the block itself has not been created yet.
        #   immediate_block: bool, if True, nothing is on the first line
        #   ignore_children: Do not inspect children, used to implement "has" statements

        # get all the data we need from the node
        keywords = node.keyword
        children = [] if ignore_children else node.children
        
        # first linenumber where we can insert content that doesn't have a clear lineno
        block_lineno = node.location[1]
        start_lineno = (block_lineno + 1) if immediate_block else block_lineno

        # these ones are optional
        tag = getattr(node, "tag", None) # only used by SLScreen
        variable = getattr(node, "variable", None) # only used by SLDisplayable
        atl_transform = getattr(node, "atl_transform", None) # all three can have it, but it is an optional property anyway

        # keywords that we have no location info over
        keywords_somewhere = []
        if variable is not None:
            keywords_somewhere.append(("as", variable))
        if tag is not None:
            keywords_somewhere.append(("tag", tag))

        # keywords
        # pre 7.7/8.2: keywords at the end of a line could not have an argument and the parser was okay with that.
        keywords_by_line = [(value.linenumber if value else None, "keyword" if value else "broken", (name, value)) for name, value in keywords]

        # children
        children_by_line = [(child.location[1], "child", child) for child in children]

        # now we have to determine the order of all things. Multiple keywords can go on the same line, but not children.
        # we don't want to completely trust lineno's, even if they're utterly wrong we still should spit out a decent file
        # also, keywords and children are supposed to be in order from the start, so we shouldn't scramble that.

        # merge keywords and childrens into a single ordered list
        # list of lineno, type, contents
        contents_in_order = []
        keywords_by_line.reverse()
        children_by_line.reverse()
        while keywords_by_line and children_by_line:
            # broken keywords: always emit before any children, so we can merge them with the previous keywords easily
            if keywords_by_line[-1][0] is None:
                contents_in_order.append(keywords_by_line.pop())

            elif keywords_by_line[-1][0] < children_by_line[-1][0]:
                contents_in_order.append(keywords_by_line.pop())

            else:
                contents_in_order.append(children_by_line.pop())

        while keywords_by_line:
            contents_in_order.append(keywords_by_line.pop())

        while children_by_line:
            contents_in_order.append(children_by_line.pop())

        # merge in at transform if present
        if atl_transform is not None:
            atl_lineno = atl_transform.loc[1]

            for i, (lineno, _, _) in enumerate(contents_in_order):
                if lineno is not None and atl_lineno < lineno:
                    index = i
                    break
            else:
                index = len(contents_in_order)

            contents_in_order.insert(index, (atl_lineno, "atl", atl_transform))

            # TODO: double check that any atl is after any "at" keyword?

        # a line can be either of the following
        # a child
        # a broken keyword
        # a list of keywords, potentially followed by an atl transform

        # accumulator for a line of keywords
        current_keyword_line = None

        # datastructure of (lineno, type, contents....)
        # possible types
        # "child"
        # "keywords"
        # "keywords_atl"
        # "keywords_broken"
        contents_grouped = []

        for (lineno, ty, content) in contents_in_order:
            if current_keyword_line is None:
                if ty == "child":
                    contents_grouped.append((lineno, "child", content))
                elif ty == "keyword":
                    current_keyword_line = (lineno, "keywords", [content])
                elif ty == "broken":
                    contents_grouped.append((lineno, "keywords_broken", [], content))
                elif ty == "atl":
                    contents_grouped.append((lineno, "keywords_atl", [], content))

            else:
                if ty == "child":
                    contents_grouped.append(current_keyword_line)
                    current_keyword_line = None
                    contents_grouped.append((lineno, "child", content))

                elif ty == "keyword":
                    if current_keyword_line[0] == lineno:
                        current_keyword_line[2].append(content)

                    else:
                        contents_grouped.append(current_keyword_line)
                        current_keyword_line = (lineno, "keywords", [content])

                elif ty == "broken":
                    contents_grouped.append(current_keyword_line[0], "keywords_broken", current_keyword_line[2], content)
                    current_keyword_line = None

                elif ty == "atl":
                    if current_keyword_line[0] == lineno:
                        contents_grouped.append(lineno, "keywords_atl", current_keyword_line[2], content)
                        current_keyword_line = None
                    else:
                        contents_grouped.append(current_keyword_line)
                        current_keyword_line = None
                        contents_grouped.append((lineno, "keywords_atl", [], content))

        if current_keyword_line is not None:
            contents_grouped.append(current_keyword_line)

        # We need to assign linenos to any broken keywords that don't have them. Best guess is the previous lineno + 1
        # unless that doesn't exist, in which case it's the first available line
        for i in range(len(contents_grouped)):
            lineno = contents_grouped[i][0]
            ty = contents_grouped[i][1]
            if ty == "keywords_broken" and lineno is None:
                contents = contents_grouped[i][3]

                if i != 0:
                    lineno = contents_grouped[i - 1][0] + 1
                else:
                    lineno = start_lineno

                contents_grouped[i] = (lineno, "keywords_broken", [], contents)

        # and insert keywords_somewhere.. somewhere. It'd be pretty to insert them on a separate line,
        # but otherwise shoving them in any keywords line will do.
        # If there are none, we need to insert one. Inserting it at the start is preferable.
        if keywords_somewhere:
            # if we have no contents: put them on the first line available
            # same if --tag-outside-block is used.
            if not contents_grouped:
                contents_grouped.append((start_lineno, "keywords", keywords_somewhere))

            # if there's multiple empty lines after the statement, fill them with it
            elif contents_grouped[0][0] >= block_lineno + len(keywords_somewhere) + 1:
                prefix = [(block_lineno + i + 1, "keywords", [content]) for i, content in enumerate(keywords_somewhere)]
                contents_grouped = prefix + contents_grouped

            # if the start line is available, put them there
            elif contents_grouped[0][0] > start_lineno:
                contents_grouped.insert(0, (start_lineno, "keywords", keywords_somewhere))

            else:
                # otherwise, just put them after some existing keywords node
                for entry in contents_grouped:
                    if entry[1].startswith("keywords"):
                        entry[2].extend(keywords_somewhere)
                        break

                # otherwise, just force them first at the start line
                else:
                    contents_grouped.insert(0, (start_lineno, "keywords", keywords_somewhere))

        # if there's no content on the first line, insert an empty line, to make processing easier.
        if immediate_block or not contents_grouped or contents_grouped[0][0] != block_lineno:
            contents_grouped.insert(0, (block_lineno, "keywords", []))

        # return first_line_content, later_contents
        return contents_grouped[0], contents_grouped[1:]

    def print_keyword_or_child(self, item, first_line=False, has_block=False):
        sep = First(" " if first_line else "", " ")

        lineno = item[0]
        ty = item[1]

        if ty == "child":
            self.print_node(item[2])
            return

        if not first_line:
            self.advance_to_line(lineno)
            self.indent()

        for name, value in item[2]:
            self.write(sep())
            self.write("%s %s" % (name, value))

        if ty == "keywords_atl":
            assert not has_block, "cannot start a block on the same line as an at transform block"
            self.write(sep())
            self.write("at transform:")

            self.linenumber = atldecompiler.pprint(
                self.out_file, item[3], self.options,
                self.indent_level, self.linenumber, self.skip_indent_until_write
            )
            self.skip_indent_until_write = False
            return

        if ty == "keywords_broken":
            self.write(sep())
            self.write(item[3])

        if first_line and has_block:
            self.write(":")
