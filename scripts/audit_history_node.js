const fs=require('fs'), path=require('path'), crypto=require('crypto'), cp=require('child_process'), vm=require('vm');
const repo=process.argv[2]||'audit/_repo.git', out='audit/original-media'; fs.mkdirSync(out,{recursive:true});
const git=(...a)=>cp.execFileSync('git',[`--git-dir=${repo}`,...a],{encoding:'utf8',maxBuffer:100*1024*1024});
const gitBuf=(...a)=>cp.execFileSync('git',[`--git-dir=${repo}`,...a],{maxBuffer:100*1024*1024});
const commits=git('rev-list','--all').trim().split(/\n+/).filter(Boolean);
const seen=new Map(), seenUrl=new Map(), versions=new Set(), records=[];
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const ext=(kind,sub)=>kind==='image'?({jpeg:'jpg',jpg:'jpg',png:'png',webp:'webp',gif:'gif',heic:'heic'}[sub]||sub):({mp4:'mp4',quicktime:'mov',webm:'webm','x-m4v':'m4v'}[sub]||sub);
function hint(p){p=p.toLowerCase(); for(const [k,v] of [['slater','slaters'],['colorado','colorado'],['emerald','emerald'],['giant','giants'],['idwal','idwal'],['glenariffe','glenariffe']]) if(p.includes(k)) return v; return 'map-page';}
function saveMedia(loc,s,sourcePath,commit,blobSha){
  if(typeof s!=='string') return;
  if(s.startsWith('data:')){
    const m=s.match(/^data:(image|video)\/([^;]+);base64,(.*)$/s); if(!m) return;
    const kind=m[1], sub=m[2].toLowerCase(); let buf; try{buf=Buffer.from(m[3].replace(/\s/g,''),'base64')}catch{return}; if(!buf.length)return;
    const h=sha(buf), unique=!seen.has(h); let dest;
    if(unique){ const dir=path.join(out,loc); fs.mkdirSync(dir,{recursive:true}); const n=[...seen.values()].filter(x=>x.location===loc&&x.kind===kind).length+1; dest=path.join(dir,`${loc}-${kind}-${String(n).padStart(3,'0')}.${ext(kind,sub)}`); fs.writeFileSync(dest,buf); seen.set(h,{path:dest,location:loc,kind,bytes:buf.length}); }
    else dest=seen.get(h).path;
    records.push({location:loc,kind,format:sub,bytes:buf.length,sha256:h,source_path:sourcePath,source_commit:commit,source_blob_sha256:blobSha,extracted_path:dest,is_duplicate:!unique,duplicate_of:unique?'':dest});
  } else if(s.startsWith('yt:')){
    const [url,thumb='']=s.slice(3).split('|'); saveUrl(loc,url,thumb,sourcePath,commit,blobSha);
  }
}
function saveUrl(loc,url,thumb,sourcePath,commit,blobSha){ if(!url)return; const unique=!seenUrl.has(url); if(unique)seenUrl.set(url,{location:loc,sourcePath,commit}); records.push({location:loc,kind:'youtube',format:'url',bytes:0,sha256:sha(Buffer.from(url)),source_path:sourcePath,source_commit:commit,source_blob_sha256:blobSha,extracted_path:'',is_duplicate:!unique,duplicate_of:unique?'':seenUrl.get(url).sourcePath,url,thumbnail:thumb||''}); }
for(const commit of commits){ let tree=''; try{tree=git('ls-tree','-r','--name-only',commit)}catch{continue}; for(const p of tree.split(/\n/).filter(x=>x.startsWith('rob-map/')&&(x.endsWith('.js')||x.endsWith('.html')))){
  let b; try{b=gitBuf('show',`${commit}:${p}`)}catch{continue}; const blobSha=sha(b), vk=p+'|'+blobSha; if(versions.has(vk))continue; versions.add(vk); const text=b.toString('utf8'); const locHint=hint(p);
  if(p.endsWith('.js')){
    const media={}; const context={window:{ROB_MEDIA:media},ROB_MEDIA:media,console:{log(){},warn(){},error(){}},URL,Array,Object,String,Number};
    try{vm.runInNewContext(text,context,{timeout:1000});}catch{}
    const objects=[context.ROB_MEDIA,context.window&&context.window.ROB_MEDIA].filter(Boolean);
    const done=new Set(); for(const obj of objects){ for(const [loc,val] of Object.entries(obj)){ if(!Array.isArray(val))continue; for(const s of val){ const k=loc+'|'+s; if(done.has(k))continue; done.add(k); saveMedia(loc||locHint,s,p,commit,blobSha); } } }
    // Some scripts keep YouTube/video link objects outside ROB_MEDIA.
    const u={}; const ctx2={window:{ROB_MEDIA:{},ROB_VIDEO_LINKS:u},ROB_MEDIA:{},ROB_VIDEO_LINKS:u,console:{log(){},warn(){},error(){}}}; try{vm.runInNewContext(text,ctx2,{timeout:1000});}catch{}
    for(const [loc,val] of Object.entries(ctx2.ROB_VIDEO_LINKS||{})) if(Array.isArray(val)) for(const url of val) if(typeof url==='string'&&/^https?:/.test(url)) saveUrl(loc,url,'',p,commit,blobSha);
  }
  // Scan any HTML or unexecuted script text for YouTube URLs.
  for(const m of text.matchAll(/https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be)\/[^'\"\s<)\]]+/g)) saveUrl(locHint,m[0],'',p,commit,blobSha);
}}
const locs={}; for(const x of seen.values()){const s=locs[x.location]||(locs[x.location]={unique_photos:0,unique_embedded_videos:0,unique_youtube_links:0,binary_bytes:0}); if(x.kind==='image')s.unique_photos++;else s.unique_embedded_videos++;s.binary_bytes+=x.bytes;} for(const x of seenUrl.values()){const s=locs[x.location]||(locs[x.location]={unique_photos:0,unique_embedded_videos:0,unique_youtube_links:0,binary_bytes:0});s.unique_youtube_links++;}
const manifest={scope:'entire Git history of Tinki911/gkonopkaart rob-map; JS executed in sandbox',commits_scanned:commits.length,unique_source_versions_scanned:versions.size,location_summary:locs,unique_binary_files:seen.size,unique_youtube_links:seenUrl.size,records}; fs.writeFileSync('audit/original-media-inventory.json',JSON.stringify(manifest,null,2));
const fields=['location','kind','format','bytes','sha256','source_path','source_commit','source_blob_sha256','extracted_path','is_duplicate','duplicate_of','url','thumbnail']; const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"'; fs.writeFileSync('audit/original-media-inventory.csv',[fields.map(q).join(','),...records.map(r=>fields.map(k=>q(r[k])).join(','))].join('\n')+'\n');
let lines=['# Original memorial media audit','','Scope: **entire Git history** of `Tinki911/gkonopkaart`, restricted to `rob-map/`. Historical media JavaScript was executed in an isolated sandbox so the original `ROB_MEDIA` arrays could be recovered exactly.','','This audit is independent of the live Remembering Rob page and does **not** include new Dropbox uploads.','','| Location | Unique photos | Unique embedded videos | Unique YouTube links |','|---|---:|---:|---:|']; for(const loc of Object.keys(locs).sort()){const s=locs[loc];lines.push(`| ${loc} | ${s.unique_photos} | ${s.unique_embedded_videos} | ${s.unique_youtube_links} |`)} lines.push('',`Commits scanned: **${commits.length}**`,`Unique historical source-file versions scanned: **${versions.size}**`,`Unique extracted image/video binaries: **${seen.size}**`,`Unique YouTube links found: **${seenUrl.size}**`,'','Every unique embedded image/video has been decoded into `audit/original-media/<location>/`.','Every occurrence, duplicate, source path, source commit and SHA-256 hash is recorded in the CSV/JSON inventory.'); fs.writeFileSync('audit/README.md',lines.join('\n')+'\n');
