from __future__ import unicode_literals
import sys

class DecompilerBase(object):
    def __init__(self, out_file=None, indentation = '    '):
        self.out_file = out_file or sys.stdout
        self.indentation = indentation

    def dump(self, ast, indent_level=0):
        """
        Write the decompiled representation of `ast` into the opened file given in the constructor
        """
        self.indent_level = indent_level
        if isinstance(ast, (tuple, list)):
            self.print_nodes(ast)
        else:
            self.print_node(ast)

    def write(self, string):
        """
        Shorthand method for writing `string` to the file
        """
        self.out_file.write(unicode(string))

    def indent(self):
        """
        Shorthand method for pushing a newline and indenting to the proper indent level
        """
        self.write('\n' + self.indentation * self.indent_level)

    def print_nodes(self, ast, extra_indent=0):
        # This node is a list of nodes
        # Print every node
        self.indent_level += extra_indent
        for node in ast:
            self.print_node(node)
        self.indent_level -= extra_indent

    def print_unknown(self, ast):
        # If we encounter a placeholder note, print a warning and insert a placeholder
        print "Unknown AST node: %s" % str(type(ast))
        self.indent()
        self.write("<<<UNKNOWN NODE %s>>>" % str(type(ast)))

    def print_node(self, ast):
        raise NotImplementedError()

class First(object):
    # An often used pattern is that on the first item
    # of a loop something special has to be done. This class
    # provides an easy object which on the first access
    # will return True, but any subsequent accesses False
    def __init__(self, yes_value=True, no_value=False):
        self.yes_value = yes_value
        self.no_value = no_value
        self.first = True

    def __call__(self):
        if self.first:
            self.first = False
            return self.yes_value
        else:
            return self.no_value

def reconstruct_paraminfo(paraminfo):
    if paraminfo is None:
        return ""

    rv = ["("]

    sep = First("", ", ")
    positional = [i for i in paraminfo.parameters if i[0] in paraminfo.positional]
    nameonly = [i for i in paraminfo.parameters if i not in positional]
    for parameter in positional:
        rv.append(sep())
        rv.append(parameter[0])
        if parameter[1] is not None:
            rv.append(" = %s" % parameter[1])
    if paraminfo.extrapos:
        rv.append(sep())
        rv.append("*%s" % paraminfo.extrapos)
    if nameonly:
        if not paraminfo.extrapos:
            rv.append(sep())
            rv.append("*")
        for param in nameonly:
            rv.append(sep())
            rv.append(parameter[0])
            if param[1] is not None:
                rv.append(" = %s" % parameter[1])
    if paraminfo.extrakw:
        rv.append(sep())
        rv.append("**%s" % paraminfo.extrakw)

    rv.append(")")

    return "".join(rv)

def reconstruct_arginfo(arginfo):
    if arginfo is None:
        return ""

    rv = ["("]
    sep = First("", ", ")
    for (name, val) in arginfo.arguments:
        rv.append(sep())
        if name is not None:
            rv.append("%s = " % name)
        rv.append(val)
    if arginfo.extrapos:
        rv.append(sep())
        rv.append("*%s" % arginfo.extrapos)
    if arginfo.extrakw:
        rv.append(sep())
        rv.append("**%s" % arginfo.extrakw)
    rv.append(")")

    return "".join(rv)

def string_escape(s):
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\t', '\\t')
    return s