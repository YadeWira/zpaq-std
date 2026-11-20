/*
	zpaq-std: the JIT for AArch64 (ARM64).

	libzpaq turns ZPAQL into machine code on x86 and x86-64 only; everywhere
	else the programs (HCOMP, PCOMP) and the model (COMP) run on the
	interpreter. This file is the same thing for AArch64: ZPAQL::assemble()
	and Predictor::assemble_p() writing A64 code, with the results of the
	interpreter (run0, predict0, update0), which are the reference.

	Included by zpaq-std.cpp inside namespace libzpaq, in place of the x86
	functions, when ZS_JIT_A64 is defined. Not a stand-alone file.

	The code written here
	  ZPAQL::assemble      int run(void)                at rcode[0]
	  Predictor::assemble_p  void update(Predictor*, int y) at pcode[0]
	                         int predict(Predictor*)        at pcode[8]
	Each of the three starts with "bti c": it does nothing, but a system
	that checks where an indirect call lands wants it there.
	Both return the bytes written, or the bytes they would have written when
	the buffer is too short (the caller asks for more and calls again).

	Registers of run(): every one of them callee-saved, so that the call to
	flush1() needs nothing saved
	  w19 a   w20 b   w21 c   w22 d   w23 f
	  x24 h   x25 m   x26 r   x27 this   x28 outbuf
	  w9..w12 scratch
	predict() and update() are leaf functions: nothing is saved
	  x0 the Predictor   w1 y   w2 c8   w3 hmap4   x4..x7 tables   w8 y*32767
	  w1 (predict), w2 w4 (update), w9..w16 scratch;  x17 far offsets
*/

namespace zsa64 {

enum {EQ=0, NE=1, HS=2, LO=3, MI=4, PL=5, HI=8, LS=9, GE=10, LT=11, GT=12, LE=13};
enum {ZR=31, SP=31};

struct Asm {
  U8* code;   // where to
  int size;   // its bytes
  int o;      // the next byte: goes on counting past size
  Asm(U8* c, int n): code(c), size(n), o(0) {}

  void w(U32 x) {  // one instruction
    if (o+4<=size) {
      code[o]=U8(x); code[o+1]=U8(x>>8); code[o+2]=U8(x>>16); code[o+3]=U8(x>>24);
    }
    o+=4;
  }
  void at(int pos, U32 x) {  // write over one
    if (pos+4<=size) {
      code[pos]=U8(x); code[pos+1]=U8(x>>8); code[pos+2]=U8(x>>16); code[pos+3]=U8(x>>24);
    }
  }

  // a 32 bit value that is one run of ones, rotated: the N:immr:imms field, or -1
  static int logimm(U32 v) {
    if (v==0 || v==0xffffffffu) return -1;
    int k=0;
    for (U32 t=v; t; t&=t-1) ++k;
    const U32 run=(k==32) ? 0xffffffffu : ((U32(1)<<k)-1);
    for (int r=0; r<32; ++r) {
      const U32 rot=r ? ((run>>r)|(run<<(32-r))) : run;
      if (rot==v) return (r<<6)|(k-1);
    }
    return -1;
  }

  // moves
  void mov(int rd, int rm)  {if (rd!=rm) w(0x2a0003e0|rm<<16|rd);}   // mov wd, wm
  void movx(int rd, int rm) {if (rd!=rm) w(0xaa0003e0|rm<<16|rd);}   // mov xd, xm
  void mvn(int rd, int rm)  {w(0x2a2003e0|rm<<16|rd);}               // mvn wd, wm
  void movi(int rd, U32 v) {                                         // mov wd, #v
    const int l=logimm(v);
    if (v<65536) w(0x52800000|v<<5|rd);
    else if ((v&0xffff)==0) w(0x52a00000|(v>>16)<<5|rd);
    else if ((~v)<65536) w(0x12800000|(~v)<<5|rd);
    else if (l>=0) w(0x320003e0|l<<10|rd);                           // orr wd, wzr, #v
    else w(0x52800000|(v&0xffff)<<5|rd), w(0x72a00000|(v>>16)<<5|rd);
  }
  void movi64(int rd, U64 v) {                                       // mov xd, #v
    bool first=true;
    for (int i=0; i<4; ++i) {
      const U32 c=U32(v>>(16*i))&0xffff;
      if (c==0 && !(i==3 && first)) continue;
      w((first ? 0xd2800000u : 0xf2800000u)|U32(i)<<21|c<<5|rd);
      first=false;
    }
  }

  // arithmetic, 32 bits (imm 0..4095)
  void addi(int rd, int rn, int imm) {w(0x11000000|imm<<10|rn<<5|rd);}
  void subi(int rd, int rn, int imm) {w(0x51000000|imm<<10|rn<<5|rd);}
  void addi4096(int rd, int rn)      {w(0x11400400|rn<<5|rd);}       // add wd, wn, #1, lsl #12
  void cmpi(int rn, int imm)         {w(0x7100001f|imm<<10|rn<<5);}
  void add(int rd, int rn, int rm)   {w(0x0b000000|rm<<16|rn<<5|rd);}
  void sub(int rd, int rn, int rm)   {w(0x4b000000|rm<<16|rn<<5|rd);}
  void cmp(int rn, int rm)           {w(0x6b00001f|rm<<16|rn<<5);}
  void add_lsl(int rd, int rn, int rm, int s) {w(0x0b000000|rm<<16|s<<10|rn<<5|rd);}
  void add_lsr(int rd, int rn, int rm, int s) {w(0x0b400000|rm<<16|s<<10|rn<<5|rd);}
  void add_asr(int rd, int rn, int rm, int s) {w(0x0b800000|rm<<16|s<<10|rn<<5|rd);}
  void sub_lsr(int rd, int rn, int rm, int s) {w(0x4b400000|rm<<16|s<<10|rn<<5|rd);}
  void mul(int rd, int rn, int rm)   {w(0x1b007c00|rm<<16|rn<<5|rd);}
  void madd(int rd, int rn, int rm, int ra) {w(0x1b000000|rm<<16|ra<<10|rn<<5|rd);}
  void msub(int rd, int rn, int rm, int ra) {w(0x1b008000|rm<<16|ra<<10|rn<<5|rd);}
  void udiv(int rd, int rn, int rm)  {w(0x1ac00800|rm<<16|rn<<5|rd);}
  void lslv(int rd, int rn, int rm)  {w(0x1ac02000|rm<<16|rn<<5|rd);}
  void lsrv(int rd, int rn, int rm)  {w(0x1ac02400|rm<<16|rn<<5|rd);}
  void and_(int rd, int rn, int rm)  {w(0x0a000000|rm<<16|rn<<5|rd);}
  void bic(int rd, int rn, int rm)   {w(0x0a200000|rm<<16|rn<<5|rd);}
  void orr(int rd, int rn, int rm)   {w(0x2a000000|rm<<16|rn<<5|rd);}
  void eor(int rd, int rn, int rm)   {w(0x4a000000|rm<<16|rn<<5|rd);}
  void lsl(int rd, int rn, int s) {                                  // s 0..31
    if (s==0) mov(rd, rn); else w(0x53000000|((32-s)&31)<<16|(31-s)<<10|rn<<5|rd);}
  void lsr(int rd, int rn, int s) {
    if (s==0) mov(rd, rn); else w(0x53007c00|s<<16|rn<<5|rd);}
  void asr(int rd, int rn, int s) {
    if (s==0) mov(rd, rn); else w(0x13007c00|s<<16|rn<<5|rd);}
  // and/eor with a constant; tmp is used when the constant has no encoding
  void andi(int rd, int rn, U32 v, int tmp) {
    const int l=logimm(v);
    if (v==0) w(0x52800000|rd);
    else if (v==0xffffffffu) mov(rd, rn);
    else if (l>=0) w(0x12000000|l<<10|rn<<5|rd);
    else movi(tmp, v), and_(rd, rn, tmp);
  }
  void eori(int rd, int rn, U32 v) {w(0x52000000|logimm(v)<<10|rn<<5|rd);}  // v: one run
  // wd = wn & (2^bits - 1): an index into a table of 2^bits elements
  void mask(int rd, int rn, int bits) {
    if (bits<=0) w(0x52800000|rd);
    else if (bits>=32) mov(rd, rn);
    else w(0x12000000|(bits-1)<<10|rn<<5|rd);
  }

