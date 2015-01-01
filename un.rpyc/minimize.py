# A module which minimizes other python code

import ast
import sys
sys.path.append("../decompiler")
import codegen

def minimize(code, obfuscate_globals=False, obfuscate_builtins=False, obfuscate_imports=False):
    tree = ast.parse(code)
    tree = DocstringRemover().visit(tree)
    tree = Crusher(obfuscate_globals, obfuscate_builtins, obfuscate_imports).visit(tree)
    generator = DenseSourceGenerator(" ", False)
    generator.visit(tree)
    newcode = ''.join(generator.result)
    return newcode

class DocstringRemover(ast.NodeTransformer):
    def visit_Expr(self, node):
        # Remove any kind of string which does nothing
        if isinstance(node.value, ast.Str):
            return None
        else:
            return self.generic_visit(node)    

class Crusher(ast.NodeTransformer):
    def __init__(self, munge_globals=False, munge_builtins=False, munge_imports=False):
        ast.NodeTransformer.__init__(self)

        # Don't munge builtins
        self.NOMUNGE_BUILTINS = not munge_builtins
        # Don't munge globals
        self.NOMUNGE_GLOBALS = not munge_globals
        # Don't munge imports
        self.NOMUNGE_IMPORTS = not munge_imports

        # Scope stack
        self.scopes = [{}]
        # keep track of available varnames on a per-scope basis
        self.varnames = [0]
        self.maxvarname = -1
        # set of all used builtins
        self.builtins = {}
        # List of all name nodes
        self.namenodes = []
        # List of scope-bearing statements discovered in the
        # current scope
        self.subscopes = []

    # Local mangling logic
    def genvarname(self, on_max=False):
        # Generate a varname to the proper scope
        if not on_max:
            current = sum(self.varnames)
            self.maxvarname = max(current, self.maxvarname)
            self.varnames[-1] += 1
        else:
            self.maxvarname += 1
            current = self.maxvarname

        rv = []
        while True:
            rv.append(chr(current % 26 + 97))
            current //= 26
            if not current:
                break

        return ''.join(reversed(rv))

    def write_var(self, name, nomunge=False):
        if name in self.scopes[-1]:
            return self.scopes[-1][name]
        elif self.scopes[-1] == ():
            # we're in a class
            return name
        elif nomunge or (self.NOMUNGE_GLOBALS and len(self.scopes) == 1):
            self.scopes[-1][name] = name
            return name
        else:
            newname = self.genvarname()
            self.scopes[-1][name] = newname
            return newname

    def read_var(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        else:
            if self.scopes[-1] == ():
                return name
            if name in self.builtins:
                self.builtins[name] += 1
            else:
                self.builtins[name] = 1
            # if read and then write: don't generate a new name on write
            self.scopes[-1][name] = name
            return name

    def _visit_name(self, node, iskwarg=False):
        if isinstance(node.ctx, (ast.Store, ast.AugStore, ast.Param)):
            # On first write to a variable: record a munged name
            # except when iskwarg is set
            return ast.Name(self.write_var(node.id, iskwarg), node.ctx)

        else:
            # Then on reading, substitute said name
            return ast.Name(self.read_var(node.id), node.ctx)

    def visit_Name(self, node, iskwarg=False):
        node = self._visit_name(node, iskwarg)
        self.namenodes.append(node)
        return node

    # Special nodes
    def register_import(self, alias, module=None):
        if self.scopes[-1] != ():
            if alias.asname is not None:
                alias.asname = self.write_var(alias.asname, self.NOMUNGE_IMPORTS)
            elif alias.name == "*":
                # Dangerous.
                __import__(module)
                mod = sys.modules[module]
                if hasattr(mod, "__all__"):
                    names = mod.__all__
                else:
                    names = [name for name in mod.__dict__ if not name.startswith("_")]
                for name in names:
                    self.write_var(name, True)
            elif module == "__future__":
                name = alias.name.split(".", 1)[0]
                self.write_var(name, True)
            else:
                name = alias.name.split(".", 1)[0]
                newname = self.write_var(name, self.NOMUNGE_IMPORTS)
                if newname != name and newname != alias.asname:
                    alias.asname = newname

    def visit_Import(self, node):
        for name in node.names:
            self.register_import(name)
        return self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for name in node.names:
            self.register_import(name, node.module)
        return self.generic_visit(node)

    def visit_subscopes(self):
        subscopes = self.subscopes
        self.subscopes = []
        for node in subscopes:
            method = 'visit_' + node.__class__.__name__
            visitor = getattr(self, method, self.generic_visit)
            visitor(node, True) #subscope pass should only alter nodes

    def visit_Module(self, node):
        # Due to dynamic scoping, analyze all global class/module defs
        # Before doing the actual walking
        # for child in node.body:
        #     if isinstance(child, (ast.ClassDef, ast.FunctionDef)):
        #         self.write_var(child.name, True)
        self.generic_visit(node)
        # subscope pass
        self.visit_subscopes()

        # builtins processing

        if not self.NOMUNGE_BUILTINS:
            self.builtins = set(key for key, value in self.builtins.iteritems()
                                if value > 1)
            builtin_names = [name for name in self.namenodes
            if name.id in self.builtins]
            scope = dict((key, self.genvarname(True)) for key in self.builtins)
            for name in builtin_names:
                name.id = scope[name.id]

            extra_nodes = [ast.Assign([ast.Name(value, ast.Store())], ast.Name(key, ast.Load()))
                           for key, value in scope.iteritems()]
            futures = [future for future in node.body if
                       isinstance(future, ast.ImportFrom) and future.module == "__future__"]
            for future in futures:
                node.body.remove(future)
            node.body = futures + extra_nodes + node.body

        return node

    def visit_ClassDef(self, node, parse_subscope=False):
        if parse_subscope:
            # classes have a scope which should not be munged
            self.scopes.append(())
            self.varnames.append(0)
            # First pass
            self.generic_visit(node)
            # Subscope pass
            self.visit_subscopes()
            self.scopes.pop()
            self.varnames.pop()
        else:
            # add name to outer scope but don't munge it
            self.write_var(node.name, True)
            # set this node to be parsed later
            self.subscopes.append(node)
        return node

    def visit_FunctionDef(self, node, parse_subscope=False):
        if parse_subscope:
            # functions have a scope
            self.scopes.append({})
            self.varnames.append(0)
            # First pass
            self.generic_visit(node)
            # Subscope pass
            self.visit_subscopes()
            self.scopes.pop()
            self.varnames.pop()
        else:
            # add name to outer scope but don't munge it
            self.write_var(node.name, True)
            # set this node to be parsed later
            self.subscopes.append(node)
        return node

    def visit_Global(self, node):
        # Global means don't munge name except with lowest scope
        for name in node.names:
            if name in self.scopes[0]:
                self.scopes[-1][name] = self.scopes[0][name]
            else: # elif self.NOMUNGE_GLOBALS:
                self.scopes[-1][name] = self.scopes[0][name] = name
            # else:
                # Annoying, can't determine correct varname to use for global here
                # newname = genvarname()
        return node

    def visit_arguments(self, node):
        freelen = len(node.args) - len(node.defaults)
        args = []
        for i, arg in enumerate(node.args):
            args.append(self.visit_Name(arg, i >= freelen))

        defaults = []
        for i in node.defaults:
            defaults.append(self.visit(i))

        vararg = self.write_var(node.vararg) if node.vararg else None
        kwarg = self.write_var(node.kwarg) if node.kwarg else None

        return ast.arguments(args, vararg, kwarg, defaults)

    # make sure comprehensions actually respect the evaluation order
    def visit_ListComp(self, node):
        comps = []
        for comp in reversed(node.generators):
            comps.append(self.visit(comp))
        elt = self.visit(node.elt)
        return node.__class__(elt, list(reversed(comps)))

    visit_GeneratorExp = visit_ListComp
    visit_SetComp = visit_ListComp

    def visit_DictComp(self, node):
        comps = []
        for comp in reversed(node.generators):
            comps.append(self.visit(comp))
        key = self.visit(node.key)
        value = self.visit(node.value)
        return ast.DictComp(key, value, list(reversed(comps)))

BOOLOP_SYMBOLS = {
    ast.And:        (' and ', 4),
    ast.Or:         (' or ', 3)
}

BINOP_SYMBOLS = {
    ast.Add:        ('+', 11),
    ast.Sub:        ('-', 11),
    ast.Mult:       ('*', 12),
    ast.Div:        ('/', 12),
    ast.FloorDiv:   ('//', 12),
    ast.Mod:        ('%', 12),
    ast.Pow:        ('**', 14),
    ast.LShift:     ('<<', 10),
    ast.RShift:     ('>>', 10),
    ast.BitOr:      ('|', 7),
    ast.BitAnd:     ('&', 9),
    ast.BitXor:     ('^', 8)
}

CMPOP_SYMBOLS = {
    ast.Eq:         ('==', 6),
    ast.Gt:         ('>', 6),
    ast.GtE:        ('>=', 6),
    ast.In:         (' in ', 6),
    ast.Is:         (' is ', 6),
    ast.IsNot:      (' is not ', 6),
    ast.Lt:         ('<', 6),
    ast.LtE:        ('<=', 6),
    ast.NotEq:      ('!=', 6),
    ast.NotIn:      (' not in ', 6)
}

UNARYOP_SYMBOLS = {
    ast.Invert:     ('~', 13),
    ast.Not:        ('not ', 5),
    ast.UAdd:       ('+', 13),
    ast.USub:       ('-', 13)
}

class DenseSourceGenerator(codegen.SourceGenerator):
    def __init__(self, indent_with, add_line_information=False):
        codegen.SourceGenerator.__init__(self, indent_with, add_line_information)
        self.new_line = True

    def body(self, statements):
        self.new_line = True
        if len(statements) == 1:
            if not isinstance(statements[0], (ast.If, ast.For,
                    ast.While, ast.With, ast.TryExcept, ast.TryFinally,
                    ast.FunctionDef, ast.ClassDef)):
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

    def visit_Dict(self, node):
        self.write('{')
        for idx, (key, value) in enumerate(zip(node.keys, node.values)):
            if idx:
                self.write(',')
            self.visit(key)
            self.write(':')
            self.visit(value)
        self.write('}')

    def visit_Call(self, node):
        want_comma = []
        def write_comma():
            if want_comma:
                self.write(',')
            else:
                want_comma.append(True)

        self.visit(node.func)
        self.write('(')
        for arg in node.args:
            write_comma()
            self.visit(arg)
        for keyword in node.keywords:
            write_comma()
            self.write(keyword.arg + '=')
            self.visit(keyword.value)
        if node.starargs is not None:
            write_comma()
            self.write('*')
            self.visit(node.starargs)
        if node.kwargs is not None:
            write_comma()
            self.write('**')
            self.visit(node.kwargs)
        self.write(')')

    def _sequence_visit(left, right): # pylint: disable=E0213
        def visit(self, node):
            self.write(left)
            for idx, item in enumerate(node.elts):
                if idx:
                    self.write(',')
                self.visit(item)
            self.write(right)
        return visit

    visit_List = _sequence_visit('[', ']')
    visit_Set = _sequence_visit('{', '}')

    def visit_Tuple(self, node, guard=True):
        if guard:
            self.write('(')
        idx = -1
        for idx, item in enumerate(node.elts):
            if idx:
                self.write(',')
            self.visit(item)
        if guard:
            self.write(idx and ')' or ',)')

    def visit_Assign(self, node):
        self.newline(node)
        for idx, target in enumerate(node.targets):
            if isinstance(target, ast.Tuple):
                self.visit_Tuple(target, False)
            else:
                self.visit(target)
            self.write('=')
        self.visit(node.value)

    def visit_BinOp(self, node):
        symbol, precedence = BINOP_SYMBOLS[type(node.op)]
        if self.prec_start(precedence):
            self.write('(')
        self.visit(node.left)
        self.write('%s' % symbol)
        self.visit(node.right)
        if self.prec_end():
            self.write(')')

    def visit_BoolOp(self, node):
        symbol, precedence = BOOLOP_SYMBOLS[type(node.op)]
        if self.prec_start(precedence):
            self.write('(')
        for idx, value in enumerate(node.values):
            if idx:
                self.write('%s' % symbol)
            self.visit(value)
        if self.prec_end():
            self.write(')')

    def visit_Compare(self, node):
        if self.prec_start(6):
            self.write('(')
        self.visit(node.left)
        for op, right in zip(node.ops, node.comparators):
            self.write('%s' % CMPOP_SYMBOLS[type(op)][0])
            self.visit(right)
        if self.prec_end():
            self.write(')')

    def visit_UnaryOp(self, node):
        symbol, precedence = UNARYOP_SYMBOLS[type(node.op)]
        if self.prec_start(precedence):
            self.write('(')
        self.write(symbol)
        self.visit(node.operand)
        if self.prec_end():
            self.write(')')

    def visit_Lambda(self, node):
        if self.prec_start(1):
            self.write('(')
        self.write('lambda ')
        self.signature(node.args)
        self.write(':')
        self.visit(node.body)
        if self.prec_end():
            self.write(')')

    def signature(self, node):
        want_comma = []
        def write_comma():
            if want_comma:
                self.write(',')
            else:
                want_comma.append(True)

        padding = [None] * (len(node.args) - len(node.defaults))
        for arg, default in zip(node.args, padding + node.defaults):
            write_comma()
            self.visit(arg)
            if default is not None:
                self.write('=')
                self.visit(default)
        if node.vararg is not None:
            write_comma()
            self.write('*' + node.vararg)
        if node.kwarg is not None:
            write_comma()
            self.write('**' + node.kwarg)

    def visit_For(self, node):
        self.newline(node)
        self.write('for ')
        if isinstance(node.target, ast.Tuple):
            self.visit_Tuple(node.target, False)
        else:
            self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        self.write(':')
        self.body_or_else(node)