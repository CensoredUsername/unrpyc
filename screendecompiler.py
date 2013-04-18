import re

FORCE_MULTILINE_KWARGS = True

def indent(f, level):
    # Print indentation
    f.write(u'    ' * level)
    
def print_screen(f, code, indent_level=0):
    # This function should be called from the outside. It does some general cleanup in advance.
    lines = []
    for line in code.splitlines():
        if not 'ui.close()' in line:
            lines.append(line)
    print_block(f, '\n'.join(lines), indent_level)

def print_block(f, code, indent_level=0):
    # Print a block of statements, splitting it up on one level.
    # The screen language parser emits lines in the shape _0 = (_0, 0) from which indentation can be revealed.
    # It translates roughly to "id = (parent_id, index_in_parent_children)". When parsing a block
    # parse the first header line to find the parent_id, and then split around headers with the same parent id
    # in this block.
    header = code.split('\n',1)
    if len(header) == 1:
        return
    me, parent, no = parse_header(header[0])
    split = re.split(r'( *_[0-9]+ = \(_%s, _?[0-9]+\) *\n?)' % parent, code)[1:]
    for i in range(0, len(split), 2):
        print_statement(f, split[i], split[i+1], indent_level)

def print_statement(f, header='', code='', indent_level=0):
    # Here we derermine how to handle a statement.
    # To do this we look at how the first line in the statement code starts, after the header.
    # Then we call the appropriate function as specified in ui_function_dict.
    # If the statement is unknown, we can still emit valid screen code by just stuffing it inside a python block.
    indent(f, indent_level)
    # The for statement has an extra header. we just swallow it here in case it appears.
    # Otherwise the parser is clueless.
    if re.match(r' *_[0-9]+ = 0', code.split('\n',1)[0]):
        code = code.split('\n',1)[1]
    for statement in ui_function_dict:
        if code.lstrip().startswith(statement):
            function = ui_function_dict[statement]
            break
    else:
        function = print_python
    function(f, header, code, indent_level)
    
def parse_header(header):
    # This function reads the appropriate id/parent/index strings. Note that lowest-level blocks have "_name" as parent
    # instead of a number. after this numbering starts at _1, indexes start at _0
    match = re.search(r' *_([0-9]+) = \(_([0-9]+|name), _?([0-9]+)\) *\n?', header)
    if match:
        return (match.group(1), match.group(2), match.group(3))
    
def splitargs(string):
    # This function is a quick&dirty way of separating comma separated values of python syntax cleanly.
    # It will only split on comma's not enclosed by [], (), {}, "" and ''.     
    string = re.search('^.*?\\((.*)\\)', string).group(1)
    inside = [None]
    splits = []
    split = ''
    for character in string:
        if character in ['"',"'"]:
            if inside[-1] not in ['"',"'"]:
                inside.append(character)
            elif character != inside[-1]:
                pass
            elif check_uneven_slashes(split):
                pass
            else:
                inside.pop()
        elif inside[-1] not in ['"',"'"]:
            if character == '[':
                inside.append('[')
            elif character == ']':
                inside.pop()
            elif character == '(':
                inside.append('(')
            elif character == ')':
                inside.pop()
            elif character == '{':
                inside.append('{')
            elif character == '}':
                inside.pop()
        if inside == [None] and character == ',':
            splits.append(split.strip())
            split = ''
        else:
            split+=character
    splits.append(split.strip())
    return splits
                
def check_uneven_slashes(string):
    # This function looks if there's an uneven amount of backslashes at the end of a string.
    # This is done to prevent escaped quotes from ending a string in the comma separation parsing.
    if not string.endswith('\\'):
        return False
    elif len(re.search('(\\+)$',string).group(1)) % 2 == 1:
        return True
    else:
        return False
    
def parse_arguments(functionstring, extra=False):
    # This function parses a functionstring, splits it on comma's using splitargs, and then 
    # orders them by args, kwargs, *args and **kwargs. TODO support multiple *args and **kwargs
    arguments = splitargs(functionstring)
    args = []
    kwargs = {}
    exkwargs = None
    exargs = None
    for argument in arguments:
        argument = argument.strip()
        if re.search('[a-zA-Z_0-9]+ *=[^=]', argument):
            name, value = argument.split('=',1)
            kwargs[name.strip()] = value.strip()
        elif re.search('\*\*', argument):
            exkwargs = argument[2:]
        elif re.search('\*', argument):
            exargs = argument[1:]
        else:
            args.append(argument)
    if not extra:
        return args, kwargs
        if exkwargs or exargs: 
            print('ignored *args/**kwargs')
    else:
        return args, kwargs, exargs, exkwargs
    
