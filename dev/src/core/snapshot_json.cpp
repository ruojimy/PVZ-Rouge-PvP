#include "core/snapshot_json.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string_view>
#include <unordered_set>
#include <vector>
namespace pvz {
namespace {
constexpr size_t bytes_limit=32u*1024u*1024u, output_limit=8u*1024u*1024u, items_limit=1024u*1024u;
struct Fallback {};
// Exactly the compact ensure_ascii=False JSON spelling used by stdlib.cpp.
std::string number(double d){
 if(!std::isfinite(d))throw Fallback{};
 char b[32];if(d==std::floor(d)&&std::fabs(d)<1e16){std::snprintf(b,sizeof b,"%lld",(long long)d);return b;}
 for(int p=1;p<=17;++p){std::snprintf(b,sizeof b,"%.*g",p,d);if(std::strtod(b,nullptr)==d)break;}
 std::string s(b);if(s.find_first_of(".eEn")==std::string::npos)s+=".0";return s;
}
bool utf8(std::string_view s){
 for(size_t i=0;i<s.size();){unsigned c=(unsigned char)s[i++],need=0,min=0,value=0;
  if(c<128)continue;
  if(c>=0xc2&&c<=0xdf){need=1;min=0x80;value=c&31;}
  else if(c>=0xe0&&c<=0xef){need=2;min=0x800;value=c&15;}
  else if(c>=0xf0&&c<=0xf4){need=3;min=0x10000;value=c&7;}else return false;
  if(need>s.size()-i)return false;
  for(unsigned n=0;n<need;++n){unsigned next=(unsigned char)s[i++];if((next&0xc0)!=0x80)return false;value=(value<<6)|(next&63);}
  if(value<min||value>0x10ffff||(value>=0xd800&&value<=0xdfff))return false;
 }return true;
}
struct Range {size_t start=0,size=0;bool string=false,bytes=false,ready=false;};
struct Parser {
 const std::string& input;std::string output;size_t cursor=0;std::vector<Range> refs;
 unsigned u8(){if(cursor>=input.size())throw Fallback{};return (unsigned char)input[cursor++];}
 uint32_t u32(){uint32_t n=0;for(int i=0;i<4;++i)n|=uint32_t(u8())<<(i*8);return n;}
 size_t length(size_t limit){int32_t n=int32_t(u32());if(n<0||size_t(n)>limit)throw Fallback{};return size_t(n);}
 void room(size_t n){if(n>output_limit-output.size())throw Fallback{};}
 void append(std::string_view s){room(s.size());output.append(s.data(),s.size());}
 void ch(char c){room(1);output+=c;}
 void string(std::string_view s){
  ch('"');size_t first=0;
  for(size_t i=0;i<s.size();++i){unsigned char c=(unsigned char)s[i];if(c>=32&&c!='"'&&c!='\\')continue;
   append(s.substr(first,i-first));first=i+1;
   switch(c){case '"':append("\\\"");break;case '\\':append("\\\\");break;case '\n':append("\\n");break;case '\r':append("\\r");break;case '\t':append("\\t");break;case '\b':append("\\b");break;case '\f':append("\\f");break;
    default:{char b[8];std::snprintf(b,sizeof b,"\\u%04x",c);append(b);break;}}
  }append(s.substr(first));ch('"');
 }
 Range value(int depth=0){
  if(depth>128)throw Fallback{};
  unsigned tag=u8();bool flag=(tag&128)!=0;tag&=127;size_t slot=refs.size();
  if(flag){if(slot>=items_limit)throw Fallback{};refs.emplace_back();}
  Range result;result.start=output.size();
  auto finish=[&]{result.size=output.size()-result.start;result.ready=true;if(flag)refs[slot]=result;return result;};
  if(tag=='N')append("null");else if(tag=='T')append("true");else if(tag=='F')append("false");
  else if(tag=='i')append(number(double(int32_t(u32()))));
  else if(tag=='l'){
   int32_t signed_count=int32_t(u32());int64_t count=signed_count<0?-int64_t(signed_count):int64_t(signed_count);if(count>4)throw Fallback{};
   uint64_t n=0;for(int64_t i=0;i<count;++i){unsigned d=u8();d|=u8()<<8;if(d>32767)throw Fallback{};n|=uint64_t(d)<<(15*i);}
   if(n>=9007199254740992ull)throw Fallback{};append(number(signed_count<0?-double(n):double(n)));
  }else if(tag=='g'){
   uint64_t bits=0;for(int i=0;i<8;++i)bits|=uint64_t(u8())<<(8*i);double d;std::memcpy(&d,&bits,8);append(number(d));
  }else if(tag=='s'||tag=='u'||tag=='t'||tag=='a'||tag=='A'||tag=='z'||tag=='Z'){
   size_t n=(tag=='z'||tag=='Z')?u8():length(bytes_limit);if(n>input.size()-cursor)throw Fallback{};
   std::string_view s(input.data()+cursor,n);cursor+=n;result.string=true;result.bytes=tag=='s';
   if(!result.bytes&&!utf8(s))throw Fallback{};string(s);
  }else if(tag=='r'){
   if(flag)throw Fallback{};size_t index=u32();if(index>=refs.size()||!refs[index].ready)throw Fallback{};
   Range previous=refs[index];room(previous.size);output.append(output,previous.start,previous.size);result.string=previous.string;result.bytes=previous.bytes;
  }else if(tag=='['||tag=='('||tag==')'){
   size_t n=tag==')'?u8():length(items_limit);ch('[');for(size_t i=0;i<n;++i){if(i)ch(',');value(depth+1);}ch(']');
  }else if(tag=='{'){
   ch('{');size_t count=0;std::unordered_set<std::string> keys;
   for(;;){if(cursor>=input.size())throw Fallback{};if((unsigned char)input[cursor]=='0'){++cursor;break;}
    if(++count>items_limit)throw Fallback{};if(count>1)ch(',');Range key=value(depth+1);
    // The V mapping contract for numeric/bool/None or duplicate keys remains
    // in the legacy codec. Real Room wire dictionaries use Unicode keys.
    if(!key.string||key.bytes||!keys.emplace(output.substr(key.start,key.size)).second)throw Fallback{};
    ch(':');value(depth+1);
   }ch('}');
  }else throw Fallback{};
  return finish();
 }
};
}
bool snapshot_json_from_marshal(const std::string& frozen,std::string& json){
 if(frozen.size()>bytes_limit)return false;
 try{Parser parser{frozen};parser.output.reserve(std::min(frozen.size(),output_limit));parser.value();if(parser.cursor!=frozen.size())return false;json=std::move(parser.output);return true;}
 catch(const Fallback&){return false;}
}
}
