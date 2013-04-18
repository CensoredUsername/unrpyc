import re

def indent(f, level):
    # Print indentation
    f.write(u'    ' * level)
    
def print_screen(f, code, indent_level=0):
    lines = []
    for line in code.splitlines():
        if not 'ui.close()' in line:
            lines.append(line)
    print_block(f, '\n'.join(lines), indent_level)

def print_block(f, code, indent_level=0):
    #print a block of statements, splitting it up on one level.
    header = code.split('\n',1)
    if len(header) == 1:
        return
    me, parent, no = parse_header(header[0])
    split = re.split(r'( *_[0-9]+ = \(_%s, _?[0-9]+\) *\n?)' % parent, code)[1:]
    for i in range(0, len(split), 2):
        print_statement(f, split[i], split[i+1], indent_level)

def print_statement(f, header='', code='', indent_level=0):
    #determine what function to call for this code block
    indent(f, indent_level)
    #for has an extra header. we just swallow it here in case it appears:
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
    match = re.search(r' *_([0-9]+) = \(_([0-9]+|name), _?([0-9]+)\) *\n?', header)
    if match:
        return (match.group(1), match.group(2), match.group(3))
    
def splitargs(string):
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
            elif check_uneven_slashes(split): #asdf
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
        if not string.endswith('\\'):
            return False
        elif len(re.search('(\\+)$',string).group(1)) % 2 == 1:
            return True
        else:
            return False
    
def parse_arguments(functionstring, extra=False):
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
    if multiline:
        f.write(u':\n')
        for arg in kwargs:
            indent(f, indent_level+1)
            f.write(u'%s %s\n' % (arg, kwargs[arg]))
    else:
        for arg in kwargs:
            f.write(u' %s %s' % (arg, kwargs[arg]))
        f.write(u'\n')
        
def print_condition(f, string, statement, indent_level):
    condition = string.split(':',1)[0].rsplit(statement,1)[1].strip()
    if statement == 'for' and '(' in condition:
        tuples, value = condition.split('in')
        if tuples.strip().startswith('(') and tuples.strip().endswith(')'):
            tuples = tuples.strip()[1:-1]
        condition = '%s in%s' % (tuples, value)
    f.write(u'%s %s:\n' % (statement, condition))
    
def print_python(f, header, code, indent_level):
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
    
def print_oneline(f, header, code, indent_level):
    line = code.split('\n',1)[0]
    type = line.split('ui.',1)[1].split('(',1)[0]
    f.write(type)
    print_arguments(f, line, indent_level, False)
    
def print_multiline_onechild(f, header, code, indent_level):
    line = code.split('\n',1)[0]
    type = line.split('ui.',1)[1].split('(',1)[0]
    f.write(type)
    print_arguments(f, code.split('\n',1)[0], indent_level)
    print_block(f, '\n'.join(code.splitlines()[2:]), indent_level+1)
    
def print_multiline_manychildren(f, header, code, indent_level):
    line = code.split('\n',1)[0]
    type = line.split('ui.',1)[1].split('(',1)[0]
    f.write(type)
    print_arguments(f, code.split('\n',1)[0], indent_level)
    print_block(f, '\n'.join(code.splitlines()[1:]), indent_level+1)



ui_function_dict = {
'ui.add': print_oneline,
'ui.button': print_multiline_onechild,
'ui.fixed': print_multiline_manychildren,
'ui.frame': print_multiline_onechild,
# 'ui.grid': print_grid,
'ui.hbox': print_multiline_manychildren,
'ui.imagebutton': print_oneline,
# 'ui.input': print_input,
# 'ui.key': print_key,
# 'ui.label': print_label,
'ui.text': print_oneline,
# 'ui.null': print_null,
# 'ui.mousearea': print_mousearea,
# 'ui.side': print_side,
# 'ui.text': print_text,
# 'ui.textbutton': print_textbutton,
# 'ui.timer': print_timer,
# 'ui.transform': print_transform,
'ui.bar': print_oneline,
'ui.vbar': print_oneline,
'ui.vbox': print_multiline_manychildren,
# 'ui.viewport': print_viewport,
'ui.window': print_multiline_onechild,
# 'ui.imagemap': print_imagemap,
# 'ui.hotspot_with_child': print_hotspot,
# 'ui.hotbar': print_hotbar,
# 'ui.drag': print_drag,
# 'ui.draggroup': print_draggroup,
'if': print_if,
'for': print_for,
# '_scope.setdefault': print_default,
'renpy.use_screen': print_use,
}

#TODO 
#strip _id attrs when prefixed with a _
#scope = _scope attrs
#actually parse call args correctly. current way's a hack which easily fails

