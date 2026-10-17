#!/usr/bin/env python3
# manifest.py DIR [--nomtime-dirs] : prints type/mode/size/mtime_ns/link/hardlink-group/sha1 for every entry
import os,sys,stat,hashlib
root=sys.argv[1]; skipdir='--nomtime-dirs' in sys.argv
inode={}; out=[]
for dp,dns,fns in os.walk(root):
    for n in sorted(dns+fns):
        p=os.path.join(dp,n); r=os.path.relpath(p,root); st=os.lstat(p)
        m=st.st_mode; t=stat.S_IFMT(m)
        kind={stat.S_IFREG:'f',stat.S_IFDIR:'d',stat.S_IFLNK:'l',stat.S_IFIFO:'p',stat.S_IFCHR:'c',stat.S_IFBLK:'b',stat.S_IFSOCK:'s'}[t]
        extra=''
        if kind=='l': extra='->'+os.readlink(p)
        if kind=='f':
            h=hashlib.sha1(open(p,'rb').read()).hexdigest()[:12]; extra=h
            if st.st_nlink>1:
                g=inode.setdefault((st.st_dev,st.st_ino),'H%d'%len(inode)); extra+=' '+g
        mt='' if (kind=='d' and skipdir) else str(st.st_mtime_ns)
        out.append(f"{r!r} {kind} {oct(stat.S_IMODE(m))} {st.st_size if kind!='d' else '-'} {mt} {extra}")
print("\n".join(sorted(out)))
