# Copyright (c) 2012 Yuri K. Schlesner
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
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import renpy.ast as ast
import renpy.atl as atl
import codegen
import screendecompiler

def pretty_print_ast(out_file, ast):
    for stmt in ast:
        print_statement(out_file, stmt, 0)

def indent(f, level):
    # Print indentation
    f.write(u'    ' * level)

def print_statement(f, statement, indent_level=0):
    indent(f, indent_level)

    func = statement_printer_dict.get(type(statement), print_Unknown)
    func(f, statement, indent_level)

def escape_string(s):
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\t', '\\t')
    return s

# TODO fix "pause 0" at the beginning of lines with no warp
# TODO "choice" and "parallel" blocks are greedily combined
#      so we need a "pass" statement to separate them if
#      multiple of the same block are immediately after
#      each other.
def print_atl(f, atl_block, indent_level):
    for stmt in atl_block.statements:
        indent(f, indent_level)
        
        if type(stmt) is atl.RawMultipurpose:
            # warper
            if stmt.warp_function:
                f.write(u"warp %s" % (stmt.warp_function.strip(), ))
            else:
                f.write(stmt.warper or "pause")
            
            # duration
            f.write(u" %s" % (stmt.duration.strip(), ))
            
            # revolution
            if stmt.revolution:
                f.write(u" %s" % (stmt.revolution, ))
            
            # circles
            if stmt.circles != "0":
                f.write(u" circles %s" % (stmt.circles.strip(), ))
            
            # splines
            for (name, exprs) in stmt.splines:
                f.write(u" %s" % (name, ))
                for expr in exprs:
                    f.write(u" knot %s" % (expr.strip(), ))
            
            # properties
            for (k, v) in stmt.properties:
                f.write(u" %s %s" % (k, v.strip()))
            
            # with
            for (expr, with_expr) in stmt.expressions:
                f.write(u" %s" % (expr.strip(), ))
                if with_expr:
                    f.write(u" with %s" % (with_expr, ))
            
            f.write(u"\n")
        
        elif type(stmt) is atl.RawBlock:
            # what does stmt.animation do?
            f.write(u"block:\n")
            print_atl(f, stmt, indent_level + 1)
        
        elif type(stmt) is atl.RawChoice:
            first = True
            for (chance, block) in stmt.choices:
                if first:
                    first = False
                else:
                    indent(f, indent_level)
                
                f.write(u"choice")
                if chance != "1.0":
                    f.write(u" %s" % (chance, ))
                f.write(u":\n")
                print_atl(f, block, indent_level + 1)
        
        elif type(stmt) is atl.RawContainsExpr:
            f.write(u"contains %s\n" % (stmt.expression, ))
        
        elif type(stmt) is atl.RawEvent:
            f.write(u"event %s\n" % (stmt.name, ))
        
        elif type(stmt) is atl.RawFunction:
            f.write(u"function %s\n" % (stmt.expr, ))
        
        elif type(stmt) is atl.RawOn:
            first = False
            for name, block in stmt.handlers.iteritems():
                if first:
                    first = True
                else:
                    indent(f, indent_level)
                
                f.write(u"on %s:\n" % (name, ))
                print_atl(f, block, indent_level + 1)
        
        elif type(stmt) is atl.RawParallel:
            first = True
            for block in stmt.blocks:
                if first:
                    first = False
                else:
                    indent(f, indent_level)
                
                f.write(u"parallel:\n")
                print_atl(f, block, indent_level + 1)
        
        elif type(stmt) is atl.RawRepeat:
            f.write(u"repeat")
            if stmt.repeats:
                f.write(u" %s" % (stmt.repeats, )) # not sure if this is even a string
            f.write(u"\n")
        
        elif type(stmt) is atl.RawTime:
            f.write(u"time %s\n" % (stmt.time, ))
        
        else:
            f.write(u"TODO atl.%s\n" % type(stmt).__name__)

def print_imspec(f, imspec):
    if imspec[1] is not None: # Expression
        f.write(imspec[1])
    else: # Image name
        f.write(' '.join(imspec[0]))

    # at
    if len(imspec[3]) > 0:
        f.write(u" at %s" % (', '.join(imspec[3])))

    # as
    if imspec[2] is not None:
        f.write(u" as %s" % (imspec[2], ))

    # behind
    if len(imspec[6]) > 0:
        f.write(u" behind %s" % (', '.join(imspec[6])))

    # onlayer
    if imspec[4] != 'master':
        f.write(u" onlayer %s" % (imspec[4], ))

    # zorder
    # This isn't in the docs, but it's in the parser
    if imspec[5] is not None:
        f.write(u" zorder %s" % (imspec[5], ))

