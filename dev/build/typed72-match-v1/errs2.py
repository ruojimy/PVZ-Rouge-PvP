import sys,re
t=open(sys.argv[1],'rb').read()
try:s=t.decode('utf8')
except:s=t.decode('gbk','replace')
seen=[]
for l in s.splitlines():
    if ' error ' in l or '纯虚' in l or 'pure virtual' in l or '未定义' in l or 'note: ' in l and 'abstract' in l:
        m=re.sub(r'\[C:.*','',l);m=m.split(chr(92))[-1][:200]
        if m not in seen:seen.append(m)
print(len(seen));print('\n'.join(seen[:int(sys.argv[2])]))
