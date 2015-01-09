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

import re
import ast
from operator import itemgetter

from util import DecompilerBase, WordConcatenator, reconstruct_paraminfo, simple_expression_guard
import codegen

# Main API

def pprint(out_file, ast, indent_level=0, linenumber=1,
           decompile_python=True,
           decompile_screencode=True, comparable=False,
           skip_indent_until_write=False):
    return SLDecompiler(out_file,
                 decompile_python=decompile_python,
                 decompile_screencode=decompile_screencode, comparable=comparable).dump(
                     ast, indent_level, linenumber, skip_indent_until_write)

# implementation

class SLDecompiler(DecompilerBase):
    """
    an object which handles the decompilation of renpy screen language 1 screens to a given stream
    """

    # This dictionary is a mapping of string: unbound_method, which is used to determine
    # what method to call for which statement
    dispatch = {}

    def __init__(self, out_file=None, decompile_python=True,
                 decompile_screencode=True, comparable=False, indentation="    "):
        super(SLDecompiler, self).__init__(out_file, indentation, comparable)
        self.decompile_python = decompile_python
        self.decompile_screencode = decompile_screencode

    def dump(self, ast, indent_level=0, linenumber=1, skip_indent_until_write=False):
        self.indent_level = indent_level
        self.linenumber = linenumber
        self.skip_indent_until_write = skip_indent_until_write
        self.print_screen(ast)
        return self.linenumber

    def to_source(self, node):
        return codegen.to_source(node, self.indentation)

    # Entry point functions

    def print_screen(self, ast):
        # Here we do the processing of the screen statement, and we
        # switch over to parsing of the python string representation

        # Print the screen statement and create the block
        self.indent()
        self.write("screen %s" % ast.name)
        # If we have parameters, print them.
        if hasattr(ast, "parameters") and ast.parameters:
            self.write(reconstruct_paraminfo(ast.parameters))

        if ast.tag:
            self.write(" tag %s" % ast.tag)

        # If the value for a simple_expression has a space after it (even the
        # space separating it from the next key), it will end up in the AST. We
        # need to pack as many as possible onto the screen line so that line
        # numbers can match up, without putting a space after a value that
        # wasn't there originally.
        kwargs_for_screen_line = WordConcatenator(True)
        kwargs_for_separate_lines = []
        for key in ('modal', 'zorder', 'variant', 'predict'):
            value = getattr(ast, key)
            # Non-Unicode strings are default values rather than user-supplied
            # values, so we don't need to write them out.
            if isinstance(value, unicode):
                guarded_value = simple_expression_guard(value)
                if value[-1] != " " or guarded_value != value.strip():
                    kwargs_for_separate_lines.append("%s %s" % (key, guarded_value))
                else:
                    kwargs_for_screen_line.append(key, value)
        # One value without a space can go on the end of the screen line, since
        # no space goes between the last value and the colon.
        if kwargs_for_separate_lines:
            kwargs_for_screen_line.append(kwargs_for_separate_lines.pop(0))
        self.write("%s:" % kwargs_for_screen_line.join())
        self.indent_level += 1
        for i in kwargs_for_separate_lines:
            self.indent()
            self.write(i)

        if not self.decompile_python:
            self.indent()
            self.write("pass # Screen code not extracted")
        elif self.decompile_screencode:
            self.print_nodes(ast.code.source.body)
        else:
            self.indent()
            self.write("python:")

            self.indent_level += 1
            # The first line is always "_1 = (_name, 0)", which gets included
            # even if the python: block is the only thing in the screen. Don't
            # include ours, since if we do, it'll be included twice when
            # recompiled.
            for line in self.to_source(ast.code.source).splitlines()[1:]:
                self.indent()
                self.write(line)
            self.indent_level -= 1

        self.indent_level -= 1

    def split_nodes_at_headers(self, nodes):
        if not nodes:
            return []
        rv = [nodes[:1]]
        parent_id = self.parse_header(nodes[0])
        if parent_id is None:
            raise Exception(
                "First node passed to split_nodes_at_headers was not a header")
        for i in nodes[1:]:
            if self.parse_header(i) == parent_id:
                rv.append([i])
                header = i
            else:
                rv[-1].append(i)
        return rv

    def print_nodes(self, nodes, extra_indent=0, has_block=False):
        # Print a block of statements, splitting it up on one level.
        # The screen language parser emits lines in the shape _0 = (_0, 0) from which indentation can be revealed.
        # It translates roughly to "id = (parent_id, index_in_parent_children)". When parsing a block
        # parse the first header line to find the parent_id, and then split around headers with the same parent id
        # in this block.
        if has_block and not nodes:
            raise BadHasBlockException()
        split = self.split_nodes_at_headers(nodes)
        self.indent_level += extra_indent
        for i in split:
            self.print_node(i[0], i[1:], has_block)
        self.indent_level -= extra_indent

    def get_first_line(self, nodes):
        if self.get_dispatch_key(nodes[0]):
            return nodes[0].value.lineno
        elif self.is_renpy_for(nodes):
            return nodes[1].target.lineno
        elif self.is_renpy_if(nodes):
            return nodes[0].test.lineno
        else:
            return nodes[0].lineno # TODO line numbers for Python blocks

    def make_printable_keywords(self, keywords, lineno):
        keywords = [(i.arg, simple_expression_guard(self.to_source(i.value)),
            i.value.lineno) for i in keywords if not (isinstance(
            i.value, ast.Name) and (
            (i.arg == 'id' and i.value.id.startswith('_')) or
            (i.arg == 'scope' and i.value.id == '_scope')))]
        # Sort the keywords according to what line they belong on
        # The first element always exists for the line the block starts on,
        # even if there's no keywords that go on it
        keywords_by_line = []
        current_line = []
        for i in keywords:
            if i[2] > lineno:
                keywords_by_line.append((lineno, ' '.join(current_line)))
                lineno = i[2]
                current_line = []
            current_line.extend(i[:2])
        keywords_by_line.append((lineno, ' '.join(current_line)))
        return keywords_by_line

    def print_keywords_and_nodes(self, kwnode, nodes, needs_colon, has_block):
        if kwnode:
            keywords = self.make_printable_keywords(kwnode.keywords,
                                                    kwnode.lineno)
            if keywords[0][1]:
                self.write(" %s" % keywords[0][1])
            if len(keywords) != 1 and not has_block:
                needs_colon = True
        else:
            keywords = []
        if nodes:
            nodelists = [(self.get_first_line(i[1:]), i)
                         for i in self.split_nodes_at_headers(nodes)]
            if not has_block:
                needs_colon = True
        else:
            nodelists = []
        if needs_colon:
            self.write(":")
        stuff_to_print = sorted(keywords[1:] + nodelists, key=itemgetter(0))
        if not has_block:
            self.indent_level += 1
        for i in stuff_to_print:
            # Nodes are lists. Keywords are ready-to-print strings.
            if type(i[1]) == list:
                self.print_node(i[1][0], i[1][1:])
            else:
                self.advance_to_line(i[0])
                self.indent()
                self.write(i[1])
        if not has_block:
            self.indent_level -= 1

    def get_dispatch_key(self, node):
        if (isinstance(node, ast.Expr) and
                isinstance(node.value, ast.Call) and
                isinstance(node.value.func, ast.Attribute) and
                isinstance(node.value.func.value, ast.Name)):
            return node.value.func.value.id, node.value.func.attr
        else:
            return None

    def print_node(self, header, code, has_block=False):
        # Here we derermine how to handle a statement.
        # To do this we look at how the first line in the statement code starts, after the header.
        # Then we call the appropriate function as specified in ui_function_dict.
        # If the statement is unknown, we can still emit valid screen code by just
        # stuffing it inside a python block.

        # There's 3 categories of things that we can convert to screencode:
        # if statements, for statements, and function calls of the
        # form "first.second(...)". Anything else gets converted to Python.
        if not has_block:
            self.advance_to_line(self.get_first_line(code))
        dispatch_key = self.get_dispatch_key(code[0])
        if dispatch_key:
            func = self.dispatch.get(dispatch_key, self.print_python.__func__)
            if has_block:
                if func not in (self.print_onechild.__func__,
                    self.print_manychildren.__func__):
                    raise BadHasBlockException()
                func(self, header, code, True)
            else:
                func(self, header, code)
        elif has_block:
            raise BadHasBlockException()
        elif self.is_renpy_for(code):
            self.print_for(header, code)
        elif self.is_renpy_if(code):
            self.print_if(header, code)
        else:
            self.print_python(header, code)
    # Helper printing functions

    def print_args(self, node):
        if node.args:
            self.write(" " + " ".join([simple_expression_guard(
                self.to_source(i)) for i in node.args]))

    # Node printing functions

    def print_python(self, header, code):
        # This function handles any statement which is a block but couldn't logically be
        # Translated to a screen statement. If it only contains one line it should not make a block, just use $.
        lines = []
        for i in code:
            lines.append(self.to_source(i))
        code = '\n'.join(lines)
        self.indent()

        if '\n' in code.strip():
            lines = code.splitlines()
            # Find the first not-whitespace line
            first = next(line for line in lines if line.strip())
            # the indentation is then equal to
            code_indent = len(first) - len(first.lstrip())

            self.write("python:")
            self.indent_level += 1
            for line in lines:
                self.indent()
                self.write(line[code_indent:])
            self.indent_level -= 1
        else:
            self.write("$ %s" % code.strip())

    def is_renpy_if(self, nodes):
        return len(nodes) == 1 and isinstance(nodes[0], ast.If) and (
            nodes[0].body and self.parse_header(nodes[0].body[0])) and (
                not nodes[0].orelse or self.is_renpy_if(nodes[0].orelse) or
                self.parse_header(nodes[0].orelse[0]))

    def is_renpy_for(self, nodes):
        return (len(nodes) == 2 and isinstance(nodes[0], ast.Assign) and
            len(nodes[0].targets) == 1 and
            isinstance(nodes[0].targets[0], ast.Name) and
            re.match(r"_[0-9]+$", nodes[0].targets[0].id) and
            isinstance(nodes[0].value, ast.Num) and nodes[0].value.n == 0 and
            isinstance(nodes[1], ast.For) and not nodes[1].orelse and
            nodes[1].body and self.parse_header(nodes[1].body[0]) and
            isinstance(nodes[1].body[-1], ast.AugAssign) and
            isinstance(nodes[1].body[-1].op, ast.Add) and
            isinstance(nodes[1].body[-1].target, ast.Name) and
            re.match(r"_[0-9]+$", nodes[1].body[-1].target.id) and
            isinstance(nodes[1].body[-1].value, ast.Num) and
            nodes[1].body[-1].value.n == 1)

    def strip_parens(self, text):
        if text and text[0] == '(' and text[-1] == ')':
            return text[1:-1]
        else:
            return text

    def print_if(self, header, code):
        # Here we handle the if statement. It might be valid python but we can check for this by
        # checking for the header that should normally occur within the if statement.
        # The if statement parser might also generate a second header if there's more than one screen
        # statement enclosed in the if/elif/else statements. We'll take care of that too.
        self.indent()
        self.write("if %s:" % self.strip_parens(self.to_source(code[0].test)))
        if (len(code[0].body) >= 2 and self.parse_header(code[0].body[0]) and
            self.parse_header(code[0].body[1])):
            body = code[0].body[1:]
        else:
            body = code[0].body
        self.print_nodes(body, 1)
        if code[0].orelse:
            self.indent()
            if self.is_renpy_if(code[0].orelse):
                self.write("el") # beginning of "elif"
                self.skip_indent_until_write = True
                self.print_if(header, code[0].orelse)
            else:
                self.write("else:")
                if (len(code[0].orelse) >= 2 and
                    self.parse_header(code[0].orelse[0]) and
                    self.parse_header(code[0].orelse[1])):
                    orelse = code[0].orelse[1:]
                else:
                    orelse = code[0].orelse
                self.print_nodes(orelse, 1)

    def print_for(self, header, code):
        # Here we handle the for statement. Note that the for statement generates some extra python code to
        # Keep track of it's header indices. The first one is ignored by the statement parser,
        # the second line is just ingored here.
        line = code[1]

        self.indent()
        self.write("for %s in %s:" % (
            self.strip_parens(self.to_source(line.target)),
            self.to_source(line.iter)))
        if (len(line.body) >= 3 and self.parse_header(line.body[0]) and
            self.parse_header(line.body[1])):
            body = line.body[1:]
        else:
            body = line.body
        self.print_nodes(body[:-1], 1)
        return

    def print_use(self, header, code):
        # This function handles the use statement, which translates into a python expression "renpy.use_screen".
        # It would technically be possible for this to be a python statement, but the odds of this are very small.
        # renpy itself will insert some kwargs, we'll delete those and then parse the command here.
        if (len(code) != 1 or not code[0].value.args or
            not isinstance(code[0].value.args[0], ast.Str)):
            return self.print_python(header, code)
        args, kwargs, exargs, exkwargs = self.parse_args(code[0])
        kwargs = [(key, value) for key, value in kwargs if not
                  (key == '_scope' or key == '_name')]

        self.indent()
        self.write("use %s" % code[0].value.args[0].s)
        args.pop(0)

        arglist = []
        if args or kwargs or exargs or exkwargs:
            self.write("(")
            arglist.extend(args)
            arglist.extend("%s=%s" % i for i in kwargs)
            if exargs:
                arglist.append("*%s" % exargs)
            if exkwargs:
                arglist.append("**%s" % exkwargs)
            self.write(", ".join(arglist))
            self.write(")")
    dispatch[('renpy', 'use_screen')] = print_use

    def print_default(self, header, code):
        if (len(code) != 1 or code[0].value.keywords or code[0].value.kwargs or
            len(code[0].value.args) != 2 or code[0].value.starargs or
            not isinstance(code[0].value.args[0], ast.Str)):
            return self.print_python(header, code)
        self.indent()
        self.write("default %s = %s" %
            (code[0].value.args[0].s, self.to_source(code[0].value.args[1])))
    dispatch[('_scope', 'setdefault')] = print_default

    # These never have a ui.close() at the end
    def print_nochild(self, header, code):
        if len(code) != 1:
            self.print_python(header, code)
            return
        line = code[0]
        self.indent()
        self.write(line.value.func.attr)
        self.print_args(line.value)
        self.print_keywords_and_nodes(line.value, None, False, False)
    dispatch[('ui', 'add')]          = print_nochild
    dispatch[('ui', 'imagebutton')]  = print_nochild
    dispatch[('ui', 'input')]        = print_nochild
    dispatch[('ui', 'key')]          = print_nochild
    dispatch[('ui', 'label')]        = print_nochild
    dispatch[('ui', 'text')]         = print_nochild
    dispatch[('ui', 'null')]         = print_nochild
    dispatch[('ui', 'mousearea')]    = print_nochild
    dispatch[('ui', 'textbutton')]   = print_nochild
    dispatch[('ui', 'timer')]        = print_nochild
    dispatch[('ui', 'bar')]          = print_nochild
    dispatch[('ui', 'vbar')]         = print_nochild
    dispatch[('ui', 'hotbar')]       = print_nochild
    dispatch[('ui', 'on')]           = print_nochild
    dispatch[('ui', 'image')]        = print_nochild

    # These functions themselves don't have a ui.close() at the end, but
    # they're always immediately followed by one that does (usually
    # ui.child_or_fixed(), but also possibly one set with "has")
    def print_onechild(self, header, code, has_block=False):
        # We expect to have at least ourself, one child, and ui.close()
        if len(code) < 3 or self.get_dispatch_key(code[-1]) != ('ui', 'close'):
            if has_block:
                raise BadHasBlockException()
            self.print_python(header, code)
            return
        line = code[0]
        name = line.value.func.attr
        if name == 'hotspot_with_child':
            name = 'hotspot'
        if self.get_dispatch_key(code[1]) != ('ui', 'child_or_fixed'):
            # Handle the case where a "has" statement was used
            if has_block:
                # Ren'Py lets users nest "has" blocks for some reason, and it
                # puts the ui.close() statement in the wrong place when they do.
                # Since we checked for ui.close() being in the right place
                # before, the only way we could ever get here is if a user added
                # one inside a python block at the end. If this happens, turn
                # the whole outer block into Python instead of screencode.
                raise BadHasBlockException()
            if not self.parse_header(code[1]):
                self.print_python(header, code)
                return
            block = code[1:]
            state = self.save_state()
            try:
                self.indent()
                self.write(name)
                self.print_args(line.value)
                self.print_keywords_and_nodes(line.value, None, True, False)
                self.indent_level += 1
                if len(block) > 1 and isinstance(block[1], ast.Expr):
                    # If this isn't true, we'll get a BadHasBlockException
                    # later anyway. This check is just to keep it from being
                    # an exception that we can't handle.
                    self.advance_to_line(block[1].value.lineno)
                self.indent()
                self.write("has ")
                self.indent_level -= 1
                self.skip_indent_until_write = True
                self.print_nodes(block, 1, True)
            except BadHasBlockException as e:
                self.rollback_state(state)
                self.print_python(header, code)
            else:
                self.commit_state(state)
        else:
            # Remove ourself, ui.child_or_fixed(), and ui.close()
            block = code[2:-1]
            if block and not self.parse_header(block[0]):
                if has_block:
                    raise BadHasBlockException()
                self.print_python(header, code)
                return
            self.indent()
            self.write(name)
            self.print_args(line.value)
            self.print_keywords_and_nodes(line.value, block, False, has_block)
    dispatch[('ui', 'button')]             = print_onechild
    dispatch[('ui', 'frame')]              = print_onechild
    dispatch[('ui', 'transform')]          = print_onechild
    dispatch[('ui', 'viewport')]           = print_onechild
    dispatch[('ui', 'window')]             = print_onechild
    dispatch[('ui', 'drag')]               = print_onechild
    dispatch[('ui', 'hotspot_with_child')] = print_onechild

    # These always have a ui.close() at the end
    def print_manychildren(self, header, code, has_block=False):
        if (self.get_dispatch_key(code[-1]) != ('ui', 'close') or
            (len(code) != 2 and not self.parse_header(code[1]))):
            if has_block:
                raise BadHasBlockException()
            self.print_python(header, code)
            return
        line = code[0]
        block = code[1:-1]
        self.indent()
        self.write(line.value.func.attr)
        self.print_args(line.value)
        self.print_keywords_and_nodes(line.value, block, False, has_block)
    dispatch[('ui', 'fixed')]        = print_manychildren
    dispatch[('ui', 'grid')]         = print_manychildren
    dispatch[('ui', 'hbox')]         = print_manychildren
    dispatch[('ui', 'side')]         = print_manychildren
    dispatch[('ui', 'vbox')]         = print_manychildren
    dispatch[('ui', 'imagemap')]     = print_manychildren
    dispatch[('ui', 'draggroup')]    = print_manychildren

    # Parsing functions

    def parse_header(self, header):
        # Given a Python AST node, returns the parent ID if the node represents
        # a header, or None otherwise.
        if (isinstance(header, ast.Assign) and len(header.targets) == 1 and
                isinstance(header.targets[0], ast.Name) and
                re.match(r"_[0-9]+$", header.targets[0].id) and
                isinstance(header.value, ast.Tuple) and
                len(header.value.elts) == 2 and
                isinstance(header.value.elts[0], ast.Name)):
            parent_id = header.value.elts[0].id
            index = header.value.elts[1]
            if re.match(r"_([0-9]+|name)$", parent_id) and (
                    isinstance(index, ast.Num) or
                    (isinstance(index, ast.Name) and
                    re.match(r"_[0-9]+$", index.id))):
                return parent_id
        return None

    def parse_args(self, node):
        return ([self.to_source(i) for i in node.value.args],
            [(i.arg, self.to_source(i.value)) for i in node.value.keywords],
            node.value.starargs and self.to_source(node.value.starargs),
            node.value.kwargs and self.to_source(node.value.kwargs))

class BadHasBlockException(Exception):
    pass