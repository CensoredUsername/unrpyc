

from __future__ import unicode_literals
from util import DecompilerBase, WordConcatenator, Dispatcher

import renpy

def pprint(out_file, ast, options,
           indent_level=0, linenumber=1, skip_indent_until_write=False):
    return ATLDecompiler(out_file, options).dump(
        ast, indent_level, linenumber, skip_indent_until_write)

class ATLDecompiler(DecompilerBase):
    """
    An object that handles decompilation of atl blocks from the ren'py AST
    """

    dispatch = Dispatcher()

    def dump(self, ast, indent_level=0, linenumber=1, skip_indent_until_write=False):
        # At this point, the preceding ":" has been written, and indent hasn't been increased yet.
        # There's no common syntax for starting an ATL node, and the base block that is created
        # is just a RawBlock. normally RawBlocks are created witha block: statement so we cannot
        # just reuse the node for that. Instead, we implement the top level node directly here
        self.indent_level = indent_level
        self.linenumber = linenumber
        self.skip_indent_until_write = skip_indent_until_write

        self.print_block(ast)

        return self.linenumber

    def print_node(self, ast):
        # Line advancement logic:
        if hasattr(ast, "loc"):
            if isinstance(ast, renpy.atl.RawBlock):
                self.advance_to_block(ast)

            else:
                self.advance_to_line(ast.loc[1])

        self.dispatch.get(type(ast), type(self).print_unknown)(self, ast)

    def print_block(self, block):
        # Prints a block of ATL statements
        # block is a renpy.atl.RawBlock instance.
        with self.increase_indent():
            if block.statements:
                self.print_nodes(block.statements)

            # If a statement ends with a colon but has no block after it, loc will
            # get set to ('', 0). That isn't supposed to be valid syntax, but it's
            # the only thing that can generate that, so we do not write "pass" then.
            elif block.loc != ('', 0):

                # if there were no contents insert a pass node to keep syntax valid.
                self.indent()
                self.write("pass")

    def advance_to_block(self, block):
        # note: the location property of a RawBlock points to the first line of the block,
        # not the statement that created it.
        # it can also contain the following nonsense if there was no block for some reason.
        if block.loc != ('', 0):
            self.advance_to_line(block.loc[1] - 1)

    @dispatch(renpy.atl.RawMultipurpose)
    def print_atl_rawmulti(self, ast):
        warp_words = WordConcatenator(False)

        # warpers
        # I think something changed about the handling of pause, that last special case doesn't look necessary anymore
        # as a proper pause warper exists now but we'll keep it around for backwards compatability
        if ast.warp_function:
            warp_words.append("warp", ast.warp_function, ast.duration)
        elif ast.warper:
            warp_words.append(ast.warper, ast.duration)
        elif ast.duration != "0":
            warp_words.append("pause", ast.duration)

        warp = warp_words.join()
        words = WordConcatenator(warp and warp[-1] != ' ', True)

        # revolution
        if ast.revolution:
            words.append(ast.revolution)

        # circles
        if ast.circles != "0":
            words.append("circles %s" % ast.circles)

        # splines
        spline_words = WordConcatenator(False)
        for name, expressions in ast.splines:
            spline_words.append(name, expressions[-1])
            for expression in expressions[:-1]:
                spline_words.append("knot", expression)
        words.append(spline_words.join())

        # properties
        property_words = WordConcatenator(False)
        for key, value in ast.properties:
            property_words.append(key, value)
        words.append(property_words.join())

        # with
        expression_words = WordConcatenator(False)
        # TODO There's a lot of cases where pass isn't needed, since we could
        # reorder stuff so there's never 2 expressions in a row. (And it's never
        # necessary for the last one, but we don't know what the last one is
        # since it could get reordered.)
        needs_pass = len(ast.expressions) > 1
        for (expression, with_expression) in ast.expressions:
            expression_words.append(expression)
            if with_expression:
                expression_words.append("with", with_expression)
            if needs_pass:
                expression_words.append("pass")
        words.append(expression_words.join())

        to_write = warp + words.join()
        if to_write:
            self.indent()
            self.write(to_write)
        else:
            # A trailing comma results in an empty RawMultipurpose being
            # generated on the same line as the last real one.
            self.write(",")

    @dispatch(renpy.atl.RawBlock)
    def print_atl_rawblock(self, ast):
        self.indent()
        self.write("block:")
        self.print_block(ast)

    @dispatch(renpy.atl.RawChild)
    def print_atl_rawchild(self, ast):
        for child in ast.children:
            self.advance_to_block(child)
            self.indent()
            self.write("contains:")
            self.print_block(child)

    @dispatch(renpy.atl.RawChoice)
    def print_atl_rawchoice(self, ast):
        for chance, block in ast.choices:
            self.advance_to_block(block)
            self.indent()
            self.write("choice")
            if chance != "1.0":
                self.write(" %s" % chance)
            self.write(":")
            self.print_block(block)
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
            self.advance_to_block(block)
            self.indent()
            self.write("on %s:" % name)
            self.print_block(block)

    @dispatch(renpy.atl.RawParallel)
    def print_atl_rawparallel(self, ast):
        for block in ast.blocks:
            self.advance_to_block(block)
            self.indent()
            self.write("parallel:")
            self.print_block(block)
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
