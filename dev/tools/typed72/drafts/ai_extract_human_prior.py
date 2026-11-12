"""Offline table extraction, never part of the C++ runtime."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
source=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp/rv_human70.py'
tree=ast.parse(source.read_text(encoding='utf8'))
values=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RESIDUAL' for t in n.targets))
body='#include "sim/typed/ai_human_prior.h"\n#include <array>\n#include <string_view>\n#include <utility>\nnamespace pvz::typed72 {\nnamespace {\n'
body+='// rv_human70.py SHA256 '+hashlib.sha256(source.read_bytes()).hexdigest()+'\n'
body+='constexpr std::array<std::pair<std::string_view,double>,'+str(len(values))+'> residuals{{\n'
for key,value in values.items():body+='    {'+json.dumps(key,ensure_ascii=False)+','+repr(value)+'},\n'
body+='}};\n}\ndouble ai_human_residual(const std::string& card){for(const auto& [key,value]:residuals)if(key==card)return value;return 0.;}\n'
body+='double ai_human_feature(std::span<const std::string> deck){double total=0.;for(const auto& key:deck)total+=ai_human_residual(key);return total;}\n}\n'
(Path(__file__).parent/'ai_human_prior.cpp').write_text(body,encoding='utf8')
print('Extracted',len(values),'r22 residual constants into C++ source')