def print_arguments(f, functionstring, indent_level, multiline=True):
    # This function parses a functionstring and prints the args/kwargs as they're
    # printed in screenlanguage. It ignores id if set to an auto-generated id and ignores _scope.
    # If multiline is set to true. print the syntax as if it's a block. 
    # If multiline is set to false, print the syntax as a statement not taking children.
    args, kwargs = parse_arguments(functionstring)
    if args: 
        f.write(u' ')
        f.write(u' '.join(['(%s)' % i if ' ' in i else i for i in args]) )
    if 'id' in kwargs and kwargs['id'].startswith('_'):
        del kwargs['id']
    if 'scope' in kwargs and kwargs['scope'] == '_scope':
        del kwargs['scope']
    for key in kwargs:
        if ' ' in kwargs[key]:
            kwargs[key] = '(%s)' % kwargs[key]
    if multiline or FORCE_MULTILINE_KWARGS:
        f.write(u':\n')
        for arg in kwargs:
            indent(f, indent_level+1)
            f.write(u'%s %s\n' % (arg, kwargs[arg]))
    else:
        for arg in kwargs:
            f.write(u' %s %s' % (arg, kwargs[arg]))
        f.write(u'\n')
        
def print_condition(f, string, statement, indent_level):
    # This handles parsing of for and if statement conditionals.
    # It also strips the brackets the parser adds around for statement assignments
    # to prevent ren'py from getting a heart attack.
    condition = string.split(':',1)[0].rsplit(statement,1)[1].strip()
    if statement == 'for' and '(' in condition:
        tuples, value = condition.split('in')
        if tuples.strip().startswith('(') and tuples.strip().endswith(')'):
            tuples = tuples.strip()[1:-1]
        condition = '%s in%s' % (tuples, value)
    f.write(u'%s %s:\n' % (statement, condition))
    
def print_python(f, header, code, indent_level):
    # This function handles any statement which is a block but couldn't logically be
    # Translated to a screen statement. If it only contains one line it will not make a block, just use $.
    # Note that because of ui.close() stripping at the start this might not necessarily 
    # Still be valid code if we couldn't parse a screen statement containing children.
    # Because some python syntax is valid screen statement syntax (if, for, function assignments) 
    # Python code might be mistaken for screen statements. It is expected that the statements handle
    # This themselves.
    if len(code.strip().splitlines()) > 1:
        f.write(u'python:\n')
        indent(f, indent_level+1)
        split = code.split('\n',1)
        f.write(split[0].strip()+u'\n')
        if len(split) == 2: 
            code_indent = len(split[0])-len(split[0].lstrip())
            for line in split[1].splitlines():
                indent(f, indent_level+1)
                f.write(line[code_indent:]+u'\n')
    else:
        f.write(u'$ %s\n' % code.strip())
    
def print_if(f, header, code, indent_level):
    # Here we handle the if statement. It might be valid python but we can check for this by
    # checking for the header that should normally occur within the if statement.
    # The if statement parser might also generate a second header if there's more than one screen
    # statement enclosed in the if/elif/else statements. We'll take care of that too.

    # note that it is possible for a python block to have "if" as it's first statement
    # so we check here if a second header appears after the if block to correct this.
    lines = code.splitlines()
    if not parse_header(lines[1]):
        # accidentally a python block
        print_python(f, header, code, indent_level)
        return
    #check for elif/else statements
    if_indent = len(lines[0])-len(lines[0].lstrip())
    blockcode = []
    for i, line in enumerate(lines):
        if i==0:
            print_condition(f, line, 'if', indent_level)
        elif line[if_indent:].startswith('elif') or line[if_indent:].startswith('else') or i == len(lines)-1:
            if i == len(lines)-1:
                blockcode.append(line)
            if len(blockcode)>2 and parse_header(blockcode[0]) and parse_header(blockcode[1]):
                print_block(f, u'\n'.join(blockcode[1:]), indent_level+1)
            elif len(blockcode)>1 and parse_header(blockcode[0]):
                print_block(f, u'\n'.join(blockcode), indent_level+1)
            else:
                indent(f, indent_level+1)
                f.write(u'pass\n')
            if line[if_indent:].startswith('elif'):
                print_condition(f, line, 'elif', indent_level)
            elif line[if_indent:].startswith('else'):
                indent(f, indent_level)
                f.write(u'else:\n')
            blockcode = []
        else:
            blockcode.append(line)

def print_for(f, header, code, indent_level):
    # Here we handle the for statement. Note that the for statement generates some extra python code to 
    # Keep track of it's header indices. The first one is ignored by the statement parser, 
    # the second line is just ingored here. 

    # note that it is possible for a python block to have "for" as it's first statement
    # so we check here if a second header appears after the for block to correct this.
    lines = code.splitlines()
    if not parse_header(lines[1]): 
        # accidentally a python block
        print_python(f, header, code, indent_level)
        return
    print_condition(f, lines[0], 'for', indent_level)
    if len(lines) > 3 and parse_header(lines[1]) and parse_header(lines[2]):
        print_block(f, u'\n'.join(lines[2:-1]), indent_level+1)
    elif len(lines) > 2 and parse_header(lines[1]):
        print_block(f, u'\n'.join(lines[1:-1]), indent_level+1)
    else:
        indent(f, indent_level+1)
        f.write(u'pass\n')  

