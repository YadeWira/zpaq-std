#!/usr/bin/env python3
"""zref.py: the Python model of the ZPAQL decoder. It RUNS lz6seq_src.py, the same source gen.py
compiles to lz6seq.cfg, so the model and the ZPAQL have the same buffers (M, H), the same registers and
the same control flow by construction.

    python3 zref.py [-d] [-k] container [output]      decode a container; exit status 1 if a chunk failed
    python3 zref.py [-d] [-k] -b block.seq [output]   wrap one seq block in a container first

  -d   DEBUG: dbg(x) values (4 bytes each) go to the output, as in the cfg made by `gen.py -d`
  -k   CHECK: every + - * << of the source is verified to stay inside 0 .. 2^32 - 1 (unless it is under
       an `& constant`, which marks an intended wrap), every shift count to be below 32 and every index
       of M and H to be inside the array: what would behave differently in ZPAQL's 32-bit registers.

As a module:  m = Model(debug=False, check=False);  out = m.run(container_bytes);  m.failed, m.env
"""
import ast, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MASK32 = 0xFFFFFFFF


class Fail(Exception):
    pass


class CheckError(Exception):
    pass


class _Check(ast.NodeTransformer):
    """BinOp -> _bo('Op', l, r, wrap_ok); Subscript loads / stores of M and H -> index checked."""
    NAMES = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.LShift: 'shl', ast.RShift: 'shr',
             ast.FloorDiv: 'div', ast.Mod: 'mod', ast.BitAnd: 'and', ast.BitOr: 'or', ast.BitXor: 'xor'}

    def visit_BinOp(self, n, wrap=False):
        inner_wrap = isinstance(n.op, ast.BitAnd) and isinstance(n.right, (ast.Constant, ast.Name)) and \
            (isinstance(n.right, ast.Constant) or n.right.id == 'MASK32')
        if isinstance(n.left, ast.BinOp):
            left = self.visit_BinOp(n.left, inner_wrap)
        else:
            left = self.visit(n.left)
        right = self.visit(n.right)
        return ast.copy_location(ast.Call(ast.Name('_bo', ast.Load()),
                                          [ast.Constant(self.NAMES[type(n.op)]), left, right, ast.Constant(wrap)],
                                          []), n)

    def visit_AugAssign(self, n):
        import copy
        tl = copy.deepcopy(n.target)
        tl.ctx = ast.Load()
        return self.visit(ast.copy_location(ast.Assign([n.target], ast.copy_location(ast.BinOp(tl, n.op, n.value), n)), n))

    def visit_Subscript(self, n):
        n.slice = ast.copy_location(ast.Call(ast.Name('_ix', ast.Load()), [self.visit(n.slice), ast.Constant(n.value.id)], []), n)
        return n


def _bo(op, a, b, wrap):
    if op == 'add':
        r = a + b
    elif op == 'sub':
        r = a - b
    elif op == 'mul':
        r = a * b
    elif op == 'shl':
        if b > 31:
            raise CheckError("shift count %d" % b)
        r = a << b
    elif op == 'shr':
        if b > 31:
            raise CheckError("shift count %d" % b)
        r = a >> b
    elif op == 'div':
        r = a // b
    elif op == 'mod':
        r = a % b
    elif op == 'and':
        r = a & b
    elif op == 'or':
        r = a | b
    else:
        r = a ^ b
    if (r < 0 or r > MASK32) and not wrap:
        raise CheckError("%s(%d, %d) leaves 32 bits" % (op, a, b))
    return r


class Model:
    def __init__(self, debug=False, check=False, src=None):
        src = src or os.path.join(HERE, "lz6seq_src.py")
        tree = ast.parse(open(src).read(), src)
        names = set()
        for f in tree.body:
            if isinstance(f, ast.FunctionDef):
                for node in ast.walk(f):
                    tg = []
                    if isinstance(node, ast.Assign):
                        tg = node.targets
                    elif isinstance(node, ast.AugAssign):
                        tg = [node.target]
                    names.update(t.id for t in tg if isinstance(t, ast.Name))
        for f in tree.body:
            if isinstance(f, ast.FunctionDef):
                params = {a.arg for a in f.args.args}
                g = sorted(names - params)
                if g:
                    f.body.insert(0, ast.Global(g))
        if check:
            for f in tree.body:
                if isinstance(f, ast.FunctionDef):
                    f.body = [_Check().visit(s) for s in f.body]
        ast.fix_missing_locations(tree)
        self.debug = debug
        self.outbuf = bytearray()
        self.failed = 0
        env = {'MASK32': MASK32, 'Fail': Fail, '_bo': _bo}
        self.env = env
        for n in names:
            env[n] = 0
        env['ferr'] = 0
        exec(compile(tree, src, 'exec'), env)
        M = env['M'] = bytearray(1 << env['PM'])
        env['H'] = [0] * (1 << env['PH'])
        msize = len(M)
        hsize = 1 << env['PH']
        outbuf = self.outbuf

        def _ix(i, arr):
            if i < 0 or i >= (msize if arr == 'M' else hsize):
                raise CheckError("index %d of %s" % (i, arr))
            return i

        def fail(n):
            env['ferr'] = n
            self.failed = n
            raise Fail(n)

        def out(x):
            outbuf.append(x & 255)

        def emit(p, n):
            outbuf.extend(M[p:p + n])

        def copy(dst, src, n):
            if src + n <= dst or dst + n <= src:
                M[dst:dst + n] = M[src:src + n]
            elif src < dst:
                d = dst - src                    # the pattern of d bytes repeats
                pat = bytes(M[src:dst])
                M[dst:dst + n] = (pat * (n // d + 1))[:n]
            else:
                for i in range(n):
                    M[dst + i] = M[src + i]

        def dbg(x):
            if debug:
                outbuf.extend((x & MASK32).to_bytes(4, 'little'))

        env.update(fail=fail, out=out, emit=emit, copy=copy, dbg=dbg, _ix=_ix)
        self.step = env['step']

    def run(self, data):
        """Feed a whole segment (the bytes, then the end mark) and return the output."""
        del self.outbuf[:]
        self.failed = 0
        step = self.step
        for b in data:
            step(b)
        step(MASK32)
        return bytes(self.outbuf)


def wrap(blocks):
    """Container of a list of seq blocks."""
    c = len(blocks).to_bytes(4, 'little')
    for b in blocks:
        c += len(b).to_bytes(4, 'little') + b
    return c


def main():
    args = sys.argv[1:]
    debug = check = block = False
    while args and args[0].startswith('-'):
        if args[0] == '-d':
            debug = True
        elif args[0] == '-k':
            check = True
        elif args[0] == '-b':
            block = True
        else:
            sys.exit(__doc__)
        args = args[1:]
    if not args:
        sys.exit(__doc__)
    data = open(args[0], 'rb').read()
    if block:
        data = wrap([data])
    m = Model(debug, check)
    out = m.run(data)
    if len(args) > 1:
        open(args[1], 'wb').write(out)
    else:
        sys.stdout.buffer.write(out)
    if m.failed:
        sys.stderr.write("chunk failed: fail(%d)\n" % m.failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