  // conditional
  void csel(int rd, int rn, int rm, int c)  {w(0x1a800000|rm<<16|c<<12|rn<<5|rd);}
  void cset(int rd, int c)                  {w(0x1a9f07e0|(c^1)<<12|rd);}
  void cinc(int rd, int rn, int c)          {w(0x1a800400|rn<<16|(c^1)<<12|rn<<5|rd);}
  void cneg(int rd, int rn, int c)          {w(0x5a800400|rn<<16|(c^1)<<12|rn<<5|rd);}
  void ccmp(int rn, int rm, int nzcv, int c){w(0x7a400000|rm<<16|c<<12|rn<<5|nzcv);}

  // memory. Offsets from a base: within range and aligned, or through x17
  void ldrw(int rt, int rn, long off) {   // ldr wt, [xn, #off]
    if (off>=0 && off<=16380 && off%4==0) w(0xb9400000|U32(off/4)<<10|rn<<5|rt);
    else movi64(17, U64(off)), w(0xb8606800|17<<16|rn<<5|rt);
  }
  void strw(int rt, int rn, long off) {
    if (off>=0 && off<=16380 && off%4==0) w(0xb9000000|U32(off/4)<<10|rn<<5|rt);
    else movi64(17, U64(off)), w(0xb8206800|17<<16|rn<<5|rt);
  }
  void ldrx(int rt, int rn, long off) {   // ldr xt, [xn, #off]
    if (off>=0 && off<=32760 && off%8==0) w(0xf9400000|U32(off/8)<<10|rn<<5|rt);
    else movi64(17, U64(off)), w(0xf8606800|17<<16|rn<<5|rt);
  }
  void strx(int rt, int rn, long off) {
    if (off>=0 && off<=32760 && off%8==0) w(0xf9000000|U32(off/8)<<10|rn<<5|rt);
    else movi64(17, U64(off)), w(0xf8206800|17<<16|rn<<5|rt);
  }
  void ldrb_r(int rt, int rn, int rm)  {w(0x38606800|rm<<16|rn<<5|rt);}  // ldrb wt, [xn, xm]
  void strb_r(int rt, int rn, int rm)  {w(0x38206800|rm<<16|rn<<5|rt);}
  void ldrh_r(int rt, int rn, int rm)  {w(0x78607800|rm<<16|rn<<5|rt);}  // [xn, xm, lsl #1]
  void strh_r(int rt, int rn, int rm)  {w(0x78207800|rm<<16|rn<<5|rt);}
  void ldrsh_r(int rt, int rn, int rm) {w(0x78e07800|rm<<16|rn<<5|rt);}  // sign extended
  void ldrw_r(int rt, int rn, int rm)  {w(0xb8607800|rm<<16|rn<<5|rt);}  // [xn, xm, lsl #2]
  void strw_r(int rt, int rn, int rm)  {w(0xb8207800|rm<<16|rn<<5|rt);}
  void ldpw(int r1, int r2, int rn)    {w(0x29400000|r2<<10|rn<<5|r1);}  // ldp w1, w2, [xn]
  void stpw(int r1, int r2, int rn)    {w(0x29000000|r2<<10|rn<<5|r1);}
  // xd = xn + off (off 0 .. 2^24-1)
  void addx_i(int rd, int rn, long off) {
    const U32 lo=U32(off)&0xfff, hi=(U32(off)>>12)&0xfff;
    if (hi) w(0x91400000|hi<<10|rn<<5|rd), rn=rd;
    if (lo || !hi) w(0x91000000|lo<<10|rn<<5|rd);
  }
  void addx_lsl(int rd, int rn, int rm, int s) {w(0x8b000000|rm<<16|s<<10|rn<<5|rd);}

  // branches. The ones forward are written as a hole and patched by here()
  void b_to(int target)            {w(0x14000000|(U32((target-o)>>2)&0x3ffffff));}
  int  b_hole()                    {const int p=o; w(0x14000000); return p;}
  int  bc_hole(int c)              {const int p=o; w(0x54000000|c); return p;}
  int  cbz_hole(int rt)            {const int p=o; w(0x34000000|rt); return p;}
  int  cbnz_hole(int rt)           {const int p=o; w(0x35000000|rt); return p;}
  int  cbzx_hole(int rt)           {const int p=o; w(0xb4000000|rt); return p;}
  int  cbnzx_hole(int rt)          {const int p=o; w(0xb5000000|rt); return p;}
  void bc_to(int c, int target)    {w(0x54000000|(U32((target-o)>>2)&0x7ffff)<<5|c);}
  // the hole at pos jumps to target (default: here)
  void patch(int pos, int target) {
    if (pos+4>size) return;
    U32 x=code[pos]|code[pos+1]<<8|code[pos+2]<<16|U32(code[pos+3])<<24;
    const U32 d=U32((target-pos)>>2);
    if ((x&0x7c000000)==0x14000000) x|=d&0x3ffffff;   // b, bl
    else x|=(d&0x7ffff)<<5;                           // b.cond, cbz, cbnz
    at(pos, x);
  }
  void here(int pos) {patch(pos, o);}
};

static int log2size(size_t n) {  // n is a power of 2
  int b=0;
  while ((size_t(1)<<b)<n && b<63) ++b;
  return b;
}

}  // namespace zsa64

//////////////////////// ZPAQL::assemble(), AArch64 ////////////////////

// Called by out
static int flush1(ZPAQL* z) {
  try {
    z->flush();
    return 0;
  }
  catch(std::bad_alloc& x) {
    return 2;
  }
  catch(...) {
    return 3;
  }
}
// return true if op is an undefined ZPAQL instruction
static bool iserr(int op) {
  return op==0 || (op>=120 && op<=127) || (op>=240 && op<=254)
    || op==58 || (op<64 && (op%8==5 || op%8==6));
}
// Return length of ZPAQL instruction at hcomp[0]. Assume 0 padding at end.
// A run of identical ++ or -- is counted as 1 instruction.
static int oplen(const U8* hcomp) {
  if (*hcomp==255) return 3;
  if (*hcomp%8==7) return 2;
  if (*hcomp<51 && (*hcomp%8-1)/2==0) {  // ++ or -- opcode
    int i;
    for (i=1; i<127 && hcomp[i]==hcomp[0]; ++i);
    return i;
  }
  return 1;
}

