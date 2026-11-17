// Extract exact uncompressed local XNA SoundEffect assets to RIFF/WAVE.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const root=path.resolve(process.argv[2]||'C:/Program Files (x86)/Steam/steamapps/common/Terraria/Content');
const output=path.resolve('extract/assets/terraria');
await fs.mkdir(output,{recursive:true});
const records=[];
for(const name of ['NPC_Hit_1','NPC_Hit_2','NPC_Killed_1','NPC_Killed_2','Roar_0','Custom/eow_dig']){
 const file=path.join(root,'Sounds',name+'.xnb');const bytes=await fs.readFile(file);
 if(bytes.toString('ascii',0,3)!=='XNB'||(bytes[5]&0xc0))throw Error('Expected uncompressed XNB: '+file);
 let offset=10;const int=()=>{let n=bytes.readUInt32LE(offset);offset+=4;return n;};
 const variable=()=>{let n=0,shift=0,b;do{b=bytes[offset++];n|=(b&127)<<shift;shift+=7;}while(b&128);return n;};
 const string=()=>{const n=variable();const s=bytes.toString('utf8',offset,offset+n);offset+=n;return s;};
 if(variable()!==1||!string().startsWith('Microsoft.Xna.Framework.Content.SoundEffectReader'))throw Error('Unexpected reader');
 int();if(variable()!==0||variable()!==1)throw Error('Unexpected shared resource or reader index');
 const formatSize=int(),format=bytes.subarray(offset,offset+formatSize);offset+=formatSize;
 const dataSize=int(),pcm=bytes.subarray(offset,offset+dataSize);offset+=dataSize;
 const loopStart=int(),loopLength=int(),duration=int();if(offset!==bytes.length)throw Error('Unexpected XNB suffix');
 const chunk=(tag,data)=>{const h=Buffer.alloc(8);h.write(tag);h.writeUInt32LE(data.length,4);return Buffer.concat([h,data,Buffer.alloc(data.length%2)]);};
 const body=Buffer.concat([Buffer.from('WAVE'),chunk('fmt ',format),chunk('data',pcm)]),head=Buffer.alloc(8);head.write('RIFF');head.writeUInt32LE(body.length,4);
 const wav=Buffer.concat([head,body]),dest=path.join(output,'terraria_'+path.basename(name)+'.wav');await fs.writeFile(dest,wav);
 records.push({source:file,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),output:dest,output_sha256:crypto.createHash('sha256').update(wav).digest('hex'),loopStart,loopLength,duration});
}
await fs.writeFile(path.join(output,'effects-sources.json'),JSON.stringify(records,null,2)+'\n');
console.log(`Extracted ${records.length} sound effects`);
