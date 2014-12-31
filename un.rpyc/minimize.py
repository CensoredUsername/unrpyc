# A module which minimizes other python code

import ast
import sys
sys.path.append("../decompiler")
import codegen

def minimize(code):
    tree = ast.parse(code)
    tree = Crusher().visit(tree)
    generator = SourceGenerator(" ", False)
    generator.visit(tree)
    newcode = ''.join(generator.result)
    return newcode

class Crusher(ast.NodeTransformer):
    def __init__(self):
        ast.NodeTransformer.__init__(self)
        self.scopes = [{}]
        self.varnames = [0]

    def visit_Expr(self, node):
        # Remove any kind of string which does nothing
        if isinstance(node.value, ast.Str):
            return None
        else:
            return self.generic_visit(node)

    def visit_ClassDef(self, node):
        # classes have a scope which should not be munged
        self.scopes.append(())
        self.varnames.append(0)
        rv = self.generic_visit(node)
        self.scopes.pop()
        self.varnames.pop()
        return rv

    def visit_FunctionDef(self, node):
        # functions have a scope
        self.scopes.append({})
        self.varnames.append(0)
        rv = self.generic_visit(node)
        self.scopes.pop()
        self.varnames.pop()
        return rv

    def genvarname(self):
        # Generate a varname to the proper scope
        current = sum(self.varnames)
        self.varnames[-1] += 1

        rv = []
        while True:
            rv.append(chr(current % 26 + 97))
            current //= 26
            if not current:
                break

        return ''.join(reversed(rv))

    def visit_Global(self, node):
        # Global means don't munge name except with lowest scope
        for name in node.names:
            if name in self.scopes[0]:
                self.scopes[-1][name] = self.scopes[0][name]
            else:
                self.scopes[-1][name] = name
        return node

    def visit_arguments(self, node):
        freelen = len(node.args) - len(node.defaults)
        args = []
        for i, arg in enumerate(node.args):
            args.append(self.visit_Name(arg, i >= freelen))

        defaults = []
        for i in node.defaults:
            defaults.append(self.generic_visit(i))

        return ast.arguments(args, node.vararg, node.kwarg, defaults)

    def visit_Name(self, node, iskwarg=False):
        if self.scopes[-1] == ():
            # can't munge class scope due to self.*
            return node

        elif (isinstance(node.ctx, (ast.Store, ast.AugStore, ast.Param)) and not
                node.id in self.scopes[-1]
                and not iskwarg):
            # On first write to a variable: record a munged name
            name = self.genvarname()
            self.scopes[-1][node.id] = name
            return ast.Name(name, node.ctx)

        if isinstance(node.ctx, (ast.Param)):
            # Can't munge kwargs
            if node.id == "self":
                print("self is not a kwarg")
            self.scopes[-1][node.id] = node.id
            return node

        else:
            # Then on reading, substitute said name
            for scope in reversed(self.scopes):
                if node.id in scope:
                    return ast.Name(scope[node.id], node.ctx)
            else:
                self.scopes[-1][node.id] = node.id
                return node

class SourceGenerator(codegen.SourceGenerator):
    def __init__(self, indent_with, add_line_information=False):
        codegen.SourceGenerator.__init__(self, indent_with, add_line_information)
        self.new_line = True

    def body(self, statements):
        self.new_line = True
        if len(statements) == 1:
            if not isinstance(statements[0], (ast.If,
                                              ast.For,
                                              ast.While,
                                              ast.With,
                                              ast.TryExcept,
                                              ast.TryFinally,
                                              ast.FunctionDef,
                                              ast.ClassDef)):
                self.new_line = False
        self.indentation += 1
        for stmt in statements:
            self.visit(stmt)
        self.indentation -= 1

    def newline(self, node=None, extra=0):
        # ignore extra
        if self.new_line:
            self.new_lines = max(self.new_lines, 1)
        else:
            self.new_lines = 0
            self.new_line = True

        if node is not None and self.add_line_information:
            self.write('# line: %s' % node.lineno)
            self.new_lines = 1