// The ZPAQL code in hcomp[0..hlen-1] to A64 code in rcode[0..rcode_size-1].
// The code is int run(): 0 if all went well, 1 for an invalid instruction
// or a jump out of the program, 2 if OUT ran out of memory, 3 for any
// other error of OUT.
int ZPAQL::assemble() {
  using namespace zsa64;
  const U8* hcomp=&header[hbegin];
  const int hlen=(hend-hbegin)+2;
  const int mbits=log2size(m.size());
  const int hbits=log2size(h.size());
  enum {A=19, B=20, C=21, D=22, F=23, H=24, M=25, R=26, THIS=27, OUTBUF=28};
  Asm s(rcode, rcode_size);
#define zoff(x) long((char*)&(x)-(char*)this)

  // run(): save the registers, load the machine
  s.w(0xd503245f);                    // bti c
  s.w(0xa9ba7bfd);                    // stp x29, x30, [sp, #-96]!
  s.w(0x910003fd);                    // mov x29, sp
  s.w(0xa90153f3);                    // stp x19, x20, [sp, #16]
  s.w(0xa9025bf5);                    // stp x21, x22, [sp, #32]
  s.w(0xa90363f7);                    // stp x23, x24, [sp, #48]
  s.w(0xa9046bf9);                    // stp x25, x26, [sp, #64]
  s.w(0xa90573fb);                    // stp x27, x28, [sp, #80]
  s.movi64(THIS, U64(size_t(this)));
  s.movi64(H, U64(size_t(&h[0])));
  s.movi64(M, U64(size_t(&m[0])));
  s.movi64(R, U64(size_t(&r[0])));
  s.movi64(OUTBUF, U64(size_t(&outbuf[0])));
  s.ldrw(A, THIS, zoff(a));
  s.ldrw(B, THIS, zoff(b));
  s.ldrw(C, THIS, zoff(c));
  s.ldrw(D, THIS, zoff(d));
  s.ldrw(F, THIS, zoff(f));
  const int tostart=s.b_hole();       // b start

  // halt: w0 is what run() returns. Save the machine, restore, return
  const int halt=s.o;
  s.strw(A, THIS, zoff(a));
  s.strw(B, THIS, zoff(b));
  s.strw(C, THIS, zoff(c));
  s.strw(D, THIS, zoff(d));
  s.strw(F, THIS, zoff(f));
  s.w(0xa94153f3);                    // ldp x19, x20, [sp, #16]
  s.w(0xa9425bf5);                    // ldp x21, x22, [sp, #32]
  s.w(0xa94363f7);                    // ldp x23, x24, [sp, #48]
  s.w(0xa9446bf9);                    // ldp x25, x26, [sp, #64]
  s.w(0xa94573fb);                    // ldp x27, x28, [sp, #80]
  s.w(0xa8c67bfd);                    // ldp x29, x30, [sp], #96
  s.w(0xd65f03c0);                    // ret

  // out: outbuf[bufptr++]=a; when full, flush1(this). w0 = 0 or the error
  const int outlabel=s.o;
  s.ldrw(9, THIS, zoff(bufptr));
  s.strb_r(A, OUTBUF, 9);             // strb w19, [x28, x9]
  s.addi(9, 9, 1);
  s.strw(9, THIS, zoff(bufptr));
  s.movi(10, U32(outbuf.size()));
  s.cmp(9, 10);
  const int full=s.bc_hole(EQ);
  s.movi(0, 0);
  s.w(0xd65f03c0);                    // ret
  s.here(full);
  s.w(0xa9bf7bfd);                    // stp x29, x30, [sp, #-16]!
  s.movx(0, THIS);
  s.movi64(16, U64(size_t(&flush1)));
  s.w(0xd63f0200);                    // blr x16
  s.w(0xa8c17bfd);                    // ldp x29, x30, [sp], #16
  s.w(0xd65f03c0);                    // ret

  // it[i]: bit 0 = the instruction at i is reached from the one before,
  // bit 1 = by a jump
  Array<int> it(hlen);
  Array<int> loc(hlen);     // where its code is, 0 = not written yet
  Array<U8> fuse(hlen);     // a jt/jf that reads the flags of the comparison before: 1 ==, 2 <, 3 >
  Array<U8> nosave(hlen);   // a comparison whose result need not go to f
  int done=0;
  it[0]=2;
  do {
    done=0;
    const int NONE=0x80000000;
    for (int i=0; i<hlen; ++i) {
      int op=hcomp[i];
      if (it[i]) {
        int next1=i+oplen(hcomp+i), next2=NONE; // next and jump targets
        if (iserr(op)) next1=NONE;  // error
        if (op==56) next1=NONE, next2=0;  // halt
        if (op==255) next1=NONE, next2=hcomp[i+1]+256*hcomp[i+2]; // lj
        if (op==39||op==47||op==63)next2=i+2+(hcomp[i+1]<<24>>24);// jt,jf,jmp
        if (op==63) next1=NONE;  // jmp
        if ((next2<0 || next2>=hlen) && next2!=NONE) next2=hlen-1; // error
        if (next1>=0 && next1<hlen && !(it[next1]&1)) it[next1]|=1, ++done;
        if (next2>=0 && next2<hlen && !(it[next2]&2)) it[next2]|=2, ++done;
      }
    }
  } while (done>0);
  // A comparison followed directly by a jt/jf that nothing else jumps to:
  // the jump reads the flags. And when both ways after the jump come to
  // another comparison (or an error) before another jt/jf, the comparison
  // does not write f either. The rule of the x86 code, and one more: no
  // other instruction runs into that jt/jf. It happens when a jump lands
  // in the middle of an instruction and the two readings of the bytes
  // meet again at the jt/jf: coming from the other one the flags are not
  // those of this comparison (the x86 code jumps on them all the same)
  Array<U8> into(hlen);     // how many instructions run into this one
  for (int i=0; i<hlen; ++i) {
    const int op=hcomp[i];
    if (!it[i] || iserr(op) || op==56 || op==63 || op==255) continue;
    const int next=i+oplen(hcomp+i);
    if (next<hlen && into[next]<2) ++into[next];
  }
  for (int i=0; i<hlen; ++i) {
    const int op1=hcomp[i]; // 216..239 = comparison
    const int i2=i+1+(op1%8==7);  // address of next instruction
    const int op2=hcomp[i2];  // 39,47 = jt,jf
    if (it[i] && op1>=216 && op1<240 && (op2==39 || op2==47)
        && it[i2]==1 && into[i2]==1 && (i2==i+1 || it[i+1]==0)) {
      int code=(op1-208)/8; // 1,2,3 is ==,<,>
      fuse[i2]=code;
      for (int j=0; j<2 && code; ++j) {  // trace each path from i2
        int k=i2+2; // branch not taken
        if (j==1) k=i2+2+(hcomp[i2+1]<<24>>24);  // branch taken
        for (int l=0; l<hlen && code; ++l) {  // trace at most hlen steps
          if (k<0 || k>=hlen) break;  // out of bounds, pass
          const int op=hcomp[k];
          if (op==39 || op==47) code=0;  // jt,jf, fail
          else if (op>=216 && op<240) break;  // ==,<,>, pass
          else if (iserr(op)) break;  // error, pass
          else if (op==255) k=hcomp[k+1]+256*hcomp[k+2]; // lj
          else if (op==63) k=k+2+(hcomp[k+1]<<24>>24);  // jmp
          else if (op==56) k=0;  // halt
          else k=k+1+(op%8==7);  // ordinary instruction
        }
      }
      nosave[i]=code!=0;
    }
  }

  s.here(tostart);

  // Every chain of instructions, from each start not yet written
  for (int istart=0; istart<hlen; ++istart) {
    int inc=0;
    for (int i=istart; i<hlen && it[i]; i+=inc) {
      inc=oplen(hcomp+i);
      if (loc[i]) {  // written already: go there
        if (i>istart) s.b_to(loc[i]);
        break;
      }
      loc[i]=s.o;
      // oplen() counts a run of the same swap (ddd<>a) as one instruction too,
      // as it does with ++ and --: inc of them. An even number of swaps
      // does nothing, an odd number is one swap (the x86 code always
      // writes one)
      const int op=hcomp[i];
      const int arg=hcomp[i+1]+((op==255)?256*hcomp[i+2]:0);
      const int ddd=op/8%8;
      const int sss=op%8;
      if (iserr(op)) {
        s.movi(0, 1);
        s.b_to(halt);
        continue;
      }
      // The source of 01dddsss and 1xxxxsss in a register: its number.
      // *b, *c, *d and n are loaded into w9
      int src=A+sss;
      if (op>=64 && op<240) {
        if (sss==4 || sss==5) {
          s.mask(9, B+sss-4, mbits);
          s.ldrb_r(9, M, 9);
          src=9;
        }
        else if (sss==6) {
          s.mask(9, D, hbits);
          s.ldrw_r(9, H, 9);
          src=9;
        }
        else if (sss==7) {
          // n: in w9, unless the instruction takes it as it is
          const int g=op/8;
          const bool direct=g==16 || g==17 || (g>=25 && g<=29)
            || (g==21 && (arg==0 || Asm::logimm(arg)>=0));
          if (!direct) s.movi(9, arg);
          src=9;
        }
      }
      // The index of a destination *b, *c, *d into w10
      const bool dmem=(op>=32 && op<56 && sss<5) || (op>=96 && op<120) || op==60;
      if (dmem) {
        if (ddd==6 || op==60) s.mask(10, D, hbits);
        else s.mask(10, B+ddd-4, mbits);
      }
      switch((op/8)&31) {
        case 0:  // ddd = a
        case 1:  // ddd = b
        case 2:  // ddd = c
        case 3:  // ddd = d
          switch(sss) {
            case 0:  // ddd<>a (swap)
              if (inc&1) s.mov(9, A+ddd), s.mov(A+ddd, A), s.mov(A, 9);
              break;
            case 1:  // ddd++
              s.addi(A+ddd, A+ddd, inc);
              break;
            case 2:  // ddd--
              s.subi(A+ddd, A+ddd, inc);
              break;
            case 3:  // ddd!
              s.mvn(A+ddd, A+ddd);
              break;
            case 4:  // ddd=0
              s.movi(A+ddd, 0);
              break;
            case 7:  // ddd=r n
              s.ldrw(A+ddd, R, arg*4);
              break;
          }
          break;
        case 4:  // ddd = *b
        case 5:  // ddd = *c
          switch(sss) {
            case 0:  // ddd<>a (swap): the high bits of a stay
              if (inc&1) {
                s.ldrb_r(9, M, 10);
                s.strb_r(A, M, 10);
                s.andi(A, A, 0xffffff00u, 11);
                s.orr(A, A, 9);
              }
              break;
            case 1:  // ddd++
              s.ldrb_r(9, M, 10), s.addi(9, 9, inc), s.strb_r(9, M, 10);
              break;
            case 2:  // ddd--
              s.ldrb_r(9, M, 10), s.subi(9, 9, inc), s.strb_r(9, M, 10);
              break;
            case 3:  // ddd!
              s.ldrb_r(9, M, 10), s.mvn(9, 9), s.strb_r(9, M, 10);
              break;
            case 4:  // ddd=0
              s.strb_r(ZR, M, 10);
              break;
            case 7: { // jt, jf: two instructions, filled in at the end
              s.w(0xd503201f);        // nop
              s.w(0xd503201f);        // nop
              break;
            }
          }
          break;
        case 6:  // ddd = *d
          switch(sss) {
            case 0:  // ddd<>a (swap)
              if (inc&1) s.ldrw_r(9, H, 10), s.strw_r(A, H, 10), s.mov(A, 9);
              break;
            case 1:  // ddd++
              s.ldrw_r(9, H, 10), s.addi(9, 9, inc), s.strw_r(9, H, 10);
              break;
            case 2:  // ddd--
              s.ldrw_r(9, H, 10), s.subi(9, 9, inc), s.strw_r(9, H, 10);
              break;
            case 3:  // ddd!
              s.ldrw_r(9, H, 10), s.mvn(9, 9), s.strw_r(9, H, 10);
              break;
            case 4:  // ddd=0
              s.strw_r(ZR, H, 10);
              break;
            case 7:  // r=a n
              s.strw(A, R, arg*4);
              break;
          }
          break;
        case 7:  // special
          switch(op) {
            case 56: // halt
              s.movi(0, 0);
              s.b_to(halt);
              break;
            case 57: { // out
              s.w(0x94000000|(U32((outlabel-s.o)>>2)&0x3ffffff));  // bl out
              const int ok=s.cbz_hole(0);
              s.b_to(halt);           // w0 is the error
              s.here(ok);
              break;
            }
            case 59:  // hash: a = (a + *b + 512) * 773
              s.mask(9, B, mbits);
              s.ldrb_r(9, M, 9);
              s.add(A, A, 9);
              s.addi(A, A, 512);
              s.movi(9, 773);
              s.mul(A, A, 9);
              break;
            case 60:  // hashd: *d = (*d + a + 512) * 773
              s.ldrw_r(9, H, 10);
              s.add(9, 9, A);
              s.addi(9, 9, 512);
              s.movi(11, 773);
              s.mul(9, 9, 11);
              s.strw_r(9, H, 10);
              break;
            case 63:  // jmp
              s.w(0xd503201f);        // nop, filled in at the end
              break;
          }
          break;
        case 8:   // a=
        case 9:   // b=
        case 10:  // c=
        case 11:  // d=
          s.mov(A+ddd, src);
          break;
        case 12:  // *b=
        case 13:  // *c=
          s.strb_r(src, M, 10);
          break;
        case 14:  // *d=
          s.strw_r(src, H, 10);
          break;
        case 15: break; // not used
        case 16:  // a+=
          if (sss==7) s.addi(A, A, arg); else s.add(A, A, src);
          break;
        case 17:  // a-=
          if (sss==7) s.subi(A, A, arg); else s.sub(A, A, src);
          break;
        case 18:  // a*=
          s.mul(A, A, src);
          break;
        case 19:  // a/=   (udiv gives 0 when the divisor is 0: what ZPAQL wants)
          s.udiv(A, A, src);
          break;
        case 20:  // a%=   (0 when the divisor is 0)
          if (sss==0) s.movi(A, 0);
          else {
            s.udiv(10, A, src);
            s.msub(A, 10, src, A);
            s.cmpi(src, 0);
            s.csel(A, A, ZR, NE);
          }
          break;
        case 21:  // a&=
          if (sss==7) s.andi(A, A, arg, 9); else s.and_(A, A, src);
          break;
        case 22:  // a&~
          s.bic(A, A, src);
          break;
        case 23:  // a|=
          s.orr(A, A, src);
          break;
        case 24:  // a^=
          s.eor(A, A, src);
          break;
        case 25:  // a<<=
          if (sss==7) s.lsl(A, A, arg&31); else s.lslv(A, A, src);
          break;
        case 26:  // a>>=
          if (sss==7) s.lsr(A, A, arg&31); else s.lsrv(A, A, src);
          break;
        case 27:  // a==
        case 28:  // a<
        case 29:  // a>
          if (sss==7) s.cmpi(A, arg); else s.cmp(A, src);
          if (!nosave[i]) s.cset(F, op/8==27 ? EQ : op/8==28 ? LO : HI);
          break;
        case 30:  // not used
        case 31:  // 255 = lj
          if (op==255) s.w(0xd503201f);  // nop, filled in at the end
          break;
      }
    }
  }
  const int rsize=s.o;
  if (rsize>rcode_size) return rsize;

  // The jumps, now that every instruction has its place
  for (int i=0; i<hlen; ++i) {
    if (!loc[i]) continue;
    const int op=hcomp[i];
    if (op==39 || op==47 || op==63 || op==255) {  // jt, jf, jmp, lj
      int target=hcomp[i+1];
      if (op==255) target+=hcomp[i+2]*256;  // lj
      else {
        if (target>=128) target-=256;
        target+=i+2;
      }
      if (target<0 || target>=hlen) target=hlen-1;  // runtime ZPAQL error
      const int to=loc[target];
      if (!to) error("JIT: jump to an instruction with no code");
      s.o=loc[i];
      if (op==63 || op==255) s.b_to(to);
      else {
        // the condition that jumps: jt, or the opposite for jf
        static const int ccode[4]={NE, EQ, LO, HI};  // f!=0, ==, <, >
        const int k=fuse[i];
        const int d=(to-s.o)>>2;
        bool near=d>-(1<<18) && d<(1<<18);
#ifdef ZS_JITTEST
        if (getenv("ZS_JITFAR")) near=false;  // the test of the far jump
#endif
        int c=ccode[k];
        if (op==47) c^=1;
        if (!near) c^=1;              // jump over the far jump
        const U32 off=near ? U32(d)&0x7ffff : 2;
        if (k) s.w(0x54000000|off<<5|c);                   // b.cond
        else s.w((c==NE ? 0x35000000u : 0x34000000u)|off<<5|F);  // cbnz/cbz w23
        if (!near) s.b_to(to);
      }
    }
  }
#undef zoff
  return rsize;
}

