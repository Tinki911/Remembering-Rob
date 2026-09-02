import base64, csv, hashlib, json, pathlib, re, subprocess, sys

repo=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'audit/_repo.git')
out=pathlib.Path('audit/original-media')
out.mkdir(parents=True,exist_ok=True)

def git(*args, text=True):
    return subprocess.check_output(['git',f'--git-dir={repo}',*args],text=text,stderr=subprocess.DEVNULL)

commits=[x for x in git('rev-list','--all').splitlines() if x]
records=[]; seen_binary={}; seen_url={}; source_versions={}
yt_form=re.compile(r"yt:(https?://[^'\"\s|]+)(?:\|([^'\"\s]+))?")
youtube=re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^'\"\s<]+")
loc_assign=re.compile(r"ROB_MEDIA\s*\[\s*['\"]([^'\"]+)['\"]\s*\]")
prefix=re.compile(r'data:(image|video)/([^;,\s]+);base64,',re.I)

def location_for(path,text,pos=0):
    name=path.lower()
    for key,loc in [('slater','slaters'),('colorado','colorado'),('emerald','emerald'),('giant','giants'),('idwal','idwal'),('glenariffe','glenariffe')]:
        if key in name: return loc
    prior=list(loc_assign.finditer(text[:pos]))
    return prior[-1].group(1) if prior else 'map-page'

def ext_for(kind,sub):
    s=sub.lower()
    if kind=='image': return {'jpeg':'jpg','jpg':'jpg','png':'png','webp':'webp','gif':'gif','heic':'heic'}.get(s,s.replace('svg+xml','svg'))
    return {'mp4':'mp4','quicktime':'mov','webm':'webm','x-m4v':'m4v'}.get(s,s)

def extract_data(text):
    # Tolerant scanner: after each data URI prefix, consume until the next JS quote.
    for m in prefix.finditer(text):
        kind,sub=m.groups(); start=m.end(); tail=text[start:]
        ends=[i for i in (tail.find("'"),tail.find('"')) if i>=0]
        if not ends: continue
        raw=tail[:min(ends)]
        # Allow physical whitespace / escaped line continuations, discard everything outside base64 alphabet.
        b64=''.join(ch for ch in raw if ch.isalnum() or ch in '+/=')
        if len(b64)<8: continue
        try:
            data=base64.b64decode(b64,validate=False)
        except Exception:
            continue
        if data: yield m.start(),kind.lower(),sub,data

for commit in commits:
    try: tree=git('ls-tree','-r','--name-only',commit)
    except Exception: continue
    paths=[p for p in tree.splitlines() if p.startswith('rob-map/') and (p.endswith('.js') or p.endswith('.html'))]
    for path in paths:
        try:
            blob=git('show',f'{commit}:{path}',text=False); text=blob.decode('utf-8','replace')
        except Exception: continue
        blobsha=hashlib.sha256(blob).hexdigest(); vk=(path,blobsha)
        if vk in source_versions: continue
        source_versions[vk]=commit
        for pos,kind,sub,data in extract_data(text):
            sha=hashlib.sha256(data).hexdigest(); loc=location_for(path,text,pos); unique=sha not in seen_binary
            if unique:
                folder=out/loc; folder.mkdir(parents=True,exist_ok=True)
                n=sum(1 for x in seen_binary.values() if x['location']==loc and x['kind']==kind)+1
                dest=folder/f'{loc}-{kind}-{n:03d}.{ext_for(kind,sub)}'; dest.write_bytes(data)
                seen_binary[sha]={'path':str(dest),'location':loc,'kind':kind,'bytes':len(data)}
            records.append({'location':loc,'kind':kind,'format':sub,'bytes':len(data),'sha256':sha,'source_path':path,
                            'source_commit':commit,'source_blob_sha256':blobsha,'extracted_path':seen_binary[sha]['path'],
                            'is_duplicate':not unique,'duplicate_of':'' if unique else seen_binary[sha]['path']})
        captured=set()
        for m in yt_form.finditer(text):
            url,thumb=m.groups(); captured.add(url); loc=location_for(path,text,m.start()); unique=url not in seen_url
            if unique: seen_url[url]={'location':loc,'first_source':path,'commit':commit}
            records.append({'location':loc,'kind':'youtube','format':'url','bytes':0,'sha256':hashlib.sha256(url.encode()).hexdigest(),
                            'source_path':path,'source_commit':commit,'source_blob_sha256':blobsha,'extracted_path':'',
                            'is_duplicate':not unique,'duplicate_of':'' if unique else seen_url[url]['first_source'],'url':url,'thumbnail':thumb or ''})
        for m in youtube.finditer(text):
            url=m.group(0).rstrip(');,]');
            if url in captured: continue
            loc=location_for(path,text,m.start()); unique=url not in seen_url
            if unique: seen_url[url]={'location':loc,'first_source':path,'commit':commit}
            records.append({'location':loc,'kind':'youtube','format':'url','bytes':0,'sha256':hashlib.sha256(url.encode()).hexdigest(),
                            'source_path':path,'source_commit':commit,'source_blob_sha256':blobsha,'extracted_path':'',
                            'is_duplicate':not unique,'duplicate_of':'' if unique else seen_url[url]['first_source'],'url':url,'thumbnail':''})

locs={}
for x in seen_binary.values():
    s=locs.setdefault(x['location'],{'unique_photos':0,'unique_embedded_videos':0,'unique_youtube_links':0,'binary_bytes':0})
    s['unique_photos' if x['kind']=='image' else 'unique_embedded_videos']+=1; s['binary_bytes']+=x['bytes']
for url,x in seen_url.items():
    s=locs.setdefault(x['location'],{'unique_photos':0,'unique_embedded_videos':0,'unique_youtube_links':0,'binary_bytes':0}); s['unique_youtube_links']+=1

manifest={'scope':'entire Git history of Tinki911/gkonopkaart rob-map','commits_scanned':len(commits),
          'unique_source_versions_scanned':len(source_versions),'location_summary':locs,'unique_binary_files':len(seen_binary),
          'unique_youtube_links':len(seen_url),'records':records}
pathlib.Path('audit/original-media-inventory.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
fields=['location','kind','format','bytes','sha256','source_path','source_commit','source_blob_sha256','extracted_path','is_duplicate','duplicate_of','url','thumbnail']
with open('audit/original-media-inventory.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); [w.writerow({k:r.get(k,'') for k in fields}) for r in records]
lines=['# Original memorial media audit','','Scope: **entire Git history** of `Tinki911/gkonopkaart`, restricted to `rob-map/` JavaScript and HTML files.','',
       'This audit is independent of the live Remembering Rob page and does **not** include new Dropbox uploads.','',
       '| Location | Unique photos | Unique embedded videos | Unique YouTube links |','|---|---:|---:|---:|']
for loc in sorted(locs):
    s=locs[loc]; lines.append(f"| {loc} | {s['unique_photos']} | {s['unique_embedded_videos']} | {s['unique_youtube_links']} |")
lines += ['',f'Commits scanned: **{len(commits)}**',f'Unique historical source-file versions scanned: **{len(source_versions)}**',
          f'Unique extracted image/video binaries: **{len(seen_binary)}**',f'Unique YouTube links found: **{len(seen_url)}**','',
          'Every unique embedded image/video has been decoded into `audit/original-media/<location>/`.',
          'Every occurrence, duplicate, source path, source commit and SHA-256 hash is recorded in the CSV/JSON inventory.']
pathlib.Path('audit/README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
