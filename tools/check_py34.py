#!/usr/bin/env python3
"""Reject Python syntax the device's Python 3.4 runtime cannot byte-compile.

Why this exists
---------------
mod-ui is developed on a modern Python but SHIPPED inside a MOD OS image whose
Buildroot toolchain provides Python 3.4.  A construct newer than 3.4 does not
fail loudly: the image build's byte-compile step fails for that module, the
cleanup step deletes the .py source anyway, and the device ships with the module
MISSING or stale.  The symptom then appears somewhere unrelated.

That happened once already (September 2026): three f-strings in session.py
took mod-ui down on the device, and the cause was first misdiagnosed as an
incremental-build problem.

This checker parses each file with the host interpreter's `ast` module and
rejects node types that do not exist in 3.4.  It needs no 3.4 interpreter,
which is what makes it runnable in CI.

Usage
-----
    python3 tools/check_py34.py                 # check everything that ships
    python3 tools/check_py34.py path/to/file.py # check specific files

Exit status is 1 if anything is rejected, 0 otherwise.
"""

import ast
import os
import subprocess
import sys

# node type -> (minimum Python version, what to write instead)
FORBIDDEN = {
    'JoinedStr':        ('3.6', 'f-string', 'use % formatting or .format()'),
    'AnnAssign':        ('3.6', 'variable annotation', 'use a plain assignment, or a comment'),
    'NamedExpr':        ('3.8', 'walrus operator :=', 'assign on a separate line'),
    'AsyncFunctionDef': ('3.5', 'async def', 'use tornado gen.coroutine'),
    'Await':            ('3.5', 'await', 'use tornado yield'),
    'AsyncFor':         ('3.5', 'async for', 'use tornado gen.coroutine'),
    'AsyncWith':        ('3.5', 'async with', 'use tornado gen.coroutine'),
    'MatMult':          ('3.5', 'matrix multiply @', 'not applicable here'),
    'Match':            ('3.10', 'match statement', 'use if/elif'),
}

# Directories and files that never reach the device.
EXCLUDE_PREFIXES = ('test/', '.github/', 'mod/old/')
EXCLUDE_FILES    = {
    'tools/check_py34.py',
    # Python 2 leftovers, broken since the 2015 migration and not shipped as
    # working tools. If any is ever revived, delete its line here FIRST.
    'hmi_debug.py',
    'host_debug.py',
    'bluetooth.py',
}


class Scanner(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.hits = []

    def generic_visit(self, node):
        name = type(node).__name__
        if name in FORBIDDEN:
            ver, what, fix = FORBIDDEN[name]
            self.hits.append((getattr(node, 'lineno', 0), ver, what, fix))
        # starred assignment targets: a, *b = ... is 3.0+, fine.
        super().generic_visit(node)


def shipped_files():
    out = subprocess.check_output(['git', 'ls-files', '*.py'], text=True)
    for f in out.splitlines():
        if f.startswith(EXCLUDE_PREFIXES) or f in EXCLUDE_FILES:
            continue
        yield f


def check(path):
    try:
        with open(path, 'rb') as fh:
            tree = ast.parse(fh.read(), filename=path)
    except SyntaxError as e:
        # Already unparseable by the HOST python -- worse than a 3.4 problem.
        return [(e.lineno or 0, '3.0', 'file does not parse at all', str(e))]
    s = Scanner(path)
    s.visit(tree)
    # One report per line: a single f-string can hold several nested nodes.
    seen, unique = set(), []
    for hit in s.hits:
        key = (hit[0], hit[2])
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


def main(argv):
    paths = argv[1:] or sorted(shipped_files())
    failures = 0
    for p in paths:
        for lineno, ver, what, fix in check(p):
            failures += 1
            print('%s:%d: %s requires Python %s; the device runs 3.4 -- %s'
                  % (p, lineno, what, ver, fix))
    if failures:
        print('')
        print('%d construct(s) the device cannot byte-compile.' % failures)
        print('A failure here is not cosmetic: the image build deletes the .py source')
        print('after a failed byte-compile, so the device ships without the module.')
        return 1
    print('checked %d shipped file(s): all parse under Python 3.4' % len(paths))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