//////////////////////// Predictor::assemble_p(), AArch64 /////////////////////

// The model in z.header to code: update() at pcode[0], predict() at pcode[8].
// Every line of C++ in the comments is the one of predict0() and update0().
int Predictor::assemble_p() {
  using namespace zsa64;
  Predictor& pr=*this;
  Asm s(pr.pcode, pcode_size);
  U8* hcomp=&pr.z.header[0];
#define off(x)  long((char*)&(pr.x)-(char*)&pr)
#define offc(x) long((char*)&(pr.comp[i].x)-(char*)&pr)
  enum {PR=0, Y=1, C8=2, HMAP4=3, STRETCH=4, SQUASH=5, DT=6, NS=7, Y32767=8};
  const int n=hcomp[6];  // number of components
  if (n<1) error("JIT: no components");

  // what the model needs, to load only that
  bool need_stretch=false, need_squash=false, need_dt=false, need_dt2k=false,
       need_ns=false, need_c8=false, need_hmap4p=false, need_hmap4u=false;
  {
    U8* cp=hcomp+7;
    for (int i=0; i<n; ++i, cp+=compsize[cp[0]]) {
      if (cp-hcomp>=pr.z.cend) error("comp too big");
      if (cp[0]<1 || cp[0]>9) error("invalid component");
      switch (cp[0]) {
        case CM: need_stretch=need_dt=need_hmap4p=true; break;
        case ICM: need_stretch=need_ns=need_c8=need_hmap4p=need_hmap4u=true; break;
        case MATCH: need_stretch=need_dt2k=true; break;
        case MIX2: case MIX: need_squash=need_c8=true; break;
        case ISSE: need_squash=need_ns=need_c8=need_hmap4p=need_hmap4u=true; break;
        case SSE: need_stretch=need_dt=need_c8=true; break;
      }
    }
  }

  s.w(0xd503245f);                    // pcode[0]: bti c
  const int toupdate=s.b_hole();      //           b update

  ////////// predict(): x0 = the Predictor. Returns squash(p[n-1])
  s.w(0xd503245f);                    // pcode[8]: bti c
  if (need_c8) s.ldrw(C8, PR, off(c8));
  if (need_hmap4p) s.ldrw(HMAP4, PR, off(hmap4));
  if (need_stretch) s.addx_i(STRETCH, PR, off(stretcht));
  if (need_dt2k) s.addx_i(DT, PR, off(dt2k));  // in predict x6 is dt2k
  U8* cp=hcomp+7;
  for (int i=0; i<n; ++i, cp+=compsize[cp[0]]) {
    switch (cp[0]) {
      case CONS:  // c
        break;
      case CM:  // sizebits limit
        // cr.cxt=h[i]^hmap4;
        // p[i]=stretch(cr.cm(cr.cxt)>>17);
        s.ldrw(9, PR, off(h[i]));
        s.eor(9, 9, HMAP4);
        s.mask(9, 9, cp[1]);
        s.strx(9, PR, offc(cxt));
        s.ldrx(10, PR, offc(cm));
        s.ldrw_r(10, 10, 9);
        s.lsr(10, 10, 17);
        s.ldrsh_r(10, STRETCH, 10);
        s.strw(10, PR, off(p[i]));
        break;
      case ISSE:  // sizebits j -- c=hi, cxt=bh
        // if (c8==1 || (c8&0xf0)==16)
        //   cr.c=find(cr.ht, cp[1]+2, h[i]+16*c8);
        // cr.cxt=cr.ht[cr.c+(hmap4&15)];  // bit history
        // int *wt=(int*)&cr.cm[cr.cxt*2];
        // p[i]=clamp2k((wt[0]*p[cp[2]]+wt[1]*64)>>16);
      case ICM: { // sizebits
        // if (c8==1 || (c8&0xf0)==16) cr.c=find(cr.ht, cp[1]+2, h[i]+16*c8);
        // cr.cxt=cr.ht[cr.c+(hmap4&15)];
        // p[i]=stretch(cr.cm(cr.cxt)>>8);
        const int sizebits=cp[1]+2;
        const U32 rowmask=(cp[1]>=26) ? 0xfffffff0u : (U32(64)<<cp[1])-16;  // ht.size()-16
        s.ldrx(9, PR, offc(ht));
        s.cmpi(C8, 1);
        const int tofind1=s.bc_hole(EQ);
        s.lsr(10, C8, 4);
        s.cmpi(10, 1);
        const int tofind2=s.bc_hole(EQ);
        s.ldrx(12, PR, offc(c));      // the row of this nibble, found before
        const int torow=s.b_hole();
        s.here(tofind1);
        s.here(tofind2);
        // find(): the row of 16 of cxt in ht. Element 0 of a row is a check
        // byte; three rows are tried, and when none has it the one with
        // the lowest element 1 is emptied and taken
        //   int chk=cxt>>sizebits&255;
        //   size_t h0=(cxt*16)&(ht.size()-16);
        //   if (ht[h0]==chk) return h0;
        //   size_t h1=h0^16;
        //   if (ht[h1]==chk) return h1;
        //   size_t h2=h0^32;
        //   if (ht[h2]==chk) return h2;
        //   if (ht[h0+1]<=ht[h1+1] && ht[h0+1]<=ht[h2+1])
        //     return memset(&ht[h0], 0, 16), ht[h0]=chk, h0;
        //   else if (ht[h1+1]<ht[h2+1])
        //     return memset(&ht[h1], 0, 16), ht[h1]=chk, h1;
        //   else
        //     return memset(&ht[h2], 0, 16), ht[h2]=chk, h2;
        s.ldrw(10, PR, off(h[i]));
        s.add_lsl(10, 10, C8, 4);     // cxt = h[i]+16*c8
        s.lsr(11, 10, sizebits&31);
        s.andi(11, 11, 255, 13);      // chk
        s.lsl(12, 10, 4);
        s.andi(12, 12, rowmask, 13);  // h0
        s.ldrb_r(13, 9, 12);
        s.cmp(13, 11);
        const int found0=s.bc_hole(EQ);
        s.eori(12, 12, 16);           // h1
        s.ldrb_r(13, 9, 12);
        s.cmp(13, 11);
        const int found1=s.bc_hole(EQ);
        s.eori(12, 12, 48);           // h2
        s.ldrb_r(13, 9, 12);
        s.cmp(13, 11);
        const int found2=s.bc_hole(EQ);
        s.eori(14, 12, 32);           // h0
        s.eori(15, 12, 48);           // h1
        s.addx_i(16, 9, 1);           // &ht[1]
        s.ldrb_r(1, 16, 14);          // ht[h0+1]
        s.ldrb_r(13, 16, 15);         // ht[h1+1]
        s.ldrb_r(16, 16, 12);         // ht[h2+1]
        s.cmp(13, 16);
        s.csel(12, 15, 12, LO);       // h1 if ht[h1+1]<ht[h2+1] else h2
        s.cmp(1, 13);
        s.ccmp(1, 16, 2, LS);         // ht[h0+1]<=ht[h1+1] && ht[h0+1]<=ht[h2+1]
        s.csel(12, 14, 12, LS);       // then h0
        s.addx_lsl(16, 9, 12, 0);     // &ht[row]
        s.w(0xa9007e1f);              // stp xzr, xzr, [x16]
        s.w(0x3900020b);              // strb w11, [x16]
        s.here(found0);
        s.here(found1);
        s.here(found2);
        s.strx(12, PR, offc(c));
        s.here(torow);
        s.andi(13, HMAP4, 15, 14);
        s.addx_lsl(12, 12, 13, 0);    // c+(hmap4&15)
        s.ldrb_r(13, 9, 12);          // the bit history
        s.strx(13, PR, offc(cxt));
        s.ldrx(9, PR, offc(cm));
        if (cp[0]==ICM) {
          s.ldrw_r(10, 9, 13);
          s.lsr(10, 10, 8);
          s.ldrsh_r(10, STRETCH, 10);
        }
        else {  // ISSE
          s.addx_lsl(9, 9, 13, 3);    // wt
          s.ldpw(10, 11, 9);          // wt[0], wt[1]
          s.ldrw(14, PR, off(p[cp[2]]));
          s.mul(10, 10, 14);
          s.add_lsl(10, 10, 11, 6);
          s.asr(10, 10, 16);
          s.movi(11, 2047);
          s.cmp(10, 11);
          s.csel(10, 10, 11, LE);
          s.movi(11, U32(-2048));
          s.cmp(10, 11);
          s.csel(10, 10, 11, GE);
        }
        s.strw(10, PR, off(p[i]));
        break;
      }
      case MATCH: { // sizebits bufbits: a=len, b=offset, c=bit, cxt=bitpos,
                    //                   ht=buf, limit=pos
        // if (cr.a==0) p[i]=0;
        // else {
        //   cr.c=(cr.ht(cr.limit-cr.b)>>(7-cr.cxt))&1; // predicted bit
        //   p[i]=stretch(dt2k[cr.a]*(cr.c*-2+1)&32767);
        // }
        s.ldrx(10, PR, offc(a));
        s.movi(11, 0);
        const int nomatch=s.cbzx_hole(10);
        s.ldrx(12, PR, offc(limit));
        s.ldrx(13, PR, offc(b));
        s.sub(12, 12, 13);
        s.mask(12, 12, cp[2]);
        s.ldrx(9, PR, offc(ht));
        s.ldrb_r(12, 9, 12);
        s.ldrx(13, PR, offc(cxt));
        s.movi(14, 7);
        s.sub(14, 14, 13);
        s.lsrv(12, 12, 14);
        s.andi(12, 12, 1, 14);
        s.strx(12, PR, offc(c));
        s.ldrw_r(11, DT, 10);         // dt2k[a]
        s.cmpi(12, 0);
        s.cneg(11, 11, NE);
        s.andi(11, 11, 32767, 14);
        s.ldrsh_r(11, STRETCH, 11);
        s.here(nomatch);
        s.strw(11, PR, off(p[i]));
        break;
      }
      case AVG: // j k wt
        // p[i]=(p[cp[1]]*cp[3]+p[cp[2]]*(256-cp[3]))>>8;
        s.ldrw(9, PR, off(p[cp[1]]));
        s.ldrw(10, PR, off(p[cp[2]]));
        s.movi(11, cp[3]);
        s.mul(9, 9, 11);
        s.movi(11, 256-cp[3]);
        s.madd(9, 10, 11, 9);
        s.asr(9, 9, 8);
        s.strw(9, PR, off(p[i]));
        break;
      case MIX2:   // sizebits j k rate mask
                   // c=size cm=wt[size] cxt=input
        // cr.cxt=((h[i]+(c8&cp[5]))&(cr.c-1));
        // int w=cr.a16[cr.cxt];
        // p[i]=(w*p[cp[2]]+(65536-w)*p[cp[3]])>>16;
        s.andi(9, C8, cp[5], 10);
        s.ldrw(10, PR, off(h[i]));
        s.add(9, 9, 10);
        s.mask(9, 9, cp[1]);
        s.strx(9, PR, offc(cxt));
        s.ldrx(10, PR, offc(a16));
        s.ldrh_r(10, 10, 9);          // w
        s.ldrw(11, PR, off(p[cp[2]]));
        s.ldrw(12, PR, off(p[cp[3]]));
        s.mul(11, 10, 11);
        s.movi(13, 65536);
        s.sub(13, 13, 10);
        s.madd(11, 13, 12, 11);
        s.asr(11, 11, 16);
        s.strw(11, PR, off(p[i]));
        break;
      case MIX: {  // sizebits j m rate mask
                   // c=size cm=wt[size][m] cxt=index of wt in cm
        // int m=cp[3];
        // cr.cxt=h[i]+(c8&cp[5]);
        // cr.cxt=(cr.cxt&(cr.c-1))*m; // pointer to row of weights
        // int* wt=(int*)&cr.cm[cr.cxt];
        // p[i]=0;
        // for (int j=0; j<m; ++j)
        //   p[i]+=(wt[j]>>8)*p[cp[2]+j];
        // p[i]=clamp2k(p[i]>>8);
        const int m=cp[3];
        s.andi(9, C8, cp[5], 10);
        s.ldrw(10, PR, off(h[i]));
        s.add(9, 9, 10);
        s.mask(9, 9, cp[1]);
        s.movi(10, m);
        s.w(0x9b0a7d29);              // mul x9, x9, x10
        s.strx(9, PR, offc(cxt));
        s.ldrx(10, PR, offc(cm));
        s.addx_lsl(10, 10, 9, 2);     // wt
        s.addx_i(11, PR, off(p[cp[2]]));
        int k=0;
        if (m>=4) {  // four at a time
          s.w(0x4f000400);            // movi v0.4s, #0
          for (; k+4<=m; k+=4) {
            s.w(0x3dc00141|U32(k/4)<<10);  // ldr q1, [x10, #k*4]
            s.w(0x3dc00162|U32(k/4)<<10);  // ldr q2, [x11, #k*4]
            s.w(0x4f380421);          // sshr v1.4s, v1.4s, #8
            s.w(0x4ea29420);          // mla v0.4s, v1.4s, v2.4s
          }
          s.w(0x4eb1b800);            // addv s0, v0.4s
          s.w(0x1e26000c);            // fmov w12, s0
        }
        else s.movi(12, 0);
        for (; k<m; ++k) {
          s.ldrw(13, 10, k*4);
          s.ldrw(14, 11, k*4);
          s.asr(13, 13, 8);
          s.madd(12, 13, 14, 12);
        }
        s.asr(12, 12, 8);
        s.movi(13, 2047);
        s.cmp(12, 13);
        s.csel(12, 12, 13, LE);
        s.movi(13, U32(-2048));
        s.cmp(12, 13);
        s.csel(12, 12, 13, GE);
        s.strw(12, PR, off(p[i]));
        break;
      }
      case SSE:  // sizebits j start limit
        // cr.cxt=(h[i]+c8)*32;
        // int pq=p[cp[2]]+992;
        // if (pq<0) pq=0;
        // if (pq>1983) pq=1983;
        // int wt=pq&63;
        // pq>>=6;
        // cr.cxt+=pq;
        // p[i]=stretch(((cr.cm(cr.cxt)>>10)*(64-wt)+(cr.cm(cr.cxt+1)>>10)*wt)>>13);
        // cr.cxt+=wt>>5;
        s.ldrw(9, PR, off(h[i]));
        s.add(9, 9, C8);
        s.mask(9, 9, cp[1]);
        s.lsl(9, 9, 5);
        s.ldrw(10, PR, off(p[cp[2]]));
        s.addi(10, 10, 992);
        s.cmpi(10, 0);
        s.csel(10, 10, ZR, GE);
        s.movi(11, 1983);
        s.cmp(10, 11);
        s.csel(10, 10, 11, LE);
        s.andi(11, 10, 63, 12);       // wt
        s.lsr(10, 10, 6);
        s.add(9, 9, 10);              // cxt
        s.ldrx(12, PR, offc(cm));
        s.addx_lsl(12, 12, 9, 2);
        s.ldpw(13, 14, 12);           // cm[cxt], cm[cxt+1]
        s.lsr(13, 13, 10);
        s.lsr(14, 14, 10);
        s.sub(14, 14, 13);            // p0*(64-wt)+p1*wt = (p1-p0)*wt+p0*64
        s.mul(14, 14, 11);
        s.add_lsl(14, 14, 13, 6);
        s.lsr(14, 14, 13);
        s.ldrsh_r(14, STRETCH, 14);
        s.strw(14, PR, off(p[i]));
        s.add_lsr(9, 9, 11, 5);
        s.strx(9, PR, offc(cxt));
        break;
      default:
        error("invalid ZPAQ component");
    }
  }
  // return squash(p[n-1])
  s.ldrw(9, PR, off(p[n-1]));
  s.addi(9, 9, 2048);
  s.addx_i(SQUASH, PR, off(squasht));
  s.ldrh_r(0, SQUASH, 9);
  s.w(0xd65f03c0);                    // ret

  ////////// update(): x0 = the Predictor, w1 = y
  s.here(toupdate);
  if (need_hmap4u) s.ldrw(HMAP4, PR, off(hmap4));
  if (need_squash) s.addx_i(SQUASH, PR, off(squasht));
  if (need_dt) s.addx_i(DT, PR, off(dt));
  if (need_ns) s.addx_i(NS, PR, off(st));
  s.lsl(Y32767, Y, 15);
  s.sub(Y32767, Y32767, Y);           // y*32767
  cp=hcomp+7;
  for (int i=0; i<n; ++i, cp+=compsize[cp[0]]) {
    switch (cp[0]) {
      case CONS:  // c
        break;
      case SSE:  // sizebits j start limit
      case CM:   // sizebits limit
        // train(cr, y):
        //   U32& pn=cr.cm(cr.cxt);
        //   U32 count=pn&0x3ff;
        //   int error=y*32767-(cr.cm(cr.cxt)>>17);
        //   pn+=(error*dt[count]&-1024)+(count<cr.limit);
        s.ldrx(9, PR, offc(cm));
        s.ldrx(10, PR, offc(cxt));
        s.mask(10, 10, cp[1]+5*(cp[0]==SSE));
        s.addx_lsl(9, 9, 10, 2);
        s.w(0xb940012b);              // ldr w11, [x9]
        s.andi(12, 11, 0x3ff, 13);    // count
        s.sub_lsr(13, Y32767, 11, 17);// error
        s.ldrw_r(14, DT, 12);
        s.mul(13, 13, 14);
        s.andi(13, 13, 0xfffffc00u, 14);
        s.add(11, 11, 13);
        s.cmpi(12, cp[2+2*(cp[0]==SSE)]*4);  // limit
        s.cinc(11, 11, LO);
        s.w(0xb900012b);              // str w11, [x9]
        break;
      case ICM:   // sizebits: cxt=bh, ht[c][0..15]=bh row
        // cr.ht[cr.c+(hmap4&15)]=st.next(cr.ht[cr.c+(hmap4&15)], y);
        // U32& pn=cr.cm(cr.cxt);
        // pn+=int(y*32767-(pn>>8))>>2;
      case ISSE:  // sizebits j  -- c=hi, cxt=bh
        // int err=y*32767-squash(p[i]);
        // int *wt=(int*)&cr.cm[cr.cxt*2];
        // wt[0]=clamp512k(wt[0]+((err*p[cp[2]]+(1<<12))>>13));
        // wt[1]=clamp512k(wt[1]+((err+16)>>5));
        // cr.ht[cr.c+(hmap4&15)]=st.next(cr.cxt, y);
        s.ldrx(9, PR, offc(ht));
        s.ldrx(10, PR, offc(c));
        s.andi(11, HMAP4, 15, 12);
        s.addx_lsl(10, 10, 11, 0);
        s.ldrb_r(12, 9, 10);          // bh
        s.add_lsl(13, Y, 12, 2);      // bh*4+y
        s.ldrb_r(13, NS, 13);         // the next bit history
        s.strb_r(13, 9, 10);
        s.ldrx(9, PR, offc(cm));
        if (cp[0]==ICM) {
          s.addx_lsl(9, 9, 12, 2);    // &cm[bh]
          s.w(0xb940012b);            // ldr w11, [x9]
          s.sub_lsr(13, Y32767, 11, 8);
          s.add_asr(11, 11, 13, 2);
          s.w(0xb900012b);            // str w11, [x9]
        }
        else {  // ISSE
          s.addx_lsl(9, 9, 12, 3);    // wt
          s.ldrw(10, PR, off(p[i]));
          s.addi(10, 10, 2048);
          s.ldrh_r(10, SQUASH, 10);
          s.sub(10, Y32767, 10);      // err
          s.ldpw(11, 13, 9);          // wt[0], wt[1]
          s.ldrw(14, PR, off(p[cp[2]]));
          s.mul(14, 14, 10);
          s.addi4096(14, 14);
          s.add_asr(11, 11, 14, 13);
          s.movi(15, (1<<19)-1);
          s.movi(16, U32(-(1<<19)));
          s.cmp(11, 15);
          s.csel(11, 11, 15, LE);
          s.cmp(11, 16);
          s.csel(11, 11, 16, GE);
          s.addi(14, 10, 16);
          s.add_asr(13, 13, 14, 5);
          s.cmp(13, 15);
          s.csel(13, 13, 15, LE);
          s.cmp(13, 16);
          s.csel(13, 13, 16, GE);
          s.stpw(11, 13, 9);
        }
        break;
      case MATCH: { // sizebits bufbits:
                    //   a=len, b=offset, c=bit, cm=index, cxt=bitpos
                    //   ht=buf, limit=pos
        // if (int(cr.c)!=y) cr.a=0;  // mismatch?
        // cr.ht(cr.limit)+=cr.ht(cr.limit)+y;
        // if (++cr.cxt==8) {
        //   cr.cxt=0;
        //   ++cr.limit;
        //   cr.limit&=(1<<cp[2])-1;
        //   if (cr.a==0) {  // look for a match
        //     cr.b=cr.limit-cr.cm(h[i]);
        //     if (cr.b&(cr.ht.size()-1))
        //       while (cr.a<255
        //              && cr.ht(cr.limit-cr.a-1)==cr.ht(cr.limit-cr.a-cr.b-1))
        //         ++cr.a;
        //   }
        //   else cr.a+=cr.a<255;
        //   cr.cm(h[i])=cr.limit;
        // }
        s.ldrx(9, PR, offc(ht));
        s.ldrx(10, PR, offc(cm));
        s.ldrx(11, PR, offc(c));
        s.cmp(11, Y);
        const int same=s.bc_hole(EQ);
        s.strx(ZR, PR, offc(a));
        s.here(same);
        s.ldrx(12, PR, offc(limit));
        s.ldrb_r(13, 9, 12);
        s.add_lsl(13, Y, 13, 1);
        s.strb_r(13, 9, 12);
        s.ldrx(13, PR, offc(cxt));
        s.addi(13, 13, 1);
        s.andi(13, 13, 7, 14);
        s.strx(13, PR, offc(cxt));
        const int notbyte=s.cbnz_hole(13);
        s.addi(12, 12, 1);
        s.mask(12, 12, cp[2]);
        s.strx(12, PR, offc(limit));
        s.ldrw(14, PR, off(h[i]));
        s.mask(14, 14, cp[1]);        // the index into cm
        s.ldrx(15, PR, offc(a));
        const int havematch=s.cbnzx_hole(15);
        s.ldrw_r(16, 10, 14);
        s.sub(16, 12, 16);            // b
        s.strx(16, PR, offc(b));
        s.mask(13, 16, cp[2]);
        const int nooffset=s.cbz_hole(13);
        s.mov(11, 12);                // limit-a
        s.sub(16, 12, 16);            // limit-a-b
        s.movi(15, 0);                // a
        const int loop=s.o;
        s.cmpi(15, 255);
        const int out1=s.bc_hole(EQ);
        s.subi(11, 11, 1);
        s.subi(16, 16, 1);
        s.mask(11, 11, cp[2]);
        s.mask(16, 16, cp[2]);
        s.ldrb_r(13, 9, 11);
        s.ldrb_r(4, 9, 16);
        s.cmp(13, 4);
        const int out2=s.bc_hole(NE);
        s.addi(15, 15, 1);
        s.b_to(loop);
        s.here(out1);
        s.here(out2);
        s.strx(15, PR, offc(a));
        const int tostore=s.b_hole();
        s.here(havematch);
        s.cmpi(15, 255);
        s.cinc(15, 15, LO);           // a+=a<255
        s.strx(15, PR, offc(a));
        s.here(nooffset);
        s.here(tostore);
        s.strw_r(12, 10, 14);         // cm(h[i])=limit
        s.here(notbyte);
        break;
      }
      case AVG:  // j k wt
        break;
      case MIX2: // sizebits j k rate mask
                 // cm=wt[size], cxt=input
        // int err=(y*32767-squash(p[i]))*cp[4]>>5;
        // int w=cr.a16[cr.cxt];
        // w+=(err*(p[cp[2]]-p[cp[3]])+(1<<12))>>13;
        // if (w<0) w=0;
        // if (w>65535) w=65535;
        // cr.a16[cr.cxt]=w;
        s.ldrw(10, PR, off(p[i]));
        s.addi(10, 10, 2048);
        s.ldrh_r(10, SQUASH, 10);
        s.sub(10, Y32767, 10);
        s.movi(11, cp[4]);
        s.mul(10, 10, 11);
        s.asr(10, 10, 5);             // err
        s.ldrx(9, PR, offc(a16));
        s.ldrx(11, PR, offc(cxt));
        s.ldrh_r(12, 9, 11);          // w
        s.ldrw(13, PR, off(p[cp[2]]));
        s.ldrw(14, PR, off(p[cp[3]]));
        s.sub(13, 13, 14);
        s.mul(13, 13, 10);
        s.addi4096(13, 13);
        s.add_asr(12, 12, 13, 13);
        s.cmpi(12, 0);
        s.csel(12, 12, ZR, GE);
        s.movi(13, 65535);
        s.cmp(12, 13);
        s.csel(12, 12, 13, LE);
        s.strh_r(12, 9, 11);
        break;
      case MIX: { // sizebits j m rate mask
                  // cm=wt[size][m], cxt=input
        // int m=cp[3];
        // int err=(y*32767-squash(p[i]))*cp[4]>>4;
        // int* wt=(int*)&cr.cm[cr.cxt];
        // for (int j=0; j<m; ++j)
        //   wt[j]=clamp512k(wt[j]+((err*p[cp[2]+j]+(1<<12))>>13));
        const int m=cp[3];
        s.ldrw(10, PR, off(p[i]));
        s.addi(10, 10, 2048);
        s.ldrh_r(10, SQUASH, 10);
        s.sub(10, Y32767, 10);
        s.movi(11, cp[4]);
        s.mul(10, 10, 11);
        s.asr(10, 10, 4);             // err
        s.ldrx(9, PR, offc(cm));
        s.ldrx(11, PR, offc(cxt));
        s.addx_lsl(9, 9, 11, 2);      // wt
        s.addx_i(12, PR, off(p[cp[2]]));
        s.movi(15, (1<<19)-1);
        s.movi(16, U32(-(1<<19)));
        int k=0;
        if (m>=4) {  // four at a time
          s.w(0x4e040d43);            // dup v3.4s, w10
          s.w(0x4f002604);            // movi v4.4s, #16, lsl #8  (4096)
          s.w(0x4e040de5);            // dup v5.4s, w15
          s.w(0x4e040e06);            // dup v6.4s, w16
          for (; k+4<=m; k+=4) {
            s.w(0x3dc00181|U32(k/4)<<10);  // ldr q1, [x12, #k*4]
            s.w(0x3dc00122|U32(k/4)<<10);  // ldr q2, [x9, #k*4]
            s.w(0x4ea39c21);          // mul v1.4s, v1.4s, v3.4s
            s.w(0x4ea48421);          // add v1.4s, v1.4s, v4.4s
            s.w(0x4f330421);          // sshr v1.4s, v1.4s, #13
            s.w(0x4ea28421);          // add v1.4s, v1.4s, v2.4s
            s.w(0x4ea56c21);          // smin v1.4s, v1.4s, v5.4s
            s.w(0x4ea66421);          // smax v1.4s, v1.4s, v6.4s
            s.w(0x3d800121|U32(k/4)<<10);  // str q1, [x9, #k*4]
          }
        }
        for (; k<m; ++k) {
          s.ldrw(13, 12, k*4);
          s.ldrw(14, 9, k*4);
          s.mul(13, 13, 10);
          s.addi4096(13, 13);
          s.add_asr(14, 14, 13, 13);
          s.cmp(14, 15);
          s.csel(14, 14, 15, LE);
          s.cmp(14, 16);
          s.csel(14, 14, 16, GE);
          s.strw(14, 9, k*4);
        }
        break;
      }
      default:
        error("invalid ZPAQ component");
    }
  }
  s.w(0xd65f03c0);                    // ret
#undef off
#undef offc
  return s.o;
}

