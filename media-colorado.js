window.ROB_MEDIA=window.ROB_MEDIA||{};
window.ROB_MEDIA['colorado']=window.ROB_MEDIA['colorado']||[];

// Videos are now treated as externally hosted memories rather than embedded
// in the map. Add an unlisted YouTube URL here for each video once uploaded.
window.ROB_VIDEO_LINKS=window.ROB_VIDEO_LINKS||{
  slaters:[],
  colorado:[],
  emerald:[],
  giants:[],
  idwal:[],
  glenariffe:[]
};

window.addEventListener('load',function(){
  // Replace the gallery renderer after the main map script has loaded.
  window.openGallery=function(id){
    const p=byId[id],g=document.getElementById('gallery');
    document.getElementById('galleryTitle').textContent=p.name+' — photos & videos';
    const photos=(p.media||[]).filter(s=>typeof s==='string'&&!s.startsWith('data:video'));
    const videos=(window.ROB_VIDEO_LINKS[id]||[]);
    const cards=[];

    photos.forEach((s,i)=>{
      cards.push('<button class="thumb" onclick="openPhotoFromGallery(\''+id+'\','+i+')"><img loading="lazy" src="'+s+'" alt="'+p.name+' memory '+(i+1)+'"></button>');
    });

    videos.forEach((v,i)=>{
      const fallback=photos.length?photos[Math.min(v.thumbIndex||0,photos.length-1)]:'';
      const thumb=v.thumb||fallback;
      const title=(v.title||'Watch video').replace(/"/g,'&quot;');
      cards.push('<button class="thumb video" aria-label="'+title+'" onclick="window.open(\''+v.url+'\',\'_blank\',\'noopener\')">'+
        (thumb?'<img loading="lazy" src="'+thumb+'" alt="'+title+'">':'')+
        '<div class="playbadge"><span>▶</span></div></button>');
    });

    g.innerHTML=cards.length?cards.join(''):'<div class="empty">No photos or videos have been added here yet.</div>';
    document.getElementById('galleryModal').classList.add('open');
  };

  window.openPhotoFromGallery=function(id,photoIndex){
    const p=byId[id];
    const photos=(p.media||[]).filter(s=>typeof s==='string'&&!s.startsWith('data:video'));
    const s=photos[photoIndex];
    if(!s)return;
    const box=document.getElementById('viewerMedia'),viewer=document.getElementById('viewer');
    box.innerHTML='<img src="'+s+'" alt="'+p.name+' memory">';
    viewer.classList.add('open');
    document.body.style.overflow='hidden';
  };
});
