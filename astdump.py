import sys
import inspect
import codegen
import ast as py_ast

EXTRACT_PYTHON_AST  =False
DECOMPILE_PYTHON_AST=True

def pprint(out_file, ast):
    AstDumper(out_file).dump(ast)

class AstDumper(object):
    def __init__(self, out_file=None, indentation='    '):
        self.indentation = indentation
        self.out_file = out_file or sys.stdout
        self.map_open = {list: '[', tuple: '(', set: '{', frozenset: 'frozenset({'}
        self.map_close= {list: ']', tuple: ')', set: '}', frozenset: '}'}

    def dump(self, ast):
        self.indent = 0
        self.passed = [] #recursiveness checks
        self.print_ast(ast)

    def print_ast(self, ast):
        if ast in self.passed:
            self.print_other(ast)
            return
        self.passed.append(ast)
        if isinstance(ast, (list, tuple, set, frozenset)):
            self.print_list(ast)
        elif isinstance(ast, dict):
            self.print_dict(ast)
        elif isinstance(ast, (str, unicode)):
            self.print_string(ast)
        elif isinstance(ast, (int, bool)) or ast is None:
            self.print_other(ast)
        elif isinstance(ast, object):
            self.print_object(ast)
        else:
            self.print_other(ast)
        self.passed.pop()

    def print_list(self, ast):
        self.p(self.map_open[ast.__class__])
        
        self.ind(1, ast)
        for i, obj in enumerate(ast):
            self.print_ast(obj)
            if i+1 != len(ast):
                self.p(',')
                self.ind()
        self.ind(-1, ast)
        self.p(self.map_close[ast.__class__])

    def print_dict(self, ast):
        self.p('{')

        self.ind(1, ast)
        for i, key in enumerate(ast):
            self.print_ast(key)
            p(': ')
            self.print_ast(ast[key])
            if i+1 != len(ast):
                self.p(',')
                self.ind()
        self.ind(-1, ast)
        self.p('}')

    def print_object(self, ast):
        self.p('<')
        self.p(str(ast.__class__)[8:-2] if hasattr(ast, '__class__')  else str(ast))
        self.p('>< ')

        if not EXTRACT_PYTHON_AST and isinstance(ast, py_ast.Module):
            self.p('.code = ')
            if DECOMPILE_PYTHON_AST:
                self.print_ast(codegen.to_source(ast, unicode(self.indentation)))
            else:
                self.print_ast('PYTHON SCREEN CODE')
            self.p('>')
            return

        keys = list(i for i in dir(ast) if not i.startswith('__') and hasattr(ast, i) and not inspect.isroutine(getattr(ast, i)))
        self.ind(1, keys)
        for i, key in enumerate(keys):
            self.p('.')
            self.p(str(key))
            self.p(' = ')
            self.print_ast(getattr(ast, key))
            if i+1 != len(keys):
                self.p(',')
                self.ind()
        self.ind(-1, keys)
        self.p('>')

    def print_string(self, ast):
        if '\n' in ast:
            astlist = ast.split('\n')
            if isinstance(ast, unicode):
                self.p('u')
            self.p('"""')
            self.p(self.escape_string(astlist.pop(0)))
            for i, item in enumerate(astlist):
                self.p('\n')
                self.p(self.escape_string(item))
            self.p('"""')
            self.ind()

        else:
            self.p(repr(ast))

    def escape_string(self, string):
        if isinstance(string, unicode):
            return repr(string)[2:-1]
        elif isinstance(string, str):
            return repr(string)[1:-1]
        else:
            return string

    def print_other(self, ast):
        self.p(repr(ast))

    def ind(self, diff_indent=0, ast=None):
        if ast is None or len(ast) > 1:
            self.indent += diff_indent
            self.p('\n' + self.indentation * self.indent)

    def p(self, string):
        self.out_file.write(unicode(string))