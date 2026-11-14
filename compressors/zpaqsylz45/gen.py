#!/usr/bin/env python3
"""gen.py: generates ZPAQSYLZ4 and ZPAQSYLZ5, the ZPAQL post-processors that decode syc's sylz blocks
(ZPAQSYLZ4: formats v2 and v4, what the plugin codec sylz4 writes; ZPAQSYLZ5: v2, v3, v4 and v5, what sylz5
writes). Both come from sylz_src.py, compiled with the constant V5 = 0 or 1.

    gen.py 4|5 PH PM          the whole config (comp 0 0 PH PM 0 + the body), to stdout
    gen.py 4|5                the same with the smallest PH and PM = 24
    gen.py 4|5 body           the body alone (what zpaq-std appends to its own comp line)
    gen.py 4|5 header         zpaqsylz4_body.h / zpaqsylz5_body.h, to stdout
    gen.py -d 4|5 ...         DEBUG variant: dbg(x) writes x as 4 bytes to the output and fail(n) keeps n
                              in register `ferr`; zref.py -d does the same

sylz_src.py is written in a small subset of Python and is also what the model (zref.py) runs:

  module level   NAME = constant expression      compile-time constants (UPPER CASE); V5 is given by gen.py
                 def f(params): ...              macros: a call `f(x, 3)` is expanded in line, the
                                                 parameters replaced BY NAME (arguments: names or constants)
  variables      every other name is one global 32-bit register R[n]. NOTHING is assumed about their
                 values when a segment starts (a zpaq block may hold several segments)
  memory         M[e] (bytes; the index is taken modulo the size of M, a store keeps the low 8 bits),
                 H[e] (32-bit words)
  expressions    + - * // % & | ^ << >> on unsigned 32-bit values; `(e) & MASK32` marks an intended wrap
  conditions     == != < > <= >= (unsigned), and / or / not, a bare expression (non-zero); a condition
                 that is a constant keeps only the branch taken (how V5 and DEBUG select code)
  statements     assignment, augmented assignment, if / elif / else, while, break, continue, return,
                 try: ... except Fail: ...,  fail(n) (jumps to the handler of the enclosing try),
                 out(e), copyout(dst, src, n) (n >= 1 bytes of M from src to dst, forward, one by one, each
                 also written to the output), ld16(x, p) (x = the 16-bit little-endian value at M[p]),
                 loadtable(2 | 4) (H[0..255] = tables.TABLE[...]), dbg(e), pass
  entry          def decode(): runs when the segment ends, with n = the number of bytes it had (they are
                 in M[0..n))

ZPAQL registers: A accumulator, B second operand, C pointer into M, D pointer into H. Nothing is kept in
A-D between statements (except inside copyout / loadtable), so every statement starts from the R registers.
The emitter remembers which R register each of A-D is known to hold and drops loads it does not need.
Jumps are written as explicit jt / jf / jmp (short) or lj (absolute), sized by relaxation.
(The compiler is the one of lz6seq's decoder, with the constant conditions and the three builtins added.)
"""
import ast, sys, copy, os
import tables


MASK32 = 0xFFFFFFFF
BINOPS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.FloorDiv: '/', ast.Mod: '%', ast.BitAnd: '&',
          ast.BitOr: '|', ast.BitXor: '^', ast.LShift: '<<', ast.RShift: '>>'}
COMMUT = (ast.Add, ast.Mult, ast.BitAnd, ast.BitOr, ast.BitXor)
PYOP = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b, ast.BitAnd: lambda a, b: a & b,
        ast.BitOr: lambda a, b: a | b, ast.BitXor: lambda a, b: a ^ b, ast.LShift: lambda a, b: a << b,
        ast.RShift: lambda a, b: a >> b}


class CompileError(Exception):
    pass


def load_source(path):
    """Parse the source: returns (constants dict, functions dict name -> FunctionDef, tree)."""
    tree = ast.parse(open(path).read(), path)
    consts = {'MASK32': MASK32}
    funcs = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            assert len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            consts[node.targets[0].id] = eval(compile(ast.Expression(node.value), path, 'eval'), dict(consts))
        elif isinstance(node, ast.FunctionDef):
            funcs[node.name] = node
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            pass                         # docstring
        else:
            raise CompileError("line %d: only constants and functions at module level" % node.lineno)
    return consts, funcs, tree


