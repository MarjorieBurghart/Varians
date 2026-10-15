/* Varians web geometry V0.8.5.24 — self-contained, no DOM, no dependencies.
 * Kept in parity with image_sources.{effective_line_bbox,display_window_indices}
 * and editeur_tei.{scaled_bbox,crop_for_items}.  Coordinates throughout are
 * source-image pixels; the actual decoded bitmap may have fewer pixels.
 */
const VariansGeometry = (() => {
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const positive = (v, fallback=1) => {const n=Number(v);return Number.isFinite(n)&&n>0?n:fallback};
  function imageSource(p){return p?.image&&typeof p.image==='object'?p.image:(p?.iiif?{type:'iiif',...p.iiif}:{type:'none'})}
  function dimensions(p){const c=imageSource(p);const aw=positive(p?.alto_width,positive(c.width)),ah=positive(p?.alto_height,positive(c.height));return {aw,ah,iw:positive(c.width,aw),ih:positive(c.height,ah)}}
  function polygon(p,l){const {aw,ah,iw,ih}=dimensions(p);const points=l?.polygon;
    if(!Array.isArray(points)||points.length<3)return [];
    const out=[];
    for(const pair of points){if(!Array.isArray(pair)||pair.length<2||!finite(pair[0])||!finite(pair[1]))return [];out.push([pair[0]*iw/aw,pair[1]*ih/ah])}
    return out;
  }
  function bbox(p,l){const {aw,ah,iw,ih}=dimensions(p);const b=l?.bbox||{};
    let x=Number(b.hpos),y=Number(b.vpos),w=Number(b.width),h=Number(b.height);
    if(![x,y,w,h].every(Number.isFinite)||w<=0||h<=0){
      const pts=polygon(p,l);if(pts.length<3)return null;
      const xs=pts.map(v=>v[0]),ys=pts.map(v=>v[1]);
      x=Math.min(...xs);y=Math.min(...ys);w=Math.max(...xs)-x;h=Math.max(...ys)-y;
      if(w<=0||h<=0)return null;
      return {x,y,w,h,iw,ih};
    }
    // Legacy rectangular extents may be narrower than a PAGE polygon.
    const pts=polygon(p,l);
    if(pts.length>=3){const xs=pts.map(v=>v[0]),ys=pts.map(v=>v[1]);
      const bx=x*iw/aw,by=y*ih/ah,bw=w*iw/aw,bh=h*ih/ah;
      const x0=Math.min(bx,...xs),y0=Math.min(by,...ys),x1=Math.max(bx+bw,...xs),y1=Math.max(by+bh,...ys);
      return {x:x0,y:y0,w:x1-x0,h:y1-y0,iw,ih};
    }
    return {x:x*iw/aw,y:y*ih/ah,w:Math.max(1,w*iw/aw),h:Math.max(1,h*ih/ah),iw,ih};
  }
  function samePage(a,b){const p=a?.p||{},q=b?.p||{};return p===q||!!(p.id&&q.id&&String(p.id)===String(q.id))}
  function adjacent(a,b){
    if(!samePage(a,b))return false;
    const la=a?.l||{},lb=b?.l||{};
    if(la._page_mode||lb._page_mode||la._image_only||lb._image_only)return false;
    // For continuity the desktop deliberately trusts a usable original bbox
    // before polygon extents; cropping (unlike column detection) takes their union.
    function continuityBBox(p,l){
      const b=l?.bbox||{},x=Number(b.hpos),y=Number(b.vpos),w=Number(b.width),h=Number(b.height);
      const {aw,ah,iw,ih}=dimensions(p);
      if([x,y,w,h].every(Number.isFinite)&&w>0&&h>0)
        return {x:x*iw/aw,y:y*ih/ah,w:w*iw/aw,h:h*ih/ah};
      return bbox(p,l);
    }
    const aa=continuityBBox(a.p,la),bb=continuityBBox(b.p,lb);
    if(!aa||!bb)return true; // source's conservative continuation rule
    const {x:xa,y:ya,w:wa,h:ha}=aa,{x:xb,y:yb,w:wb,h:hb}=bb;
    if(yb<ya-Math.max(ha,hb)*.65)return false;
    const overlap=Math.max(0,Math.min(xa+wa,xb+wb)-Math.max(xa,xb));
    if(overlap<.1*Math.min(wa,wb)){
      const pageWidth=positive(a.p?.alto_width,0);
      const {aw,iw}=dimensions(a.p);const inSource=iw/aw;
      if(Math.abs(xa+wa/2-xb-wb/2)>Math.max(.10*pageWidth*inSource,.5*Math.max(wa,wb)))return false;
    }
    return true;
  }
  function windowIndices(items,center,radius=1){
    if(!items?.length)return [];
    center=Math.max(0,Math.min(items.length-1,Math.trunc(Number(center)||0)));
    if(items[center]?.l?._page_mode||items[center]?.l?._image_only)return [center];
    radius=Math.max(0,Math.trunc(Number(radius)||0));const out=[center];let prev=center;
    for(let i=center-1;i>=Math.max(0,center-radius);i--){if(!adjacent(items[i],items[prev]))break;out.unshift(i);prev=i}
    prev=center;
    for(let i=center+1;i<=Math.min(items.length-1,center+radius);i++){if(!adjacent(items[prev],items[i]))break;out.push(i);prev=i}
    return out;
  }
  function crop(items,pad=24){
    if(!items?.length)return null;
    const bs=items.map(it=>bbox(it.p,it.l));
    if(bs.some(b=>!b))return null; // no false (0,0) crop for missing OCR geometry
    const iw=bs[0].iw,ih=bs[0].ih;
    const x=Math.max(0,Math.trunc(Math.min(...bs.map(b=>b.x))-pad));
    const y=Math.max(0,Math.trunc(Math.min(...bs.map(b=>b.y))-pad));
    const x1=Math.min(Math.trunc(iw),Math.ceil(Math.max(...bs.map(b=>b.x+b.w))+pad));
    const y1=Math.min(Math.trunc(ih),Math.ceil(Math.max(...bs.map(b=>b.y+b.h))+pad));
    return {x,y,w:Math.max(1,x1-x),h:Math.max(1,y1-y)};
  }
  function fullRegion(p){const {iw,ih}=dimensions(p);return{x:0,y:0,w:iw,h:ih}}
  function folioRegion(p,src){
    if(!Array.isArray(src)||src.length!==4||!src.every(finite)||src[2]<=0||src[3]<=0)return fullRegion(p);
    // A <zone> holds SOURCE-image pixels, not OCR-grid pixels. Never multiply
    // the zone by image.width / alto_width a second time.
    const {iw,ih}=dimensions(p),x=Math.max(0,Math.min(iw,Math.floor(src[0]))),y=Math.max(0,Math.min(ih,Math.floor(src[1])));
    const x1=Math.max(x,Math.min(iw,Math.ceil(src[0]+src[2]))),y1=Math.max(y,Math.min(ih,Math.ceil(src[1]+src[3])));
    return {x,y,w:Math.max(1,x1-x),h:Math.max(1,y1-y)};
  }
  function nearestIndex(matches,previous,count){const valid=[...new Set(matches)].filter(i=>Number.isInteger(i)&&i>=0&&i<count);return valid.length?valid.sort((a,b)=>Math.abs(a-previous)-Math.abs(b-previous)||a-b)[0]:null}
  return Object.freeze({imageSource,dimensions,scaledPolygon:polygon,scaledBBox:bbox,adjacent,windowIndices,crop,fullRegion,folioRegion,nearestIndex});
})();
