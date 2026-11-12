from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
p=root/'tools/typed72/drafts/cold_native_factory.cpp';t=p.read_bytes().decode('utf8')
i=t.index('for(double angle:facing>=0.?std::initializer_list<double>');j=t.index(')',t.index('std::initializer_list<double>{',i+60))
print(t[i:j+60])