class Subst(ast.NodeTransformer):
    def __init__(self, m):
        self.m = m

    def visit_Name(self, n):
        if n.id in self.m:
            return copy.deepcopy(self.m[n.id])
        return n


class Gen:
    def __init__(self, consts, funcs, debug):
        self.consts = consts
        self.funcs = funcs
        self.debug = debug
        self.items = []                  # ('op', text, size) | ('label', name) | ('j', kind, label)
        self.regs = {}
        self.eq = {'a': set(), 'b': set(), 'c': set(), 'd': set()}
        self.nlabel = 0
        self.loops = []                  # (break label, continue label)
        self.fails = []                  # fail labels
        self.rets = []                   # return labels
        self.inl = []                    # functions being expanded
        self.ntemp = 0
        self.dead = False                # code after an unconditional jump, before the next label

    # ---------------------------------------------------------------- emitter
    def reg(self, name):
        if name not in self.regs:
            if len(self.regs) >= 256:
                raise CompileError("more than 256 registers")
            self.regs[name] = len(self.regs)
        return self.regs[name]

    def label(self):
        self.nlabel += 1
        return "L%d" % self.nlabel

    def place(self, lab):
        self.items.append(('label', lab))
        for k in self.eq:
            self.eq[k].clear()
        self.dead = False

    def jump(self, kind, lab):
        if self.dead:
            return
        self.items.append(('j', kind, lab))
        if kind == 'jmp':
            self.dead = True

    def op(self, text):
        if self.dead:
            return
        t = text.split()
        eq = self.eq
        size = len(t)
        if len(t) == 2 and t[0] in ('a=r', 'b=r', 'c=r', 'd=r'):
            r = t[0][0]
            n = int(t[1])
            if n in eq[r]:
                return
            eq[r] = {n}
        elif t[0] == 'r=a':
            n = int(t[1])
            for r in 'bcd':
                eq[r].discard(n)
            eq['a'].add(n)
        elif len(t[0]) == 3 and t[0][1] == '=' and t[0][0] in 'abcd' and t[0][2] in 'abcd':
            if t[0][0] == t[0][2]:
                return
            eq[t[0][0]] = set(eq[t[0][2]])
        elif t[0][0] == '*' or t[0] in ('out', 'halt') or t[0].startswith('a==') or \
                (t[0].startswith('a<') and not t[0].startswith('a<<') and not t[0].startswith('a<>')) or \
                (t[0].startswith('a>') and not t[0].startswith('a>>')):
            pass
        else:
            assert t[0][0] in 'abcd', text
            eq[t[0][0]].clear()
        self.items.append(('op', text, size))

    def loadk(self, v):
        v &= MASK32
        if v == 0:
            self.op("a=0")
            return
        if v < 256:
            self.op("a= %d" % v)
            return
        if v == MASK32:
            self.op("a=0")
            self.op("a--")
            return
        s = (v & -v).bit_length() - 1
        if (v >> s) < 256:
            self.op("a= %d" % (v >> s))
            self.op("a<<= %d" % s)
            return
        w = v + 1
        s = (w & -w).bit_length() - 1
        if w <= MASK32 and (w >> s) < 256:
            self.op("a= %d" % (w >> s))
            self.op("a<<= %d" % s)
            self.op("a--")
            return
        for s2 in range(1, 32):
            if v & ((1 << s2) - 1) == 0:
                u = (v >> s2) + 1
                s1 = (u & -u).bit_length() - 1
                if (u >> s1) < 256:
                    self.op("a= %d" % (u >> s1))
                    self.op("a<<= %d" % s1)
                    self.op("a--")
                    self.op("a<<= %d" % s2)
                    return
        bs = []
        while v:
            bs.append(v & 255)
            v >>= 8
        self.op("a= %d" % bs[-1])
        for b in reversed(bs[:-1]):
            self.op("a<<= 8")
            if b:
                self.op("a+= %d" % b)

    # ---------------------------------------------------------------- expressions
    def fold(self, n):
        """Constant folding and normal form: a constant or the simpler operand of a commutative op on the right."""
        if isinstance(n, ast.Name) and n.id in self.consts:
            return ast.Constant(self.consts[n.id])
        if isinstance(n, ast.BinOp):
            l = self.fold(n.left)
            r = self.fold(n.right)
            if isinstance(l, ast.Constant) and isinstance(r, ast.Constant):
                return ast.Constant(PYOP[type(n.op)](l.value, r.value))
            if isinstance(n.op, COMMUT) and self.rank(l) < self.rank(r):
                l, r = r, l
            # (x + c1) + c2
            if isinstance(n.op, ast.Add) and isinstance(r, ast.Constant) and isinstance(l, ast.BinOp) and \
                    isinstance(l.op, ast.Add) and isinstance(l.right, ast.Constant):
                return ast.BinOp(l.left, ast.Add(), ast.Constant(l.right.value + r.value))
            return ast.BinOp(l, n.op, r)
        if isinstance(n, ast.Subscript):
            return ast.Subscript(n.value, self.fold(n.slice), n.ctx)
        return n

    def rank(self, n):                   # how good a right operand it is: higher = more complex
        if isinstance(n, ast.Constant):
            return 0 if 0 <= n.value < 256 else 2
        if isinstance(n, ast.Name):
            return 1
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Name):
            return 3
        return 4

    def clob(self, n):
        """Registers among b, c, d that evaluating the (folded) expression changes."""
        if isinstance(n, (ast.Constant, ast.Name)):
            return set()
        if isinstance(n, ast.Subscript):
            return {'c' if n.value.id == 'M' else 'd'} | self.clob(n.slice)
        if isinstance(n, ast.BinOp):
            l, r = n.left, n.right
            if isinstance(n.op, ast.BitAnd) and isinstance(r, ast.Constant) and r.value == MASK32:
                return self.clob(l)
            if isinstance(r, ast.Constant) and 0 <= r.value < 256:
                return self.clob(l)
            if isinstance(r, ast.Name):
                return self.clob(l) | {'b'}
            if isinstance(r, ast.Subscript) and isinstance(r.slice, ast.Name):
                return self.clob(l) | {'c' if r.value.id == 'M' else 'd'}
            return self.clob(l) | self.clob(r) | {'b'}
        raise CompileError("line %d: expression not supported: %s" % (getattr(n, 'lineno', 0), ast.dump(n)))

    def ev(self, n, folded=False):
        """Code that leaves the value of the expression in A."""
        if not folded:
            n = self.fold(n)
        if isinstance(n, ast.Constant):
            self.loadk(n.value)
        elif isinstance(n, ast.Name):
            self.op("a=r %d" % self.reg(n.id))
        elif isinstance(n, ast.Subscript):
            p = 'c' if n.value.id == 'M' else 'd'
            if isinstance(n.slice, ast.Name):
                self.op("%s=r %d" % (p, self.reg(n.slice.id)))
            else:
                self.ev(n.slice, True)
                self.op("%s=a" % p)
            self.op("a=*%s" % p)
        elif isinstance(n, ast.BinOp):
            l, r = n.left, n.right
            if isinstance(n.op, ast.BitAnd) and isinstance(r, ast.Constant) and r.value == MASK32:
                self.ev(l, True)
                return
            o = BINOPS[type(n.op)]
            if isinstance(r, ast.Constant) and r.value == 1 and isinstance(n.op, (ast.Add, ast.Sub)):
                self.ev(l, True)
                self.op("a++" if isinstance(n.op, ast.Add) else "a--")
            else:
                self.operand(l, r, "a%s=" % o)
        else:
            raise CompileError("line %d: expression not supported" % getattr(n, 'lineno', 0))

    def operand(self, l, r, o):
        """A = l, then the instruction `o` (a+=, a==, a<, ...) with r as its operand."""
        if isinstance(r, ast.Constant) and 0 <= r.value < 256:
            self.ev(l, True)
            self.op("%s %d" % (o, r.value))
        elif isinstance(r, ast.Name):
            self.ev(l, True)
            self.op("b=r %d" % self.reg(r.id))
            self.op(o + "b")
        elif isinstance(r, ast.Subscript) and isinstance(r.slice, ast.Name):
            p = 'c' if r.value.id == 'M' else 'd'
            self.ev(l, True)
            self.op("%s=r %d" % (p, self.reg(r.slice.id)))
            self.op(o + "*" + p)
        elif 'b' not in self.clob(l):
            self.ev(r, True)
            self.op("b=a")
            self.ev(l, True)
            self.op(o + "b")
        else:
            t = self.reg("_t%d" % self.ntemp)
            self.ntemp += 1
            self.ev(r, True)
            self.op("r=a %d" % t)
            self.ev(l, True)
            self.op("b=r %d" % t)
            self.op(o + "b")
            self.ntemp -= 1

    # ---------------------------------------------------------------- conditions
    def cjump(self, n, lab, when):
        """Jump to lab if the truth of the condition equals `when`; otherwise fall through."""
        if isinstance(n, ast.BoolOp):
            is_and = isinstance(n.op, ast.And)
            if is_and != when:           # and/False, or/True: any operand decides
                for v in n.values:
                    self.cjump(v, lab, when)
            else:
                skip = self.label()
                for v in n.values[:-1]:
                    self.cjump(v, skip, not when)
                self.cjump(n.values[-1], lab, when)
                self.place(skip)
            return
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            self.cjump(n.operand, lab, not when)
            return
        if isinstance(n, ast.Name) and n.id in self.consts:
            n = ast.Constant(self.consts[n.id])
        if isinstance(n, ast.Constant):
            if bool(n.value) == when:
                self.jump('jmp', lab)
            return
        if isinstance(n, ast.Compare):
            if len(n.ops) != 1:
                raise CompileError("line %d: chained comparison" % n.lineno)
            l = self.fold(n.left)
            r = self.fold(n.comparators[0])
            op = type(n.ops[0])
            if self.rank(l) < self.rank(r):          # the simpler operand on the right
                l, r = r, l
                op = {ast.Lt: ast.Gt, ast.Gt: ast.Lt, ast.LtE: ast.GtE, ast.GtE: ast.LtE}.get(op, op)
            ins, truth = {ast.Eq: ("a==", True), ast.NotEq: ("a==", False), ast.Lt: ("a<", True),
                          ast.Gt: ("a>", True), ast.LtE: ("a>", False), ast.GtE: ("a<", False)}[op]
            self.operand(l, r, ins)
            self.jump('jt' if truth == when else 'jf', lab)
            return
        self.ev(n)
        self.op("a== 0")
        self.jump('jf' if when else 'jt', lab)

    # ---------------------------------------------------------------- statements
    def target_of(self, s):
        """If the statement is a bare jump (break, continue, return, fail in non-debug), its label."""
        if isinstance(s, ast.Break):
            return self.loops[-1][0]
        if isinstance(s, ast.Continue):
            return self.loops[-1][1]
        if isinstance(s, ast.Return):
            return self.rets[-1]
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and s.value.func.id == 'fail' and not self.debug:
            return self.fails[-1]
        return None

    def block(self, body):
        for s in body:
            self.stmt(s)

    def assign(self, tgt, val):
        if isinstance(tgt, ast.Name):
            if tgt.id in self.consts or tgt.id.isupper():
                raise CompileError("line %d: assignment to a constant" % tgt.lineno)
            self.ev(val)
            self.op("r=a %d" % self.reg(tgt.id))
            return
        assert isinstance(tgt, ast.Subscript) and tgt.value.id in ('M', 'H'), ast.dump(tgt)
        p = 'c' if tgt.value.id == 'M' else 'd'
        idx = self.fold(tgt.slice)
        val = self.fold(val)
        if isinstance(idx, ast.Name):
            self.ev(val, True)
            self.op("%s=r %d" % (p, self.reg(idx.id)))
        elif p not in self.clob(val):
            self.ev(idx, True)
            self.op("%s=a" % p)
            self.ev(val, True)
        else:
            t = self.reg("_t%d" % self.ntemp)
            self.ntemp += 1
            self.ev(idx, True)
            self.op("r=a %d" % t)
            self.ev(val, True)
            self.op("%s=r %d" % (p, t))
            self.ntemp -= 1
        self.op("*%s=a" % p)

    def stmt(self, s):
        if isinstance(s, ast.Pass):
            return
        if isinstance(s, ast.Assign):
            assert len(s.targets) == 1
            self.assign(s.targets[0], s.value)
        elif isinstance(s, ast.AugAssign):
            self.assign(s.target, ast.BinOp(copy.deepcopy(s.target), s.op, s.value))
        elif isinstance(s, ast.If):
            if isinstance(s.test, ast.Name) and s.test.id in self.consts:    # only the branch taken
                self.block(s.body if self.consts[s.test.id] else s.orelse)
                return
            if len(s.body) == 1 and not s.orelse and self.target_of(s.body[0]):
                self.cjump(s.test, self.target_of(s.body[0]), True)
                return
            lelse = self.label()
            self.cjump(s.test, lelse, False)
            self.block(s.body)
            if s.orelse:
                lend = self.label()
                self.jump('jmp', lend)
                self.place(lelse)
                self.block(s.orelse)
                self.place(lend)
            else:
                self.place(lelse)
        elif isinstance(s, ast.While):
            assert not s.orelse
            top = self.label()
            end = self.label()
            if isinstance(s.test, ast.Constant) and s.test.value:
                self.loops.append((end, top))
                self.place(top)
                body = s.body
                last = body[-1]
                if isinstance(last, ast.If) and not last.orelse and len(last.body) == 1 and \
                        isinstance(last.body[0], ast.Break):
                    self.block(body[:-1])
                    self.cjump(last.test, top, False)     # do ... while not test
                else:
                    self.block(body)
                    self.jump('jmp', top)
            else:
                test = self.label()
                self.loops.append((end, test))
                self.jump('jmp', test)
                self.place(top)
                self.block(s.body)
                self.place(test)
                self.cjump(s.test, top, True)
            self.loops.pop()
            self.place(end)
        elif isinstance(s, (ast.Break, ast.Continue, ast.Return)):
            if isinstance(s, ast.Return) and s.value is not None:
                raise CompileError("line %d: return with a value" % s.lineno)
            self.jump('jmp', self.target_of(s))
        elif isinstance(s, ast.Try):
            assert len(s.handlers) == 1 and s.handlers[0].type.id == 'Fail' and not s.orelse and not s.finalbody
            lf = self.label()
            lend = self.label()
            self.fails.append(lf)
            self.block(s.body)
            self.fails.pop()
            self.jump('jmp', lend)
            self.place(lf)
            self.block(s.handlers[0].body)
            self.place(lend)
        elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
            self.call(s.value)
        elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            pass
        else:
            raise CompileError("line %d: statement not supported" % s.lineno)

    def simple(self, n):
        n = self.fold(n)
        if not isinstance(n, (ast.Name, ast.Constant)):
            raise CompileError("line %d: argument must be a name or a constant" % getattr(n, 'lineno', 0))
        return n

    def call(self, c):
        name = c.func.id
        if name == 'fail':
            if self.debug:
                self.ev(c.args[0])
                self.op("r=a %d" % self.reg('ferr'))
            self.jump('jmp', self.fails[-1])
        elif name == 'out':
            self.ev(c.args[0])
            self.op("out")
        elif name == 'dbg':
            if self.debug:
                self.ev(c.args[0])
                self.op("out")
                for _ in range(3):
                    self.op("a>>= 8")
                    self.op("out")
        elif name == 'copyout':
            dst, src, n = [self.simple(x) for x in c.args]
            top = self.label()
            self.ev(self.fold(ast.BinOp(dst, ast.Add(), n)), True)
            self.op("d=a")
            for r, x in (('c', dst), ('b', src)):
                if isinstance(x, ast.Name):
                    self.op("%s=r %d" % (r, self.reg(x.id)))
                else:
                    self.ev(x, True)
                    self.op("%s=a" % r)
            self.place(top)
            for t in ("a=*b", "*c=a", "out", "b++", "c++", "a=c", "a==d"):
                self.op(t)
            self.jump('jf', top)
        elif name == 'ld16':
            x, p = c.args
            assert isinstance(x, ast.Name) and isinstance(p, ast.Name) and x.id not in self.consts
            self.op("c=r %d" % self.reg(p.id))
            for t in ("a=*c", "b=a", "c++", "a=*c", "a<<= 8", "a|=b"):
                self.op(t)
            self.op("r=a %d" % self.reg(x.id))
        elif name == 'loadtable':
            self.loadtable(tables.TABLE[self.fold(c.args[0]).value])
        elif name in self.funcs:
            f = self.funcs[name]
            if name in self.inl:
                raise CompileError("line %d: recursive call of %s" % (c.lineno, name))
            params = [a.arg for a in f.args.args]
            if len(params) != len(c.args):
                raise CompileError("line %d: wrong number of arguments" % c.lineno)
            m = dict(zip(params, [self.simple(a) for a in c.args]))
            argnames = {a.id for a in m.values() if isinstance(a, ast.Name)}
            for node in ast.walk(f):
                tg = []
                if isinstance(node, ast.Assign):
                    tg = node.targets
                elif isinstance(node, ast.AugAssign):
                    tg = [node.target]
                for t in tg:
                    if isinstance(t, ast.Name) and (t.id in params or t.id in argnames):
                        raise CompileError("line %d: %s assigns to a parameter or an argument (%s)"
                                           % (c.lineno, name, t.id))
            body = [Subst(m).visit(copy.deepcopy(b)) for b in f.body]
            ret = self.label()
            self.rets.append(ret)
            self.inl.append(name)
            self.block(body)
            self.inl.pop()
            self.rets.pop()
            self.place(ret)
        else:
            raise CompileError("line %d: unknown function %s" % (c.lineno, name))

    def loadtable(self, v):
        """H[0..255] = v: the value in A, each entry from the one before (a++, a+= N, a-= N, or loaded);
        4 or more entries that go up by one are a loop with the value in B."""
        self.op("d=0")
        self.loadk(v[0])
        self.op("*d=a")
        self.op("d++")
        i = 1
        while i < 256:
            run = 0
            while i + run < 255 and v[i + run] == v[i + run - 1] + 1:
                run += 1
            if run >= 4:
                top = self.label()
                self.op("b=a")
                self.place(top)
                for t in ("b++", "*d=b", "d++", "a=d", "a== %d" % (i + run)):
                    self.op(t)
                self.jump('jf', top)
                self.op("a=b")
                i += run
                continue
            d = v[i] - v[i - 1]
            if d == 1:
                self.op("a++")
            elif 0 < d < 256:
                self.op("a+= %d" % d)
            elif -256 < d < 0:
                self.op("a-= %d" % -d)
            elif d:
                self.loadk(v[i])
            self.op("*d=a")
            self.op("d++")
            i += 1

    # ---------------------------------------------------------------- assembly
    def assemble(self):
        """Sizes the jumps (short first, those out of range become long) and returns the text lines."""
        items = self.items
        long = [False] * len(items)
        while True:
            addr = []
            labels = {}
            a = 0
            for i, it in enumerate(items):
                addr.append(a)
                if it[0] == 'op':
                    a += it[2]
                elif it[0] == 'label':
                    labels[it[1]] = a
                else:
                    a += (3 if it[1] == 'jmp' else 5) if long[i] else 2
            changed = False
            for i, it in enumerate(items):
                if it[0] == 'j' and not long[i]:
                    off = labels[it[2]] - (addr[i] + 2)
                    if off < -128 or off > 127:
                        long[i] = True
                        changed = True
            if not changed:
                break
        lines = []
        for i, it in enumerate(items):
            if it[0] == 'op':
                lines.append(it[1])
            elif it[0] == 'j':
                tgt = labels[it[2]]
                if not long[i]:
                    lines.append("%s %d" % (it[1], tgt - (addr[i] + 2)))
                elif it[1] == 'jmp':
                    lines.append("lj %d" % tgt)
                else:
                    lines.append("%s 3 lj %d" % ('jf' if it[1] == 'jt' else 'jt', tgt))
        return lines, a


HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sylz_src.py")


def compile_file(variant, debug=False, src=SRC):
    consts, funcs, _ = load_source(src)
    consts['V5'] = 1 if variant == 5 else 0
    consts['DEBUG'] = 1 if debug else 0
    g = Gen(consts, funcs, debug)
    # a byte of the segment: into M at C. The end of the segment (A > 255): n = C, decode, C = 0
    eos = g.label()
    end = g.label()
    g.op("a> 255")
    g.jump('jt', eos)
    g.op("*c=a")
    g.op("c++")
    g.op("halt")
    g.place(eos)
    g.op("a=c")
    g.op("r=a %d" % g.reg('n'))
    g.rets.append(end)
    g.inl.append('decode')
    g.block(funcs['decode'].body)
    g.place(end)
    g.op("c=0")
    g.op("halt")
    lines, size = g.assemble()
    return g, consts, lines, size


def min_ph(variant):
    return 12 if variant == 5 else 8


def body(variant, debug=False):
    g, consts, lines, size = compile_file(variant, debug)
    if size > 65000:
        sys.exit("program too big: %d bytes" % size)
    name = "zpaqsylz%d" % variant
    fm = "v2, v3, v4 and v5" if variant == 5 else "v2 and v4"
    out = ["hcomp", "  halt", "pcomp %s ;" % name,
           "(ZPAQSYLZ%d: sylz formats %s (syc v0.8.0, frozen), for zpaq-std -ma:sylz%d." % (variant, fm, variant),
           " zpaq-std, 2026. The segment into M; at its end, the sequences. Generated by gen.py%s:" %
           (" [DEBUG]" if debug else ""),
           " %d bytes of code, %d registers.)" % (size, len(g.regs))]
    line = ""
    for t in lines:
        if len(line) + len(t) > 100:
            out.append(line)
            line = ""
        line += " " + t
    out.append(line)
    out.append("end")
    return "\n".join(out) + "\n", g, size


