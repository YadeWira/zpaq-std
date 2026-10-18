#!/usr/bin/env python3
# Generates ZPAQSYLZ: a ZPAQL post-processor that decodes one sylz format v2
# block (syc v0.2.2) per segment. The token table is built from SYLZ_TOKENS.
# The segment is: original size u32le, then the sylz block. The decoder never
# writes more than the original size, so a damaged block (a length extension
# of 255s, say) ends at once instead of writing gigabytes.
# Usage: gen_zpaqsylz.py [PH] > zpaqsylz.cfg   (PH: log2 of the H words)
import sys, re
s = open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'sylz', 'sylz.pas')).read()
t = s[s.index('SYLZ_TOKENS: array[0..255] of UInt32 = ('):]; t = t[:t.index(');')]
T = [int(x, 16) for x in re.findall(r'\$([0-9A-F]+)', t)]; assert len(T) == 256

def const(v):
    # a = v, from 8-bit immediates
    parts = [(v >> 16) & 255, (v >> 8) & 255, v & 255]
    out = []; started = False
    for i, p in enumerate(parts):
        if not started:
            if p == 0 and i < 2: continue
            out.append(f'a= {p}'); started = True
        else:
            out.append('a<<= 8')
            if p: out.append(f'a+= {p}')
    return ' '.join(out)

def table():
    lines = ['    d= 0']
    prev = None
    for v in T:
        if prev is not None and v == prev + 256:
            lines.append('    a+= 255 a++ *d=a d++')
        else:
            lines.append(f'    {const(v)} *d=a d++')
        prev = v
    return '\n'.join(lines)

body = f'''hcomp
  halt
pcomp zpaqsylz ;
  (r1 phase: 0 sizes, 1 control, 2 literals of a sequence, 3 tail)
  (r2 header bytes read, r16 bytes still to write, r3 ctrlLen, r6 end of control in H, r5 saved d)
  (r7 literals left, r8 match length, r10 offset, r11 token, r13 step, r14 match pending)
  (r15 table entry, r9 table built, r12 r4 temporaries; b output in M)
  a> 255 ifl
    a=0 r=a 1 r=a 2 r=a 3 r=a 13 r=a 14 r=a 16
    halt
  endif
  c=a
  a=r 9 a== 0 ifl
{table()}
    a= 1 r=a 9
  endif
  a=0 r=a 13
  a=r 1
  a== 0 ifl
    a=r 2 a&= 3 a<<= 3 r=a 4
    a=c r=a 12
    a=r 4 c=a a=r 12 a<<=c c=a
    a=r 2 a< 4 ifl
      a=r 16 a+=c r=a 16
    elsel
      a=r 3 a+=c r=a 3
    endif
    a=r 2 a++ r=a 2
    a== 8 ifl
      a=r 3 a== 0 ifl
        a= 3 r=a 1
      elsel
        a= 1 r=a 1
        a= 255 a++ d=a
        a=r 3 a+=d r=a 6
      endif
    endif
  elsel
    a== 1 ifl
      a=c *d=a d++
      a=r 6 c=a a=d a==c ifl
        a= 255 a++ d=a
        a=0 r=a 14
        a= 1 r=a 13
      endif
    elsel
      a== 2 ifl
        a=r 16 a> 0 if
          a-- r=a 16 a=c *b=a out b++
        endif
        a=r 7 a-- r=a 7
        a== 0 ifl
          a= 1 r=a 13
        endif
      elsel
        a=r 16 a> 0 if
          a-- r=a 16 a=c out
        endif
      endif
    endif
  endif
  a=r 13 a== 1 ifl
    do
      a=r 14 a== 1 ifl
        a=r 8 c=r 16 a>c if
          a=c r=a 8
        endif
        a=r 16 c=r 8 a-=c r=a 16
        a=b c=r 10 a-=c c=a
        a=r 8 a> 0 ifl
          do
            a=*c *b=a out b++ c++
            a=r 8 a-- r=a 8
          a> 0 while
        endif
        a=0 r=a 14
      endif
      a=r 6 c=a a=d a<c ifl
        a=*d d++ r=a 11
        a=*d d++ r=a 10
        a=*d d++ a<<= 8 c=a a=r 10 a+=c a++ r=a 10
        a=d r=a 5 a=r 11 d=a a=*d r=a 15 a=r 5 d=a
        a=r 15 a&= 255 r=a 7
        a=r 15 a>>= 8 a&= 255 r=a 8
        a=r 15 a>>= 16 a&= 1 a== 1 ifl
          do
            a=*d d++ c=a a=r 7 a+=c r=a 7
            a=c a== 255
          while
        endif
        a=r 15 a>>= 17 a&= 1 a== 1 ifl
          do
            a=*d d++ c=a a=r 8 a+=c r=a 8
            a=c a== 255
          while
        endif
        a= 1 r=a 14
        a=r 7 a> 0 ifl
          a= 2 r=a 1 a=0 r=a 13
        endif
      elsel
        a= 3 r=a 1 a=0 r=a 13
      endif
    a=r 13 a== 1 while
  endif
  halt
end
'''
if len(sys.argv) > 1 and sys.argv[1] == 'body':
    sys.stdout.write(body)
else:
    ph = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    sys.stdout.write(f'comp 0 0 {ph} 17 0\n' + body)
