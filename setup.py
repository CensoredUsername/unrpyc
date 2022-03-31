#!/usr/bin/env python2
from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()
setup(
    name='unrpyc',
    version='0.1',
    description='Tool to decompile Ren\'Py compiled .rpyc script files.',
    long_description=readme(),
    url='https://github.com/CensoredUsername/unrpyc',
    py_modules=['unrpyc', '.deobfuscate'],
    packages=['decompiler'],
    scripts=['unrpyc.py'],
    zip_safe=False,
)
