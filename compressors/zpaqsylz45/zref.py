#!/usr/bin/env python3
"""zref.py: the Python model of ZPAQSYLZ4 / ZPAQSYLZ5. It RUNS sylz_src.py, the same source gen.py
compiles to ZPAQL, so the model and the ZPAQL have the same arrays (M, H), the same registers and the
same control flow by construction.

    python3 zref.py [-d] [-k] [-p PM] 4|5 segment [output]     exit status 1 if the block was rejected

  -d   DEBUG: dbg(x) values (4 bytes each) go to the output, as in the cfg made by `gen.py -d`
  -k   CHECK: every + - * << of the source is verified to stay inside 0 .. 2^32 - 1 (unless it is under
       an `& constant`, which marks an intended wrap), every shift count to be below 32, every index of H
       to be inside it, and every copy to stay inside M without wrapping: what would behave differently
       in ZPAQL's 32-bit registers.
  -p   PM (default: the smallest that holds the segment, as zpaq-std chooses it)

As a module:  m = Model(variant, pm, debug=False, check=False);  out = m.run(segment);  m.failed, m.env
A Model keeps M, H and every register from one run to the next, as zpaq does between the segments of a
block; m.poison(seed) fills them with random values.
"""
import ast, os, sys, random
import tables

HERE = os.path.dirname(os.path.abspath(__file__))
MASK32 = 0xFFFFFFFF


class Fail(Exception):
    pass


class CheckError(Exception):
    pass


def pm_for(variant, seglen):
    """zpaqsylz4_pm / zpaqsylz5_pm: the segment and the window (and, variant 5, the literal buffer)."""
    need = seglen + (131072 if variant == 5 else 65536)
    pm = 17
    while pm < 31 and (1 << pm) < need:
        pm += 1
    return pm


def ph_for(variant):
    return 12 if variant == 5 else 8


class _Ld16(ast.NodeTransformer):
    """ld16(x, p)  ->  x = M[p] | (M[p + 1] << 8)"""

    def visit_Expr(self, n):
        c = n.value
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == 'ld16':
            x, p = c.args
            m = lambda idx: ast.Subscript(ast.Name('M', ast.Load()), idx, ast.Load())
            val = ast.BinOp(m(ast.Name(p.id, ast.Load())), ast.BitOr(),
                            ast.BinOp(m(ast.BinOp(ast.Name(p.id, ast.Load()), ast.Add(), ast.Constant(1))),
                                      ast.LShift(), ast.Constant(8)))
            return ast.copy_location(ast.Assign([ast.Name(x.id, ast.Store())], val), n)
        return n


class _Mem(ast.NodeTransformer):
    """M[e] -> M[e & _MM]; a store to M keeps the low 8 bits."""

    def visit_Subscript(self, n):
        self.generic_visit(n)
        if isinstance(n.value, ast.Name) and n.value.id == 'M':
            n.slice = ast.BinOp(n.slice, ast.BitAnd(), ast.Name('_MM', ast.Load()))
        return n

    def visit_Assign(self, n):
        self.generic_visit(n)
        t = n.targets[0]
        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == 'M':
            n.value = ast.BinOp(n.value, ast.BitAnd(), ast.Constant(255))
        return n


class _Check(ast.NodeTransformer):
    """BinOp -> _bo('op', l, r, wrap_ok); the index of an H subscript -> checked."""
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
    def __init__(self, variant, pm=24, debug=False, check=False, ph=None, src=None):
        src = src or os.path.join(HERE, "sylz_src.py")
        ph = ph or ph_for(variant)
        tree = ast.parse(open(src).read(), src)
        names = set()
        for f in tree.body:
            if isinstance(f, ast.FunctionDef):
                f.body = [_Ld16().visit(s) for s in f.body]
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
        for f in tree.body:
            if isinstance(f, ast.FunctionDef):
                if check:
                    f.body = [_Check().visit(s) for s in f.body]
                f.body = [_Mem().visit(s) for s in f.body]
        ast.fix_missing_locations(tree)
        self.variant = variant
        self.pm = pm
        self.debug = debug
        self.outbuf = bytearray()
        self.failed = 0
        self.names = sorted(names | {'n'})
        msize = 1 << pm
        hsize = 1 << ph
        env = {'MASK32': MASK32, 'Fail': Fail, '_bo': _bo, 'V5': 1 if variant == 5 else 0, 'DEBUG': 1 if debug else 0, '_MM': msize - 1}
        self.env = env
        for nm in self.names:
            env[nm] = 0
        env['ferr'] = 0
        exec(compile(tree, src, 'exec'), env)
        M = env['M'] = bytearray(msize)
        H = env['H'] = [0] * hsize
        outbuf = self.outbuf
        mm = msize - 1

        def _ix(i, arr):
            if arr == 'H' and (i < 0 or i >= hsize):
                raise CheckError("index %d of H" % i)
            return i

        def fail(k):
            env['ferr'] = k
            self.failed = k
            raise Fail(k)

        def out(x):
            outbuf.append(x & 255)

        def copyout(dst, src, k):
            dst &= mm
            src &= mm
            if k < 1 or dst + k > msize or src + k > msize:
                raise CheckError("copyout(%d, %d, %d)" % (dst, src, k))
            if src + k <= dst or dst + k <= src:
                M[dst:dst + k] = M[src:src + k]
            elif src < dst:
                d = dst - src                    # the pattern of d bytes repeats
                pat = bytes(M[src:dst])
                M[dst:dst + k] = (pat * (k // d + 1))[:k]
            elif src > dst:
                for i in range(k):
                    M[dst + i] = M[src + i]
            outbuf.extend(M[dst:dst + k])

        def loadtable(k):
            H[0:256] = tables.TABLE[k]

        def dbg(x):
            if debug:
                outbuf.extend((x & MASK32).to_bytes(4, 'little'))

        env.update(fail=fail, out=out, copyout=copyout, loadtable=loadtable, dbg=dbg, _ix=_ix)
        self.decode = env['decode']

    def poison(self, seed):
        """Random values in M, H and every register, as if another segment had left them."""
        rnd = random.Random(seed)
        M = self.env['M']
        M[:] = rnd.randbytes(len(M))
        H = self.env['H']
        H[:] = [rnd.getrandbits(32) for _ in H]
        for nm in self.names:
            self.env[nm] = rnd.getrandbits(32)

    def run(self, seg):
        """A whole segment into M, then decode(): returns the output."""
        del self.outbuf[:]
        self.failed = 0
        M = self.env['M']
        if len(seg) <= len(M):
            M[:len(seg)] = seg
        else:
            for i, b in enumerate(seg):
                M[i & (len(M) - 1)] = b
        self.env['n'] = len(seg) & MASK32
        self.decode()
        return bytes(self.outbuf)


def main():
    args = sys.argv[1:]
    debug = check = False
    pm = None
    while args and args[0].startswith('-'):
        if args[0] == '-d':
            debug = True
        elif args[0] == '-k':
            check = True
        elif args[0] == '-p':
            pm = int(args[1])
            args = args[1:]
        else:
            sys.exit(__doc__)
        args = args[1:]
    if len(args) < 2 or args[0] not in ('4', '5'):
        sys.exit(__doc__)
    variant = int(args[0])
    data = open(args[1], 'rb').read()
    m = Model(variant, pm or pm_for(variant, len(data)), debug, check)
    out = m.run(data)
    if len(args) > 2:
        open(args[2], 'wb').write(out)
    else:
        sys.stdout.buffer.write(out)
    if m.failed:
        sys.stderr.write("rejected: fail(%d)\n" % m.failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
