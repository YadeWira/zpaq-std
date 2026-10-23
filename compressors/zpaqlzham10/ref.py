#!/usr/bin/env python3
# Decodificador de referencia de LZHAM 1.0 (LZHAM_DLL_VERSION 0x1010, el de lzham-ex que
# usa zpaq-std -ma:lzh desde 1.6.0: dict 2^20, sin zlib, sin hilos, tasa de actualizacion
# por defecto). Sirve de especificacion ejecutable para el ZPAQL (gen.py). Diferencias con
# el formato alpha 0x1008 de ../zpaqlzham: sin los 2 bits de configuracion, un solo modelo
# de literales y uno de literales delta, is_match indexado solo por el estado, sin codigos
# polares, otro crecimiento del ciclo de los modelos y el Adler-32 al final.
import sys

class Bits:
    """Flujo MSB-first; pasado el final, ceros (como lzham)."""
    def __init__(s, b): s.b=b; s.p=0; s.buf=0; s.n=0
    def get(s, k):
        while s.n < k:
            c = s.b[s.p] if s.p < len(s.b) else 0
            s.p += 1; s.buf = (s.buf<<8)|c; s.n += 8
        if k == 0: return 0
        s.n -= k; r = (s.buf >> s.n) & ((1<<k)-1); s.buf &= (1<<s.n)-1
        return r
    def peek(s, k):
        while s.n < k:
            c = s.b[s.p] if s.p < len(s.b) else 0
            s.p += 1; s.buf = (s.buf<<8)|c; s.n += 8
        return (s.buf >> (s.n-k)) & ((1<<k)-1)
    def align(s): s.get(s.n & 7)

def radix_sorted(freq):
    # orden estable por frecuencia ascendente (empates: indice de simbolo)
    return sorted(range(len(freq)), key=lambda i: freq[i])

def moffat(A):
    n=len(A)
    if n==1: A[0]=0; return A
    A[0]+=A[1]; root=0; leaf=2
    for nxt in range(1,n-1):
        if leaf>=n or A[root]<A[leaf]:
            A[nxt]=A[root]; A[root]=nxt; root+=1
        else:
            A[nxt]=A[leaf]; leaf+=1
        if leaf>=n or (root<nxt and A[root]<A[leaf]):
            A[nxt]+=A[root]; A[root]=nxt; root+=1
        else:
            A[nxt]+=A[leaf]; leaf+=1
    A[n-2]=0
    for nxt in range(n-3,-1,-1): A[nxt]=A[A[nxt]]+1
    avbl=1; used=dpth=0; root=n-2; nxt=n-1
    while avbl>0:
        while root>=0 and A[root]==dpth: used+=1; root-=1
        while avbl>used: A[nxt]=dpth; nxt-=1; avbl-=1
        avbl=2*used; dpth+=1; used=0
    return A

def huff_sizes(freq):
    n=len(freq); order=radix_sorted(freq)
    if n==1: return [1]
    x=moffat([freq[i] for i in order])
    cs=[0]*n
    for k,i in enumerate(order): cs[i]=x[k]
    return cs

def limit(cs, mx=16):
    n=len(cs); nc=[0]*35
    for c in cs: nc[c]+=1
    if max(cs)<=mx: return cs
    ofs=0; nso=[0]*35
    for i in range(1,35): nso[i]=ofs; ofs+=nc[i]
    for i in range(mx+1,35): nc[mx]+=nc[i]
    tot=sum(nc[i]<<(mx-i) for i in range(mx,0,-1))
    if tot==(1<<mx): pass
    else:
        while True:
            nc[mx]-=1
            i=mx-1
            while i:
                if nc[i]:
                    nc[i]-=1; nc[i+1]+=2; break
                i-=1
            assert i
            tot-=1
            if tot==(1<<mx): break
    new=[]
    for i in range(1,mx+1): new+= [i]*nc[i]
    out=list(cs)
    for i in range(n):
        c=cs[i]
        if c:
            out[i]=new[nso[c]]; nso[c]+=1
    return out

class Model:
    def __init__(s, n):
        # tasa 8 (la de por defecto): max_update_interval 64, adapt_rate 64
        s.n=n; s.max_cycle=min((max(24,n)+6)*64,32767)
        s.reset()
    def reset(s):
        s.freq=[1]*s.n; s.cycle=s.n; s.total=0; s.until=0
        s.update(); s.until=s.cycle=min(s.max_cycle,16)
    def rescale(s):
        s.freq=[(f+1)>>1 for f in s.freq]; s.total=sum(s.freq)
    def reset_rate(s):
        s.total+=s.cycle-s.until
        if s.total>s.n: s.rescale()
        s.until=s.cycle=min(8,s.cycle)
    def update(s):
        s.total+=s.cycle
        while s.total>=32768: s.rescale()
        cs=huff_sizes(s.freq)
        if max(cs)>16: cs=limit(cs)
        s.build(cs)
        s.cycle = (31+s.cycle*64)>>5
        if s.cycle>s.max_cycle: s.cycle=s.max_cycle
        s.until=s.cycle
    def build(s, cs):
        # canonico: por largo, y dentro del largo por simbolo
        s.tab={}; code=0
        for L in range(1,17):
            for i in range(s.n):
                if cs[i]==L: s.tab[(L,code)]=i; code+=1
            code<<=1
        s.cs=cs
    def decode(s, bits):
        code=0
        for L in range(1,17):
            code=(code<<1)|bits.get(1)
            r=s.tab.get((L,code))
            if r is not None: break
        else: raise Exception("bad code")
        s.freq[r]+=1; s.until-=1
        if s.until==0: s.update()
        return r

