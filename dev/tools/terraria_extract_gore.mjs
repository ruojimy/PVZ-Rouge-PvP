// Extract original local Terraria gore textures. Usage: node tools/terraria_extract_gore.mjs [Content directory] [xnb module path]
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
const content=path.resolve(process.argv[2]||'C:/Program Files (x86)/Steam/steamapps/common/Terraria/Content');
const decoder=path.resolve(process.argv[3]||'build/terraria-reference/xnb/node_modules/xnb/dist/xnb.module.js');
const {unpackToFiles}=await import(pathToFileURL(decoder).href);
const output=path.resolve('extract/assets/terraria'),records=[];
await fs.mkdir(output,{recursive:true});
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
for(const id of [2,6,7,8,9,10,24,25,26,27,28,29,54,55,56,57]){
 const source=path.join(content,'Images',`Gore_${id}.xnb`),bytes=await fs.readFile(source);
 const files=await unpackToFiles(bytes,{fileName:`Gore_${id}.xnb`});
 const png=files.find(f=>f.extension==='png');if(!png)throw Error('No PNG decoded: '+source);
 const data=Buffer.from(await png.data.arrayBuffer()),dest=path.join(output,`Gore_${id}.png`);
 await fs.writeFile(dest,data);
 records.push({source,sha256:hash(bytes),output:dest,output_sha256:hash(data)});
}
await fs.writeFile(path.join(output,'gore-sources.json'),JSON.stringify(records,null,2)+'\n');
console.log(`Extracted ${records.length} original gore textures`);