HEADER = r"""/*
  ZPAQSYLZ%(v)d: a decoder for sylz format%(fm)s (syc v0.8.0, frozen) written in ZPAQL, for zpaq-std
  -ma:sylz%(v)d: what the plugin codec sylz%(v)d writes%(also)s. zpaq-std, 2026.
  Generated by `gen.py %(v)d header` from sylz_src.py (next to gen.py), which is also the Python
  model of the same algorithm (zref.py); tests.py checks both against syc's tools/sylz_ref.py.

  The whole segment (the original size, u32le, and the block) is kept in M and decoded at its end: the
  tokens (the running table of 256 entries in H), the offsets and the literals are read where they are in
  the segment, and the output goes through a window of 65536 bytes at the top of M%(lit)s.
  Every loop is bounded by a count known before it starts; a damaged block ends at once, and the last
  byte of the output is only written when every check has passed (so the output is short, and zpaq's
  SHA-1 reports it).

  M (2^pm bytes): the segment and %(top)s bytes: pm = the smallest with 2^pm >= segment + %(top)s
  (zpaqsylz%(v)d_pm). H: ph = %(ph)d. %(code)d bytes of code.

  FROZEN, like the other portable decoders.
*/
static const char ZPAQSYLZ%(v)d_CUERPO[] = R"ZSY%(v)d(%(body)s)ZSY%(v)d";
"""