def print_use(f, header, code, indent_level):
    # This function handles the use statement, which translates into a python expression "renpy.use_screen".
    # It would technically be possible for this to be a python statement, but the odds of this are very small.
    # renpy itself will insert some kwargs, we'll delete those and then parse the command here.
    args, kwargs, exargs, exkwargs = parse_arguments(code.strip(), True)
    del kwargs['_scope']
    del kwargs['_name']
    f.write(u'use %s' % args[0][2:-1])
    args = args[1:]
    arglist = []
    if args or kwargs or exargs or exkwargs:
        f.write(u'(')
        for arg in args:
            arglist.append(arg)
        for arg in kwargs:
            arglist.append('%s=%s' %(arg, kwargs[arg]))
        if exargs:
            arglist.append('*%s' % exargs)
        if exkwargs:
            arglist.append('**%s' % exkwargs)
        f.write(u', '.join(arglist))
        f.write(u')')
    f.write(u'\n')      
    
def print_default(f, header, code, indent_level):
    args, kwargs = parse_arguments(code.strip())
    var = args[0].split("'",1)[1].rsplit("'",1)[0]
    val = args[1]
    f.write(u'default %s = %s\n' % (var, val))
    
def print_hotspot(f, header, code, indent_level):
    # Because hotspot's ui function doesn't match, here's a bit of code for it.
    line = code.split('\n',1)[0]
    f.write(u'hotspot')
    print_arguments(f, line, indent_level, False)
    
def print_oneline(f, header, code, indent_level):
    # This is the translation of any simple statement not taking children.
    # The name equates to the part between "ui.|statement name|()"
    # Then print the arguments.
    line = code.split('\n',1)[0]
    type = line.split('ui.',1)[1].split('(',1)[0]
    f.write(type)
    print_arguments(f, line, indent_level, False)
    
def print_multiline_onechild(f, header, code, indent_level):
    # This is the translation of any simple statement taking one child.
    # Technically it translates to "statement\nui.child_or_fixed()"
    # This is however not very interesting. test if it's there, and ignore it if it is
    # The name equates to the part between "ui.|statement name|()"
    # Then print the arguments.
    line = code.split('\n',1)[0]
    type = line.split('ui.',1)[1].split('(',1)[0]
    f.write(type)
    print_arguments(f, code.split('\n',1)[0], indent_level)
    if 'ui.child_or_fixed()' in code.splitlines()[1]:
        print_block(f, '\n'.join(code.splitlines()[2:]), indent_level+1)
    else:
        print_block(f, '\n'.join(code.splitlines()[1:]), indent_level+1)
    
def print_multiline_manychildren(f, header, code, indent_level):
    # This is the translation of any statement taking multiple children.
    # It translates the same as a oneline, except it'll be followed by
    # a block of children.
    line = code.split('\n',1)[0]
    type = line.split('ui.',1)[1].split('(',1)[0]
    f.write(type)
    print_arguments(f, code.split('\n',1)[0], indent_level)
    print_block(f, '\n'.join(code.splitlines()[1:]), indent_level+1)



ui_function_dict = { 
# a dictionary of the code with which the translated statement starts, and which function to use to parse the block
# commented statemens are statemens I haven't looked at yet.
'ui.add': print_oneline,
'ui.button': print_multiline_onechild,
'ui.fixed': print_multiline_manychildren,
'ui.frame': print_multiline_onechild,
'ui.grid': print_multiline_manychildren,
'ui.hbox': print_multiline_manychildren,
'ui.imagebutton': print_oneline,
'ui.input': print_oneline,
'ui.key': print_oneline,
'ui.label': print_oneline,
'ui.text': print_oneline,
'ui.null': print_oneline,
'ui.mousearea': print_oneline,
'ui.side': print_multiline_manychildren,
'ui.textbutton': print_oneline,
'ui.timer': print_oneline,
'ui.transform': print_multiline_onechild,
'ui.bar': print_oneline,
'ui.vbar': print_oneline,
'ui.vbox': print_multiline_manychildren,
'ui.viewport': print_multiline_onechild,
'ui.window': print_multiline_onechild,
'ui.imagemap': print_multiline_manychildren,
'ui.hotspot_with_child': print_hotspot,
'ui.hotbar': print_oneline,
'ui.drag': print_multiline_onechild,
'ui.draggroup': print_multiline_manychildren,
'if': print_if,
'for': print_for,
'_scope.setdefault': print_default,
'renpy.use_screen': print_use,
}

# TODO 
# test