def print_Label(f, stmt, indent_level):
    f.write(u"label %s" % (stmt.name, ))
    if stmt.parameters is not None:
        print_params(f, stmt.parameters)
    f.write(u':\n')

    for sub_stmt in stmt.block:
        print_statement(f, sub_stmt, indent_level + 1)

def print_Say(f, stmt, indent_level):
    if stmt.who is not None:
        f.write(u"%s " % (stmt.who, ))
    f.write(u"\"%s\"" % (escape_string(stmt.what), ))
    if stmt.with_ is not None:
        f.write(u" with %s" % (stmt.with_, ))
    f.write(u'\n')

def print_Jump(f, stmt, indent_level):
    f.write(u"jump ")
    if stmt.expression:
        # TODO expression
        f.write(u"expression TODO")
    else:
        f.write(stmt.target)
    f.write(u'\n')

def print_Scene(f, stmt, indent_level):
    f.write(u"scene")
    if stmt.imspec is None:
        if stmt.layer != 'master':
            f.write(u" onlayer %s" % (stmt.layer, ))
    else:
        f.write(u' ')
        print_imspec(f, stmt.imspec)

    # with isn't handled here, but split in several statements

    if stmt.atl is not None:
        f.write(u':\n')
        print_atl(f, stmt.atl, indent_level+1)
    else:
        f.write('\n')

def print_With(f, stmt, indent_level):
    f.write(u"with %s\n" % (stmt.expr, ))

def print_Show(f, stmt, indent_level):
    f.write(u"show ")
    print_imspec(f, stmt.imspec)

    # with isn't handled here, but split in several statements

    if stmt.atl is not None:
        f.write(u':\n')
        print_atl(f, stmt.atl, indent_level+1)
    else:
        f.write('\n')

def print_Hide(f, stmt, indent_level):
    f.write(u"hide ")
    print_imspec(f, stmt.imspec)

    # with isn't handled here, but split in several statements

    f.write('\n')

def print_Python(f, stmt, indent_level, early=False):
    code_src = stmt.code.source

    stripped_code = code_src.strip()

    if stripped_code.count('\n') == 0:
        f.write(u"$ %s\n" % (stripped_code, ))
    else:
        f.write(u"python")
        if early:
            f.write(u" early")
        if stmt.hide:
            f.write(u" hide")
        f.write(u":\n")

        for line in code_src.splitlines(True):
            indent(f, indent_level + 1)
            f.write(line)

def print_Return(f, stmt, indent_level):
    f.write(u"return")

    if stmt.expression is not None:
        f.write(u" %s" % (stmt.expression, ))

    f.write(u'\n')

def print_UserStatement(f, stmt, indent_level):
    f.write(u"%s\n" % (stmt.line, ))

def print_Init(f, stmt, indent_level):
    f.write(u"init")
    if stmt.priority != 0:
        f.write(u" %d" % (stmt.priority, ))
    f.write(u":\n")
    for s in stmt.block:
        print_statement(f, s, indent_level + 1)

def print_Image(f, stmt, indent_level):
    f.write(u"image %s" % (' '.join(stmt. imgname), ))
    if stmt.code is not None:
        f.write(u" = %s\n" % (stmt.code.source, ))
    else:
        f.write(u":\n")
        print_atl(f, stmt.atl, indent_level + 1)

def print_Transform(f, stmt, indent_level):
    f.write(u"transform %s" % (stmt.varname, ))

    if stmt.parameters is not None:
        print_params(f, stmt.parameters)

    f.write(":\n")
    print_atl(f, stmt.atl, indent_level + 1)

def print_Menu(f, stmt, indent_level):
    f.write(u"menu:\n")

    if stmt.with_ is not None:
        indent(f, indent_level + 1)
        f.write(u"with %s\n" % (stmt.with_, ))

    if stmt.set is not None:
        indent(f, indent_level + 1)
        f.write(u"set %s\n" % (stmt.with_, ))

    for item in stmt.items:
        indent(f, indent_level + 1)

        # caption
        f.write(u"\"%s\"" % (escape_string(item[0]), ))

        if item[2] is not None:
            # condition
            if item[1] != 'True':
                f.write(u" if %s" % (item[1], ))

            f.write(u':\n')

            for inner_stmt in item[2]:
                print_statement(f, inner_stmt, indent_level + 2)
        else:
            f.write(u'\n')

def print_Pass(f, stmt, indent_level):
    f.write(u"pass\n")