def main():
    args = sys.argv[1:]
    debug = False
    if args and args[0] == '-d':
        debug = True
        args = args[1:]
    if not args or args[0] not in ('4', '5'):
        sys.exit(__doc__)
    variant = int(args[0])
    args = args[1:]
    text, g, size = body(variant, debug)
    if args and args[0] == 'body':
        sys.stdout.write(text)
    elif args and args[0] == 'header':
        assert ')ZSY' not in text
        sys.stdout.write(HEADER % dict(
            v=variant, body=text, code=size, ph=min_ph(variant),
            fm="s v2 and v4" if variant == 4 else "s v2, v3, v4 and v5",
            also=" (a v2 block where that is smaller)" if variant == 4 else " (v5, or a block of a format below it)",
            lit="" if variant == 4 else
            ", the literals of a Huffman chunk (65536 at most) through a buffer below it (H also has the\n"
            "  2048-entry decoding table)",
            top="65536" if variant == 4 else "131072"))
    else:
        ph = int(args[0]) if args else min_ph(variant)
        pm = int(args[1]) if len(args) > 1 else 24
        if ph < min_ph(variant):
            sys.exit("PH must be at least %d" % min_ph(variant))
        sys.stdout.write("comp 0 0 %d %d 0\n" % (ph, pm) + text)
    regs = " ".join("%s=%d" % kv for kv in sorted(g.regs.items(), key=lambda kv: kv[1]))
    sys.stderr.write("zpaqsylz%d%s: %d bytes of code, %d registers: %s\n" % (variant, " [DEBUG]" if debug else "", size, len(g.regs), regs))


if __name__ == "__main__":
    main()
