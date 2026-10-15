/* Varians Web IIIF, V0.8.5.25. No external dependencies or persistent storage.
 * Image API 1/2/3, progressive size/region fallbacks, stale-request avoidance.
 * An image, whether a reduced derivative or a region, is ALWAYS displayed
 * in the original canvas coordinate frame provided by VariansGeometry.
 */
const VariansIIIF = (() => {
  const metadata = new Map(); // session only, no private API or auth tokens
  const number = n => Number.isFinite(Number(n)) && Number(n)>0 ? Number(n) : null;
  const safeURL = s => typeof s==='string' && /^https?:\/\//i.test(s.trim());
  const version = s => [1,2,3].includes(Number(s?.iiif_version)) ? Number(s.iiif_version) : 2;
  const quality = s => version(s)===1?'native':'default';
  const clampRegion = (r,f) => {
    if(!r || !f)return null;
    const x=Math.max(0,Math.min(f.w-1,Math.floor(Number(r.x)||0)));
    const y=Math.max(0,Math.min(f.h-1,Math.floor(Number(r.y)||0)));
    const w=Math.max(1,Math.min(f.w-x,Math.ceil(Number(r.w)||f.w)));
    const h=Math.max(1,Math.min(f.h-y,Math.ceil(Number(r.h)||f.h)));
    return {x,y,w,h};
  };
  const sameRegion = (a,b) => a&&b&&['x','y','w','h'].every(k=>a[k]===b[k]);
  function limits(source){
    const m=metadata.get(String(source?.service||'').replace(/\/$/,''))||{};
    const strictest=(key)=>{const a=number(m[key]),b=number(source?.[key]);return a&&b?Math.min(a,b):(a||b)};
    return {maxWidth:strictest('maxWidth'),maxHeight:strictest('maxHeight'),maxArea:strictest('maxArea')};
  }
  function boundWidth(requested,r,source){
    let w=Math.max(1,Math.min(Math.round(requested),Math.ceil(r.w)));
    const caps=limits(source);
    if(caps.maxWidth)w=Math.min(w,Math.floor(caps.maxWidth));
    if(caps.maxHeight)w=Math.min(w,Math.floor(caps.maxHeight*r.w/r.h));
    if(caps.maxArea)w=Math.min(w,Math.floor(Math.sqrt(caps.maxArea*r.w/r.h)));
    return Math.max(1,w);
  }
  function path(source,r,full,width){
    const service=String(source?.service||'').replace(/\/$/,'');
    if(!safeURL(service))return null;
    const region=sameRegion(r,full)?'full':`${r.x},${r.y},${r.w},${r.h}`;
    // Image API 1 supports "full" size and native quality; Image API 2
    // uses "full", Image API 3 uses "max" for original resolution.
    const orig=width>=r.w;
    const size=orig?(version(source)===3?'max':'full'):`${width},`;
    return `${service}/${region}/${size}/0/${quality(source)}.jpg`;
  }
  function plan(source,region,full,displayWidth=900,dpr=1){
    if(!source||source.type==='none')return [];
    if(source.type==='file')return source.path?[{url:source.path,local:true,kind:'local'}]:[];
    if(source.type!=='iiif')return [];
    const r=clampRegion(region,full),f=clampRegion(full,full);
    if(!r||!f)return [];
    const result=[],seen=new Set();
    function add(url,local,kind){
      if(!url||seen.has(url))return;
      // Never inject unsafe remote javascript/data schemes from a manuscript.
      if(!safeURL(url))return;
      seen.add(url);result.push({url,local:!!local,kind});
    }
    if(safeURL(source.service)){
      const desired=Math.max(700,Math.min(8192,Math.round((number(displayWidth)||900)*(number(dpr)||1)*1.4)));
      const width=boundWidth(desired,r,source);
      add(path(source,r,f,width),false,'region-best');
      const smaller=boundWidth(Math.min(1100,Math.max(480,Math.floor(width*.55))),r,source);
      if(smaller<width)add(path(source,r,f,smaller),false,'region-reduced');
      // A region can be refused by an otherwise functional Image API.
      // A full image MUST then be positioned and clipped locally.
      const fullWidth=boundWidth(Math.min(1400,Math.max(700,desired)),f,source);
      add(path(source,f,f,fullWidth),true,'full-reduced');
      const smallFull=boundWidth(Math.min(700,fullWidth),f,source);
      if(smallFull<fullWidth)add(path(source,f,f,smallFull),true,'full-small');
    }
    add(source.image||source.url, true, 'preview');
    return result;
  }
  function fullPageURL(source,full){
    if(source?.type==='file')return source.path||null;
    if(source?.type!=='iiif')return null;
    if(safeURL(source.service)){
      const s=String(source.service).replace(/\/$/,'');
      return `${s}/full/${version(source)===3?'max':'full'}/0/${quality(source)}.jpg`;
    }
    return safeURL(source.image||source.url)?(source.image||source.url):null;
  }
  function acceptInfo(json){
    if(!json||typeof json!=='object'||!number(json.width)||!number(json.height))return null;
    // Extra size capabilities are hints only, not evidence that an image is public.
    return {width:number(json.width),height:number(json.height),
      maxWidth:number(json.maxWidth),maxHeight:number(json.maxHeight),maxArea:number(json.maxArea)};
  }
  function discover(source){
    if(!safeURL(source?.service)||typeof fetch!=='function')return Promise.resolve(null);
    const service=String(source.service).replace(/\/$/,'');
    if(metadata.has(service))return Promise.resolve(metadata.get(service));
    metadata.set(service,{}); // in-flight/failed results are not refetched per render
    const controller=typeof AbortController!=='undefined'?new AbortController():null;
    const abort=setTimeout(()=>controller?.abort(),2500);
    return fetch(service+'/info.json',{signal:controller?.signal,cache:'default',credentials:'omit'})
      .then(r=>r.ok?r.json():null).then(acceptInfo)
      .then(v=>{if(v)metadata.set(service,v);return v})
      .catch(()=>null).finally(()=>clearTimeout(abort));
  }
  // Browser runtime. A cancelled <img> cannot change the DOM for the next
  // page; neither its error event nor its timeout can activate an old plan.
  function attach(img, candidates, viewport, onFailure){
    if(!img||!candidates?.length)return ()=>{};
    let active=true,index=0,timer=null;
    const finish=()=>{if(timer!==null){clearTimeout(timer);timer=null}};
    const style=(c)=>{
      if(c.local && viewport?.partial){
        const {full,r}=viewport;
        img.style.cssText=`position:absolute;width:${100*full.w/r.w}%;height:auto;max-width:none;left:${-100*r.x/r.w}%;top:${-100*r.y/r.h}%`;
      }else img.style.cssText='';
      img.dataset.iiifQuality=c.kind;
    };
    const timeout=()=>{if(active && img.isConnected)next()};
    const start=()=>{
      if(!active||!img.isConnected)return;
      const c=candidates[index];style(c);
      // The source property is assigned only to the CURRENT mounted image.
      img.src=c.url;
      finish();timer=setTimeout(timeout,12000);
    };
    const next=()=>{
      finish();if(!active||!img.isConnected)return;
      if(++index<candidates.length)start();
      else {active=false;img.removeAttribute('src');onFailure?.(img)}
    };
    const onLoad=()=>finish();
    const onError=()=>next();
    img.addEventListener('load',onLoad);
    img.addEventListener('error',onError);
    // Initial src was inserted with stage.innerHTML. The load might already
    // have succeeded or failed before handlers were registered.
    style(candidates[0]);
    if(img.complete){if(img.naturalWidth>0)finish();else next()}
    else {timer=setTimeout(timeout,12000)}
    return ()=>{active=false;finish();img.removeEventListener('load',onLoad);img.removeEventListener('error',onError);img.removeAttribute('src')};
  }
  function cancelStage(stage){
    if(!stage)return;
    stage.querySelectorAll('img[data-iiif-plan]').forEach(img=>img._variansCancel?.());
  }
  function bindStage(stage,unavailable){
    for(const img of stage.querySelectorAll('img[data-iiif-plan]')){
      let candidates;
      try{candidates=JSON.parse(img.dataset.iiifPlan)}catch{candidates=[]}
      if(!Array.isArray(candidates)||!candidates.length)continue;
      const crop=(img.dataset.crop||'').split(',').map(Number);
      const full=[Number(img.dataset.fullWidth),Number(img.dataset.fullHeight)];
      const partial=crop.length===4&&crop.every(Number.isFinite)&&full.every(number);
      const viewport=partial?{partial:true,r:{x:crop[0],y:crop[1],w:crop[2],h:crop[3]},full:{w:full[0],h:full[1]}}:{partial:false};
      img._variansCancel=attach(img,candidates,viewport,failed=>{
        const msg=document.createElement('span');msg.className='iiif-failure';msg.textContent=unavailable;
        failed.replaceWith(msg);
      });
    }
  }
  return Object.freeze({plan,fullPageURL,acceptInfo,discover,attach,bindStage,cancelStage,clampRegion,limits});
})();