def print_Call(f, stmt, indent_level):
    f.write(u"call ")
    if stmt.expression:
        f.write(u"expression %s" % (stmt.label, ))
    else:
        f.write(stmt.label)

    if stmt.arguments is not None:
        if stmt.expression:
            f.write(u"pass ")
        print_args(f, stmt.arguments)

    f.write(u'\n')

def print_If(f, stmt, indent_level):
    f.write(u"if %s:\n" % (stmt.entries[0][0], ))
    for inner_stmt in stmt.entries[0][1]:
        print_statement(f, inner_stmt, indent_level + 1)

    if len(stmt.entries) >= 2:
        if stmt.entries[-1][0].strip() == 'True':
            else_entry = stmt.entries[-1]
            elif_entries = stmt.entries[:-1]
        else:
            else_entry = None
            elif_entries = stmt.entries

        for case in elif_entries:
            indent(f, indent_level)
            f.write(u"elif %s:\n" % (case[0], ))
            for inner_stmt in case[1]:
                print_statement(f, inner_stmt, indent_level + 1)

        if else_entry is not None:
            indent(f, indent_level)
            f.write(u"else:\n")
            for inner_stmt in else_entry[1]:
                print_statement(f, inner_stmt, indent_level + 1)

def print_EarlyPython(f, stmt, indent_level):
    print_Python(f, stmt, indent_level, early=True)

# TODO extrapos, extrakw?
def print_args(f, arginfo):
    if arginfo is None:
        return

    f.write(u"(")

    first = True
    for (name, val) in arginfo.arguments:
        if first:
            first = False
        else:
            f.write(u", ")

        if name is not None:
            f.write(u"%s = " % (name, ))
        f.write(val)

    f.write(u")")

# TODO positional?
def print_params(f, paraminfo):
    f.write(u"(")

    first = True
    for param in paraminfo.parameters:
        if first:
            first = False
        else:
            f.write(u", ")

        f.write(param[0])

        if param[1] is not None:
            f.write(u" = %s" % param[1])
    if paraminfo.extrapos:
        f.write(u", ")
        f.write(u"*%s" % paraminfo.extrapos)
    if paraminfo.extrakw:
        f.write(u", ")
        f.write(u"**%s" % paraminfo.extrakw)

    f.write(u")")

# Print while command, from http://forum.cheatengine.org/viewtopic.php?p=5377683
def print_While(f, stmt, indent_level): 
    f.write(u"while %s:\n" % (stmt.condition, )) 
    for inner_stmt in stmt.block: 
        print_statement(f, inner_stmt, indent_level + 1)

# Print define command, by iAmGhost
def print_Define(f, stmt, indent_level): 
    f.write(u"define %s = %s\n" % (stmt.varname, stmt.code.source,))
    
# Print Screen code (or at least code which does exactly the same. can't be picky, don't have source)  
def print_screen(f, stmt, indent_level):
    screen = stmt.screen
    sourcecode = codegen.to_source(screen.code.source, u" "*4)
    #why suddenly ast in the source code field
    f.write(u"screen %s" % screen.name)
    if screen.parameters:
        print_params(f, screen.parameters)
    f.write(u":\n")
    if screen.tag:
        indent(f, indent_level+1)
        f.write(u"tag %s\n" % screen.tag)
    if screen.zorder:
        indent(f, indent_level+1)
        f.write(u"zorder %s\n" % screen.zorder)
    if screen.modal:
        indent(f, indent_level+1)
        f.write(u"modal %s\n" % screen.modal)
    if screen.variant != "None":
        indent(f, indent_level+1)
        f.write(u"variant %s\n" % screen.variant)
    screendecompiler.print_screen(f, sourcecode, indent_level+1)
    f.write(u"\n")
    
statement_printer_dict = {
        ast.Label: print_Label,
        ast.Say: print_Say,
        ast.Jump: print_Jump,
        ast.Scene: print_Scene,
        ast.With: print_With,
        ast.Show: print_Show,
        ast.Hide: print_Hide,
        ast.Python: print_Python,
        ast.Return: print_Return,
        ast.UserStatement: print_UserStatement,
        ast.Init: print_Init,
        ast.Image: print_Image,
        ast.Transform: print_Transform,
        ast.Menu: print_Menu,
        ast.Pass: print_Pass,
        ast.Call: print_Call,
        ast.If: print_If,
        ast.While: print_While,
        ast.Define: print_Define,
        ast.EarlyPython: print_EarlyPython,
        ast.Screen: print_screen
    }

def print_Unknown(f, stmt, indent_level):
    print "Unknown AST node: %s" % (type(stmt).__name__, )
    f.write(u"<<<UNKNOWN NODE %s>>>\n" % (type(stmt).__name__, ))