class Arith:
    def __init__(s, bits): s.bits=bits
    def start(s):
        s.v=0
        for _ in range(4): s.v=((s.v<<8)|s.bits.get(8))&0xFFFFFFFF
        s.l=0xFFFFFFFF
    def bit(s, probs, i):
        while s.l < 0x01000000:
            s.v=((s.v<<8)|s.bits.get(8))&0xFFFFFFFF; s.l=(s.l<<8)&0xFFFFFFFF
        p=probs[i]; x=p*(s.l>>11)
        if s.v>=x:
            probs[i]=p-(p>>5); s.v-=x; s.l-=x; return 1
        probs[i]=p+((2048-p)>>5); s.l=x; return 0

LIT_NEXT=[0,0,0,0,1,2,3,4,5,6,4,5]
HUGE_BASE=[258,258+256,258+256+1024,258+256+1024+4096]
HUGE_LEN=[8,10,12,16]

def slots(log2=20):
    eb=[0]*128; j=0
    for i in range(0,128,2):
        eb[i]=eb[i+1]=j
        if i!=0 and j<25: j+=1
    base=[0]*128; j=0
    for i in range(128): base[i]=j; j+=1<<eb[i]
    big=(1<<log2)-1
    for i in range(128):
        if base[i]<=big<base[i]+(1<<eb[i]): return eb,base,i+1
    raise Exception

def decompress(data):
    eb,base,nslots=slots()
    b=Bits(data); ar=Arith(b)
    mk=Model
    def tables():
        return ([mk(256)],[mk(256)],
                mk(2+(nslots-1)*8),[mk(1+256) for _ in range(2)],[mk(1+249) for _ in range(2)],mk(16))
    lit,dlit,main,replen,largelen,dlsb=tables()
    def bitmodels():
        return dict(m=[1024]*12,r=[1024]*12,r0=[1024]*12,r0s=[1024]*12,r1=[1024]*12,r2=[1024]*12)
    bm=bitmodels()
    allm=lambda: lit+dlit+[main]+replen+largelen+[dlsb]
    out=bytearray()
    def huge():
        k=0
        while k<3:
            if not b.get(1): break
            k+=1
        return HUGE_BASE[k]+b.get(HUGE_LEN[k])
    while True:
        bt=b.get(2)
        if bt==0:
            ft=b.get(2)
            if ft==1:
                for m in allm(): m.reset_rate()
            elif ft==2:
                for m in allm(): m.reset()
                bm.update(bitmodels())
            b.align()
            if b.get(16)!=0 or b.get(16)!=0xFFFF: raise Exception("bad sync")
        elif bt==2:
            n=b.get(24); chk=b.get(8)
            if chk!=((n&255)^((n>>8)&255)^((n>>16)&255)): raise Exception("bad raw")
            n+=1; b.align()
            for _ in range(n): out.append(b.get(8))
        elif bt==1:
            ar.start()
            h0=h1=h2=h3=1; st=0
            ft=b.get(2)
            if ft==1:
                for m in allm(): m.reset_rate()
            elif ft==2:
                for m in allm(): m.reset()
                bm.update(bitmodels())
            while True:
                if not ar.bit(bm['m'], st):
                    if st<7:
                        r=lit[0].decode(b)
                    else:
                        o=len(out)-h0
                        if o<0: raise Exception("bad dist")
                        r0=out[o]
                        r=dlit[0].decode(b)^r0
                    out.append(r)
                    st=LIT_NEXT[st]
                    continue
                ml=1
                if ar.bit(bm['r'],st):
                    if ar.bit(bm['r0'],st):
                        if ar.bit(bm['r0s'],st):
                            st=9 if st<7 else 11
                        else:
                            ml=replen[st>=7].decode(b)+2
                            if ml==258: ml=huge()
                            st=8 if st<7 else 11
                    else:
                        ml=replen[st>=7].decode(b)+2
                        if ml==258: ml=huge()
                        if ar.bit(bm['r1'],st): h0,h1=h1,h0
                        elif ar.bit(bm['r2'],st): h0,h1,h2=h2,h0,h1
                        else: h0,h1,h2,h3=h3,h0,h1,h2
                        st=8 if st<7 else 11
                else:
                    sym=main.decode(b)-2
                    if sym<0:
                        if sym==-2: break
                        h0=h1=h2=h3=1; st=0; continue
                    ml=(sym&7)+2; slot=(sym>>3)+1
                    if ml==9:
                        ml+=largelen[st>=7].decode(b)
                        if ml==258: ml=huge()
                    ne=eb[slot]
                    if ne<3: ex=b.get(ne)
                    else:
                        ex=0
                        if ne>4: ex=b.get(ne-4)<<4
                        ex+=dlsb.decode(b)
                    h0,h1,h2,h3=base[slot]+ex,h0,h1,h2
                    st=7 if st<7 else 10
                if h0>len(out): raise Exception("bad dist")
                s0=len(out)-h0
                for k in range(ml): out.append(out[s0+k])
            b.align()
        else:
            break
    b.align()
    ad=(b.get(16)<<16)|b.get(16)
    s1,s2=1,0
    for c in out: s1=(s1+c)%65521; s2=(s2+s1)%65521
    if ad!=(s2<<16)|s1: raise Exception("bad adler32")
    return bytes(out)

if __name__=="__main__":
    d=open(sys.argv[1],'rb').read()
    o=decompress(d)
    open(sys.argv[2],'wb').write(o)