#ifdef ZS_JITTEST
/*
	The test of ZPAQL::assemble (a build with -DZS_JITTEST; ZS_JITTEST=seed,count
	in the environment runs it instead of the program): programs made at
	random, each run on the interpreter and on the code of the JIT with the
	same machine and the same input. Everything must be the same after
	each run: a, b, c, d, r, m, h, what OUT wrote, and an error if the other
	had one. Returns the number of programs that differ.
*/
static U32 zs_jt_rnd(U32& s) {s^=s<<13; s^=s>>17; s^=s<<5; return s;}
int zs_jittest(U32 seed, int count) {
  U32 rs=seed ? seed : 1;
  int bad=0, compared=0, errors=0, endless=0;
  for (int t=0; t<count; ++t) {
    // the program
    U8 prog[80];
    const int len=4+zs_jt_rnd(rs)%60;
    for (int i=0; i<len; ) {
      const U32 k=zs_jt_rnd(rs)%100;
      int op;
      if (k<3) op=zs_jt_rnd(rs)&255;                    // anything, errors too
      else if (k<6) op=255;                             // lj
      else if (k<16) {static const U8 j[3]={39,47,63}; op=j[zs_jt_rnd(rs)%3];}
      else if (k<20) op=57+2*(zs_jt_rnd(rs)%2)+(zs_jt_rnd(rs)%3==0);  // out, hash, hashd (and 58: error)
      else do op=zs_jt_rnd(rs)&255; while (iserr(op) || op==56 || op==255 || op==39 || op==47 || op==63);
      prog[i++]=op;
      if (op==255) {
        const int to=zs_jt_rnd(rs)%(len+2);
        if (i<len) prog[i++]=to&255;
        if (i<len) prog[i++]=to>>8;
      }
      else if (op==39 || op==47 || op==63) {
        if (i<len) prog[i++]=(zs_jt_rnd(rs)%25-12)&255;
      }
      else if (op%8==7) {
        if (i<len) prog[i++]=(zs_jt_rnd(rs)%4==0) ? zs_jt_rnd(rs)%34 : zs_jt_rnd(rs)&255;
      }
      else if (op<51 && (op%8==1 || op%8==2) && zs_jt_rnd(rs)%3==0) {  // a run of ++ or --
        for (int j=zs_jt_rnd(rs)%6; j>0 && i<len; --j) prog[i++]=op;
      }
    }
    prog[len-1]=56;  // halt
    const int hh=zs_jt_rnd(rs)%6, hm=zs_jt_rnd(rs)%8;
    ZPAQL z[2];
    for (int v=0; v<2; ++v) {
      ZPAQL& q=z[v];
      const int hsize=7+len+1+1-2+1;
      q.header.resize(hsize+300);
      q.header[0]=hsize&255, q.header[1]=hsize>>8;
      q.header[2]=hh, q.header[3]=hm;
      q.cend=8;            // n=0, COMP END
      q.hbegin=q.hend=q.cend+128;
      for (int i=0; i<len; ++i) q.header[q.hend++]=prog[i];
      q.header[q.hend++]=0;
      q.inith();
    }
    // the same machine in both
    U32 st=zs_jt_rnd(rs);
    for (int v=0; v<2; ++v) {
      U32 r2=st;
      ZPAQL& q=z[v];
      q.b=zs_jt_rnd(r2), q.c=zs_jt_rnd(r2), q.d=zs_jt_rnd(r2), q.f=zs_jt_rnd(r2)&1;
      if (zs_jt_rnd(r2)&1) q.b&=255, q.c&=255, q.d&=255;
      for (int i=0; i<256; ++i) q.r[i]=(zs_jt_rnd(r2)%3) ? zs_jt_rnd(r2)%40 : zs_jt_rnd(r2);
      for (size_t i=0; i<q.m.size(); ++i) q.m[i]=zs_jt_rnd(r2);
      for (size_t i=0; i<q.h.size(); ++i) q.h[i]=(zs_jt_rnd(r2)%3) ? zs_jt_rnd(r2)%40 : zs_jt_rnd(r2);
      if (zs_jt_rnd(r2)%4==0) q.bufptr=q.outbuf.isize()-1-zs_jt_rnd(r2)%20;  // OUT fills the buffer
    }
    bool differs=false;
    for (int k=0; k<6 && !differs; ++k) {
      const U32 input=(zs_jt_rnd(rs)%5==0) ? zs_jt_rnd(rs) : (zs_jt_rnd(rs)&255);
      int e0=0, e1=0;
      z[0].passi=0, z[0].passimax=1;   // the interpreter, with a limit of steps
      try {z[0].run(input);}
      catch (std::exception& e) {e0=strstr(e.what(), "does not end") ? 2 : 1;}
      if (e0==2) {++endless; break;}   // never ends: nothing to compare
      if (getenv("ZS_JITTEST_V")) {    // which one hangs or dies
        printf("program %d input %d (%08x) hh %d hm %d:", t, k, input, hh, hm);
        for (int i=0; i<len; ++i) printf(" %d", prog[i]);
        printf("\n");
        fflush(stdout);
      }
      z[1].passimax=0;                 // the JIT
      try {z[1].run(input);}
      catch (std::exception& e) {e1=1;}
      ++compared;
      errors+=e0;
      differs=e0!=e1 || z[0].a!=z[1].a || z[0].b!=z[1].b || z[0].c!=z[1].c || z[0].d!=z[1].d
        || z[0].bufptr!=z[1].bufptr
        || memcmp(&z[0].r[0], &z[1].r[0], 256*4)
        || memcmp(&z[0].m[0], &z[1].m[0], z[0].m.size())
        || memcmp(&z[0].h[0], &z[1].h[0], z[0].h.size()*4)
        || memcmp(&z[0].outbuf[0], &z[1].outbuf[0], z[0].bufptr);
      if (differs) {
        ++bad;
        if (bad<=5) {
          printf("JITTEST differs: program %d input %d (%08x) err %d/%d a %08x/%08x b %08x/%08x c %08x/%08x d %08x/%08x bufptr %d/%d hh %d hm %d\n  ",
            t, k, input, e0, e1, z[0].a, z[1].a, z[0].b, z[1].b, z[0].c, z[1].c, z[0].d, z[1].d,
            z[0].bufptr, z[1].bufptr, hh, hm);
          for (int i=0; i<len; ++i) printf("%d ", prog[i]);
          printf("\n");
        }
      }
      if (e0) break;
    }
    z[0].bufptr=z[1].bufptr=0;  // nothing to flush
  }
  printf("JITTEST seed %u: %d programs, %d runs compared (%d of them ZPAQL errors), %d endless left out, %d DIFFERENT\n",
    seed, count, compared, errors, endless, bad);
  return bad;
}
#endif // corresponds to #ifdef (#ifdef ZS_JITTEST)
