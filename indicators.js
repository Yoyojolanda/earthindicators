// Earth Indicators: shared calculations.
// Every live number outside the charts comes from here: the front page tiles, the claims page
// and the "In short" boxes. Change a calculation or a verdict once, here, and every page agrees.
//
//   EI.get(id)    -> Promise of an object of ready-to-print strings (plus .tile for the front page)
//   EI.fill(root) -> fills every <span data-k="id.key"> inside root, e.g. data-k="air.vd"
//
// ids: air, sst, nino, ohc, sl, ice (Arctic), ant (Antarctic), glob (both together), co2, ch4, eei, sun (solar cycle), pdo
// Every object has: vd (plain verdict), through (how recent the data is), src (data source)
(function () {
const MS=[0,31,59,90,120,151,181,212,243,273,304,334],ML=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fmtDate=i=>{let m=11;while(MS[m]>i)m--;return ML[m]+' '+(i-MS[m]+1)};
const sg=(x,d=2)=>{const r=Math.abs(x)<.5*10**-d?0:x;return (r>=0?'+':'−')+Math.abs(r).toFixed(d)};
const ab=(x,d=2)=>(x<0?'−':'')+Math.abs(x).toFixed(d);
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const slope=P=>{const mx=mean(P.map(p=>p.x)),my=mean(P.map(p=>p.y));let a=0,b=0;P.forEach(p=>{a+=(p.x-mx)*(p.y-my);b+=(p.x-mx)**2});return a/b};
const ord=n=>n+(['th','st','nd','rd'][(n%100-20)%10]||['th','st','nd','rd'][n%100]||'th');
const rankTxt=(n,first,other)=>n==1?first+' on record':ord(n)+' '+other+' on record';
const get=f=>fetch('data/'+f).then(r=>{if(!r.ok)throw new Error(f);return r.text()});
const lines=t=>t.split(/\r?\n/).filter(l=>l.trim()&&!/^\s*(#|HDR)/.test(l));

// daily JSON files: one array per year plus a "1991-2020" climatology
function daily(d){const by={};d.forEach(r=>by[r.name]=r.data);const clim=by['1991-2020'],years=Object.keys(by).filter(k=>/^\d{4}$/.test(k)).map(Number).sort((a,b)=>a-b),cur=years[years.length-1];
 let last=-1;by[cur].forEach((v,i)=>{if(v!=null)last=i});
 const an=(y,i)=>by[y]&&by[y][i]!=null&&clim[i]!=null?by[y][i]-clim[i]:null,now=an(cur,last);
 const prior=years.filter(y=>y<cur).map(y=>[y,an(y,last)]).filter(r=>r[1]!=null),rec=prior.reduce((b,r)=>r[1]>b[1]?r:b,prior[0]);
 const annual=years.filter(y=>y<cur).map(y=>{const a=by[y].map((v,i)=>an(y,i)).filter(v=>v!=null);return{x:y,y:a.length>300?mean(a):null}}).filter(p=>p.y!=null);
 const back=n=>{let s=[],dt=new Date(Date.UTC(cur,0,last+1));for(let k=0;k<n;k++){const yy=dt.getUTCFullYear(),ii=Math.round((dt-Date.UTC(yy,0,1))/864e5);s.unshift(an(yy,ii));dt=new Date(dt-864e5)}return s};
 return{cur,last,now,rec,annual,back,rank:prior.filter(r=>r[1]>now).length+1,first:prior.length?prior[0][0]:cur,date:fmtDate(last)}}

// sea level: remove the mean seasonal cycle (residuals from a quadratic fit, 26 two-week bins), same as the sea level page
function fit2(P){const x0=P[0].x,A=[[0,0,0,0],[0,0,0,0],[0,0,0,0]];P.forEach(p=>{const t=p.x-x0;for(let i=0;i<3;i++){for(let j=0;j<3;j++)A[i][j]+=t**(i+j);A[i][3]+=p.y*t**i}});
 for(let i=0;i<3;i++)for(let k=i+1;k<3;k++){const f=A[k][i]/A[i][i];for(let j=i;j<4;j++)A[k][j]-=f*A[i][j]}
 const c=[0,0,0];for(let i=2;i>=0;i--)c[i]=(A[i][3]-[1,2].filter(j=>j>i).reduce((s,j)=>s+A[i][j]*c[j],0))/A[i][i];return x=>c[0]+c[1]*(x-x0)+c[2]*(x-x0)**2}
function deseason(P){const q=fit2(P),B=26,sum=Array(B).fill(0),n=Array(B).fill(0),bin=x=>Math.min(B-1,Math.floor((x%1)*B));
 P.forEach(p=>{const b=bin(p.x);sum[b]+=p.y-q(p.x);n[b]++});return P.map(p=>({...p,y:p.y-(n[bin(p.x)]?sum[bin(p.x)]/n[bin(p.x)]:0)}))}

// sea ice (NSIDC daily CSV): latest 5-day mean vs 1981-2010, rank for the date, yearly averages
function seaIce(t){const V={};let L=null;
 t.split(/\r?\n/).forEach(l=>{const p=l.split(','),y=+p[0],m=+p[1],d=+p[2],e=parseFloat(p[3]);if(!(y>1900&&m>=1&&e>=0)||(m==2&&d==29))return;const i=MS[m-1]+d-1;(V[y]=V[y]||{})[i]=e;if(!L||y>L.y||(y==L.y&&i>L.i))L={y,i}});
 const win=y=>{const a=[];for(let k=L.i-4;k<=L.i;k++)if(V[y]&&V[y][k]!=null)a.push(V[y][k]);return a.length?mean(a):null};
 const now=win(L.y),ref=[];for(let y=1981;y<=2010;y++){const w=win(y);if(w!=null)ref.push(w)}
 const all=Object.keys(V).map(Number).filter(y=>y<L.y).map(win).filter(v=>v!=null),rank=all.filter(v=>v<now).length+1,n=all.length+1,an=now-mean(ref);
 const dayRef=[];for(let i=0;i<365;i++){const a=[];for(let y=1981;y<=2010;y++)if(V[y]&&V[y][i]!=null)a.push(V[y][i]);dayRef[i]=a.length?mean(a):null}
 const full=Object.keys(V).map(Number).filter(y=>y<L.y&&Object.keys(V[y]).length>300);
 const yAn=y=>mean(Object.keys(V[y]).map(Number).filter(i=>dayRef[i]!=null).map(i=>V[y][i]-dayRef[i]));
 const vd=rank<=10?`${rank==1?'Lowest':ord(rank)+' lowest'} for this time of year (of ${n} years)`:an<0?'Below the long-term average for this time of year':'Above the 1981–2010 average for this time of year';
  // yearly minimum and maximum of the 5-day trailing mean (the way NSIDC reports them)
  const ext=(y,lo)=>{const a=[];for(let i=0;i<365;i++)if(V[y]&&V[y][i]!=null)a.push(i);if(a.length<150)return null;let b=null;
   a.forEach(i=>{const w=[];for(let k=i-4;k<=i;k++)if(V[y][k]!=null)w.push(V[y][k]);if(w.length){const m=mean(w);if(b==null||(lo?m<b:m>b))b=m}});return b};
  const yrs=Object.keys(V).map(Number).filter(y=>y>1978);
  const season=(y,end)=>y<L.y||L.i>end;   // the current year counts once its low (or high) season is over
  return{V,L,now,an,rank,n,full,yAn,vd,ext,yrs,season,date:fmtDate(L.i),through:`${fmtDate(L.i)}, ${L.y}`,first:Object.keys(V)[0]}}

// yearly extremes: N such that the N lowest years are exactly the N most recent; the lowest year; rank of the latest year
function lowest(P){const S=[...P].sort((a,b)=>a.v-b.v),R=[...P].sort((a,b)=>b.y-a.y);let k=0,since=null;
 // earliest year Y (not the first) such that every year from Y on is lower than every year before Y
 const ys=[...P].sort((a,b)=>a.y-b.y);for(let j=ys.length-1;j>=1;j--){const after=ys.slice(j),before=ys.slice(0,j);
  if(Math.max(...after.map(p=>p.v))<Math.min(...before.map(p=>p.v))){k=after.length;since=ys[j].y}}
 return{n:k,since,low:S[0].y,lastY:R[0].y,lastRank:S.findIndex(p=>p.y==R[0].y)+1,count:P.length}}

const SEAS=[['1-3','Jan–Mar',.125],['4-6','Apr–Jun',.375],['7-9','Jul–Sep',.625],['10-12','Oct–Dec',.875]];
const ncei=t=>t.split(/\r?\n/).slice(1).map(l=>l.trim().split(/\s+/).map(Number)).filter(r=>r.length>=3&&r[0]>1900&&isFinite(r[1]));

const LOAD={
 air:()=>get('era5_t2_global_day.json').then(JSON.parse).then(d=>{const r=daily(d),A=r.annual,y12=r.back(365).filter(v=>v!=null),pre=mean(y12)+0.88;
  const p98=A.find(p=>p.x==1998),last=A[A.length-1];let since=last.x;for(let i=A.length-1;i>=0&&A[i].y>p98.y;i--)since=A[i].x;
  const top=[...A].sort((a,b)=>b.y-a.y).slice(0,10);
  return{src:'Copernicus ERA5',vd:`${rankTxt(r.rank,'Hottest','warmest')} for this time of year (since ${r.first})`,now:sg(r.now)+' °C',date:r.date,through:`${r.date}, ${r.cur}`,
   pre12:pre.toFixed(2)+' °C',first:A[0].x,since,y98:sg(p98.y)+' °C',lastY:last.x,last:sg(last.y)+' °C',top10:Math.min(...top.map(p=>p.x)),
   trend:(slope(A.slice(-30))*10).toFixed(2)+' °C',
   warmDays:Math.round(100*y12.filter(v=>v>0).length/y12.length)+'%',
   ...(()=>{const all=r.back(40000);let n=0;for(let i=all.length-1;i>=0&&all[i]!=null&&all[i]>0;i--)n++;      // days in a row warmer than 1991-2020
    const cd=d.find(x=>x.name==String(r.cur)).data;let li=cd.length-1;while(li>=0&&cd[li]==null)li--;
    const st=new Date(Date.UTC(r.cur,0,li+1-(n-1)));
    return{warmRun:n.toLocaleString('en-US'),warmSince:st.toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}})(),
   ...(()=>{const t=A.slice(-10),c=t.reduce((b,p)=>p.y<b.y?p:b,t[0]),pre=A.slice(0,-10),k=pre.filter(p=>p.y<c.y).length;
    return{cool10Y:c.x,win10:t[0].x,cool10Beat:k==pre.length?`every one of the ${pre.length} years`:`${k} of the ${pre.length} years`}})(),
   tile:{v:sg(r.now)+' °C',l:`vs 1991–2020 average on ${r.date}`,s:`Last 12 months: about ${sg(pre,2)} °C above pre-industrial (1850–1900)`,spark:A,sparkLabel:`yearly, ${A[0].x}–${last.x}`}}}),

 sst:()=>get('oisst2.1_world_sst_day.json').then(JSON.parse).then(d=>{const r=daily(d),A=r.annual;
  return{src:'NOAA OISST',vd:`${rankTxt(r.rank,'Hottest','warmest')} for this time of year (since ${r.first})`,now:sg(r.now)+' °C',date:r.date,through:`${r.date}, ${r.cur}`,first:r.first,
   tile:{v:sg(r.now)+' °C',l:`vs 1991–2020 average on ${r.date}`,s:r.rank==1?`${sg(r.now-r.rec[1])} °C above the previous record for this date (${r.rec[0]})`:`Record for this date: ${sg(r.rec[1])} °C (${r.rec[0]}). Area: 60°S–60°N`,
   spark:A,sparkLabel:`yearly, ${A[0].x}–${A[A.length-1].x}`}}}),

 nino:()=>get('oisst2.1_nino3.4_sst_day.json').then(JSON.parse).then(d=>{const r=daily(d);
  // strength categories as NOAA uses them (weak 0.5, moderate 1.0, strong 1.5, very strong 2.0 °C)
  const a=Math.abs(r.now),str=a>=2?'Very strong ':a>=1.5?'Strong ':a>=1?'Moderate ':'Weak ',rec=r.rank==1?(r.now>0?', warmest on record for this date':''):'';
  const vd=r.now>=.5?`${str}El Niño conditions${rec}`:r.now<=-.5?`${str}La Niña conditions`:'Neutral: neither El Niño nor La Niña';
  return{src:'NOAA OISST',vd,now:sg(r.now)+' °C',date:r.date,through:`${r.date}, ${r.cur}`,
   tile:{v:sg(r.now)+' °C',l:`central Pacific vs 1991–2020, ${r.date}`,s:'Daily value, traditional index. NOAA\u2019s official index averages 3 months and subtracts the warming of the whole tropics, so it reads lower.',spark:r.back(365).map((y,i)=>({x:i,y})),sparkLabel:'last 12 months'}}}),

 // ocean heat: 0-2000 m by quarter (latest), 0-700 m by year (long record)
 ohc:()=>Promise.all([get('h22-w0-700m.dat'),...SEAS.map(s=>get(`h22-w0-2000m${s[0]}.dat`))]).then(([y7,...q])=>{
  const Q=[];q.forEach((t,k)=>ncei(t).forEach(r=>Q.push({y:Math.floor(r[0]),s:k,x:Math.floor(r[0])+SEAS[k][2],v:r[1]*10})));Q.sort((a,b)=>a.x-b.x);
  const L=Q[Q.length-1],P=Q.find(o=>o.y==L.y-1&&o.s==L.s),rk=Q.filter(o=>o.v>L.v).length+1,dt=`${SEAS[L.s][1]} ${L.y}`;
  const wm=slope(Q.filter(o=>o.x>L.x-10).map(o=>({x:o.x,y:o.v})))*1e21/31557600/5.1e14;
  const S=ncei(y7).map(r=>({x:Math.floor(r[0]),y:r[1]*10})),s98=S.find(p=>p.x==1998),sL=S[S.length-1];
  const vd=rk==1?`Highest on record (since ${Q[0].y})`:rk<=4?`Among the highest on record (since ${Q[0].y})`:'Far above the 1955–2006 average';
  return{src:'NOAA NCEI',vd,value:sg(L.v,0)+' ZJ',date:dt,through:dt,d12:P?(L.v-P.v).toFixed(0)+' ZJ':'–',energyX:P?Math.round((L.v-P.v)/0.6)+' times':'–',rate:wm.toFixed(2)+' W/m²',rateNum:wm,winFrom:L.x-10,winTo:L.x,winLabel:`${SEAS[L.s][1]} ${L.y-10} to ${dt}`,
   since98:(sL.y-s98.y).toFixed(0)+' ZJ',lastY:sL.x,first7:S[0].x,first2:Q[0].y,
   tile:{v:sg(L.v,0)+' ZJ',l:`upper 2000 m vs 1955–2006, ${dt}`,s:`${P?sg(L.v-P.v,0)+' ZJ in 12 months. ':''}The ocean gained heat at ${wm.toFixed(2)} W/m² over the last 10 years. 1 ZJ = 10²¹ joules.`,
   spark:S,sparkLabel:`upper 700 m, ${S[0].x}–${sL.x}`}}}),

 // sea level: NASA-SSH, cm with zero mean over 1993
 sl:()=>get('NASA_SSH_GMSL_INDICATOR.txt').then(t=>deseason(lines(t).map(l=>l.trim().split(/\s+/).map(Number)).filter(p=>p[0]>1990&&Math.abs(p[1])<1000).map(p=>({x:p[0],y:p[1]*10,s:p[2]*10})))).then(D=>{
  const L=D[D.length-1],y12=mean(D.filter(d=>d.x>L.x-1).map(d=>d.y)),y93=mean(D.filter(d=>d.x<1994).map(d=>d.y)),r10=slope(D.filter(d=>d.x>L.x-10)),r0=slope(D.filter(d=>d.x<2003)),f=r10/r0;
  const dt=`${ML[Math.min(11,Math.floor((L.x%1)*12))]} ${Math.floor(L.x)}`,rise=(y12-y93)/10;
  const vd=f>=1.25?`Still rising, about ${f.toFixed(1)}× as fast as in the 1990s`:r10>0?'Still rising':'Not rising over the last 10 years';
  return{src:'NASA',vd,rise:rise.toFixed(1)+' cm',r10:r10.toFixed(1)+' mm',r0:r0.toFixed(1)+' mm',through:dt,
   tile:{v:sg(rise,1)+' cm',l:'since 1993 (last 12 months vs 1993)',s:`Rising ${r10.toFixed(1)} mm per year over the last 10 years, vs ${r0.toFixed(1)} mm per year in 1993–2002`,
   spark:D.filter((d,i)=>i%4==0).map(d=>({x:d.x,y:d.s})),sparkLabel:`${Math.floor(D[0].x)}–${Math.floor(L.x)}`}}}),

 ice:()=>get('N_seaice_extent_daily_v4.0.csv').then(t=>{const r=seaIce(t);
  const sep=Object.keys(r.V).map(Number).map(y=>{const a=[];for(let i=243;i<273;i++)if(r.V[y][i]!=null)a.push(r.V[y][i]);return{x:y,y:a.length>=10?mean(a):null}}).filter(p=>p.y!=null);
  const mn=lowest(r.yrs.filter(y=>r.season(y,273)).map(y=>({y,v:r.ext(y,true)})).filter(p=>p.v!=null)),
        mx=lowest(r.yrs.filter(y=>r.season(y,120)).map(y=>({y,v:r.ext(y,false)})).filter(p=>p.v!=null));
  return{src:'NSIDC',vd:r.vd,an:ab(r.an)+' million km²',extent:r.now.toFixed(2)+' million km²',rank:`${r.rank==1?'lowest':ord(r.rank)+' lowest'} of ${r.n} years for this date`,date:r.date,through:r.through,
   minN:mn.n,minSince:mn.since,minLow:mn.low,minLastY:mn.lastY,minLast:mn.lastRank==1?'the lowest':ord(mn.lastRank)+' lowest',yrsN:mn.count,
   maxLow:mx.low,maxLastY:mx.lastY,maxLast:mx.lastRank==1?'the lowest':ord(mx.lastRank)+' lowest',
   tile:{v:sg(r.an,2)+' M km²',l:`vs 1981–2010, ${r.date}`,s:`Extent ${r.now.toFixed(2)} million km² (5-day average). Satellite record since ${r.first}.`,spark:sep,sparkLabel:`September extent, ${sep[0].x}–${sep[sep.length-1].x}`}}}),

 ant:()=>get('S_seaice_extent_daily_v4.0.csv').then(t=>{const r=seaIce(t),since=r.full.filter(y=>y>=2016),below=since.filter(y=>r.yAn(y)<0).length,low=r.full.reduce((b,y)=>r.yAn(y)<r.yAn(b)?y:b,r.full[0]);
  return{src:'NSIDC',vd:r.vd,an:ab(r.an)+' million km²',extent:r.now.toFixed(2)+' million km²',rank:`${r.rank==1?'lowest':ord(r.rank)+' lowest'} of ${r.n} years for this date`,date:r.date,through:r.through,
   below:below==since.length?`Every one of the ${below} full years`:`${below} of the ${since.length} full years`,low}}),

 // global sea ice: Arctic + Antarctic daily extent added together, yearly averages vs 1981-2010
 glob:()=>Promise.all([get('N_seaice_extent_daily_v4.0.csv'),get('S_seaice_extent_daily_v4.0.csv')]).then(([n,s])=>{const N=seaIce(n),S=seaIce(s),Y={};
  Object.keys(N.V).map(Number).filter(y=>y<N.L.y&&y>1978).forEach(y=>{const a=[];for(let i=0;i<365;i++)if(N.V[y][i]!=null&&S.V[y]&&S.V[y][i]!=null)a.push(N.V[y][i]+S.V[y][i]);if(a.length>150)Y[y]=mean(a)});
  const ys=Object.keys(Y).map(Number),ref=mean(ys.filter(y=>y>=1981&&y<=2010).map(y=>Y[y])),last=ys[ys.length-1],an=Y[last]-ref;
  const R=[...ys].sort((a,b)=>Y[a]-Y[b]),rk=R.indexOf(last)+1;let since=last;for(let j=ys.length-1;j>=0&&Y[ys[j]]<ref;j--)since=ys[j];
  return{src:'NSIDC',vd:an<0?'Below the 1981–2010 average':'Above the 1981–2010 average',an:ab(an)+' million km²',lastY:last,rank:rk==1?'the lowest':ord(rk)+' lowest',low:R[0],since,first:ys[0],through:String(last)}}),

 co2:()=>get('co2_daily_mlo.txt').then(t=>{const D=new Map(),dn=(y,m,d)=>Math.round(Date.UTC(y,m-1,d)/864e5);
  lines(t).forEach(l=>{const p=l.trim().split(/\s+/);if(p.length<5)return;const v=parseFloat(p[4]);if(v>250&&v<700)D.set(dn(+p[0],+p[1],+p[2]),v)});
  const ks=[...D.keys()].sort((a,b)=>a-b),L=ks[ks.length-1],avg=(a,b)=>{const v=[];for(let k=a;k<=b;k++)if(D.has(k))v.push(D.get(k));return v.length>=10?mean(v):null};
  const w=avg(L-29,L),wp=avg(L-394,L-365),w10=avg(L-29-3652,L-3652),ld=new Date(L*864e5),date=`${ML[ld.getUTCMonth()]} ${ld.getUTCDate()}`,yr={};
  ks.forEach(k=>{const y=new Date(k*864e5).getUTCFullYear();(yr[y]=yr[y]||[]).push(D.get(k))});
  const ann=Object.keys(yr).map(Number).filter(y=>yr[y].length>=200&&y<ld.getUTCFullYear()).map(y=>({x:y,y:mean(yr[y])}));
  // yearly growth as on the CO2 page: monthly means, each month compared with the same month a year earlier
  const MM=new Map(),acc=new Map();ks.forEach(k=>{const d=new Date(k*864e5),key=d.getUTCFullYear()*12+d.getUTCMonth(),a=acc.get(key)||[0,0];a[0]+=D.get(k);a[1]++;acc.set(key,a)});
  acc.forEach(([s,n],key)=>{if(n>=10)MM.set(key,s/n)});
  const cy=ld.getUTCFullYear(),gr={};for(let y=cy-11;y<=cy;y++){const d=[];for(let m=0;m<12;m++){const a=MM.get(y*12+m),b=MM.get((y-1)*12+m);if(a!=null&&b!=null)d.push(a-b)}if(d.length>=6)gr[y]=mean(d)}
  const done=Object.keys(gr).map(Number).filter(y=>y<cy).slice(-10),rate10=done.length?mean(done.map(y=>gr[y])):null;
  const up=gr[cy]!=null?gr[cy]:null,vd=up==null?'Higher than at any time in human history':up>0?`Still climbing: up ${up.toFixed(1)} ppm over the past year`:'No rise over the past year';
  return{src:'NOAA Mauna Loa',vd,now:w.toFixed(1)+' ppm',date,through:`${date}, ${ld.getUTCFullYear()}`,pct:Math.round((w/280-1)*100)+'%',x:(w/280).toFixed(2)+'×',
   rate:rate10!=null?rate10.toFixed(2)+' ppm':'–',up:up==null?'–':up.toFixed(2)+' ppm',
   tile:{v:w.toFixed(1)+' ppm',l:`30-day average to ${date}`,s:`About ${(w/280).toFixed(2)}× the pre-industrial level of about 280 ppm`,spark:ann,sparkLabel:`yearly, ${ann[0].x}–${ann[ann.length-1].x}`}}}),

 ch4:()=>Promise.all([get('ch4_mm_gl.txt'),get('ch4_gr_gl.txt')]).then(([a,b])=>{
  const M=lines(a).map(l=>l.trim().split(/\s+/).map(Number)).filter(r=>r.length>=6&&r[3]>0),G=lines(b).map(l=>l.trim().split(/\s+/).map(Number)).filter(r=>r.length>=2&&r[0]>1900);
  const L=M[M.length-1],g=G[G.length-1],x=(L[5]/729).toFixed(1),dt=`${ML[L[1]-1]} ${L[0]}`;
  return{src:'NOAA',vd:g[1]>0?`${x}× pre-industrial, and still rising`:`${x}× pre-industrial`,now:L[3].toFixed(0)+' ppb',x:x+'×',rise:g[1].toFixed(1)+' ppb',riseYear:g[0],date:dt,through:dt,
   tile:{v:L[3].toFixed(0)+' ppb',l:`global monthly mean, ${dt}`,s:`Rose ${g[1].toFixed(1)} ppb in ${g[0]}. Pre-industrial: about 729 ppb.`,spark:M.map(r=>({x:r[2],y:r[5]})),sparkLabel:`trend, ${M[0][0]}–${L[0]}`}}}),

 // sun: WDC-SILSO sunspot number, monthly and 13-month smoothed; cycles found from the smoothed minima (as on sun.html)
 sun:()=>Promise.all([get('SN_m_tot_V2.0.csv'),get('SN_ms_tot_V2.0.csv')]).then(([a,b])=>{
  const P=t=>t.split(/\r?\n/).map(l=>l.split(';').map(s=>s.trim())).filter(p=>p.length>=4&&+p[0]>1700&&+p[3]>=0).map(p=>({y:+p[0],m:+p[1],x:+p[2],v:+p[3],prov:p[6]==='0'}));
  const M=P(a),S=P(b),L=M[M.length-1],SL=S[S.length-1],lb=r=>`${ML[r.m-1]} ${r.y}`;
  const mins=[];S.forEach((r,i)=>{const w=S.slice(Math.max(0,i-60),i+61);if(i>=12&&i<S.length-12&&r.v===Math.min(...w.map(q=>q.v))&&(!mins.length||i-mins[mins.length-1]>84))mins.push(i)});
  const i0=mins[mins.length-1],seg=S.slice(i0),pk=seg.reduce((q,r)=>r.v>q.v?r:q,seg[0]),done=seg.indexOf(pk)<seg.length-6;
  const c25=mins.findIndex(i=>S[i].y===2019||S[i].y===2020),n=c25<0?null:25+(mins.length-1-c25),cname=n?`Solar cycle ${n}`:'The current solar cycle';
  const yAgo=S[S.length-13],trend=SL.v<yAgo.v-5?'declining':SL.v>yAgo.v+5?'rising':'steady';
  const vd=done?`${cname} is past its peak; activity ${trend}`:`${cname}: activity ${trend}, highest so far ${pk.v.toFixed(0)}`;
  return{src:'WDC-SILSO',vd,now:L.v.toFixed(0),date:lb(L)+(L.prov?' (provisional)':''),through:lb(L),smooth:SL.v.toFixed(0),sdate:lb(SL),cycle:cname,peak:pk.v.toFixed(0),peakDate:lb(pk),
   tile:{v:L.v.toFixed(0),l:`sunspot number, ${lb(L)}${L.prov?' (provisional)':''}`,s:`13-month smoothed: ${SL.v.toFixed(0)} (${lb(SL)}). ${done?'Cycle maximum':'Highest so far'}: ${pk.v.toFixed(0)} (${lb(pk)}).`,
    spark:S.filter(r=>r.y>=1976).map(r=>({x:r.x,y:r.v})),sparkLabel:`smoothed, ${1976}–${SL.y}`}}}),

 // PDO: NOAA NCEI index, one row per year with 12 monthly values (99.99 = missing)
 pdo:()=>get('pdo_ncei.dat').then(t=>{const M=[];t.split(/\r?\n/).forEach(l=>{const p=l.trim().split(/\s+/);if(!/^\d{4}$/.test(p[0]))return;p.slice(1,13).forEach((v,k)=>{const x=+v;if(isFinite(x)&&Math.abs(x)<99)M.push({y:+p[0],m:k+1,x:+p[0]+(k+.5)/12,v:x})})});
  const L=M[M.length-1],dt=`${ML[L.m-1]} ${L.y}`,a12=mean(M.slice(-12).map(r=>r.v));let n=0;for(let i=M.length-1;i>=0&&Math.sign(M[i].v)===Math.sign(L.v);i--)n++;
  const ph=L.v>=1?'Strongly positive (warm) phase':L.v>0?'Positive (warm) phase':L.v<=-1?'Strongly negative (cool) phase':'Negative (cool) phase';
  const run=M.map((r,i)=>i<11?null:{x:r.x,y:mean(M.slice(i-11,i+1).map(q=>q.v))}).filter(p=>p&&p.x>=L.y-40);
  return{src:'NOAA NCEI',vd:`${ph}, ${n} month${n==1?'':'s'} in a row`,now:sg(L.v),a12:sg(a12),months:String(n),sign:L.v<0?'negative':'positive',date:dt,through:dt,
   tile:{v:sg(L.v),l:`PDO index, ${dt}`,s:`12-month average ${sg(a12)}. Beyond ±1 counts as strong.`,spark:run,sparkLabel:`12-month average, ${Math.floor(run[0].x)}–${L.y}`}}}),

 eei:()=>get('ceres_ebaf_global.csv').then(t=>{const R=t.trim().split(/\r?\n/).slice(1).map(l=>l.split(',')).filter(p=>/^\d{4}-\d{2}$/.test(p[0])).map(p=>({m:p[0],n:+p[4]}));
  const n=R.map(r=>r.n),l12=mean(n.slice(-12)),l48=mean(n.slice(-48)),f48=mean(n.slice(0,48)),[y,m]=R[R.length-1].m.split('-'),dt=`${ML[m-1]} ${y}`,y0=+R[0].m.slice(0,4);
  const run=n.map((_,i)=>i<11?null:{x:i,y:mean(n.slice(i-11,i+1))}).filter(Boolean);
  const vd=l12>0?(l48/f48>=1.5?`Earth is gaining heat, about ${(l48/f48).toFixed(1)}× as fast as in the early 2000s (4-year averages)`:'Earth is gaining heat: more energy in than out'):'Earth is not gaining heat right now';
  return{src:'NASA CERES',vd,l12:ab(l12)+' W/m²',x:(l48/f48).toFixed(1)+'×',l48:ab(l48)+' W/m²',f48:ab(f48)+' W/m²',early:`${y0}–${y0+3}`,date:dt,through:dt,
   tile:{v:sg(l12,2)+' W/m²',l:`average over the 12 months to ${dt}`,s:`48-month average ${sg(l48,2)} W/m², vs ${sg(f48,2)} W/m² in the first 4 years of the record (${y0}–${y0+3})`,spark:run,sparkLabel:`12-month mean, ${R[11].m.slice(0,4)}–${y}`}}})
};

const NAMES={air:'air temperature',sst:'sea surface',nino:'El Niño',ohc:'ocean heat',sl:'sea level',ice:'Arctic sea ice',ant:'Antarctic sea ice',co2:'CO₂',ch4:'methane',eei:'energy imbalance',glob:'global sea ice',sun:'solar cycle',pdo:'PDO'};
const cache={};
function getId(id){if(!LOAD[id])return Promise.reject(new Error('unknown indicator '+id));return cache[id]||(cache[id]=LOAD[id]())}

// fill <span data-k="id.key"> elements; returns a promise that settles when all are done
function fill(root){
 const els=[...(root||document).querySelectorAll('[data-k]')],ids=[...new Set(els.map(e=>e.dataset.k.split('.')[0]))];
 return Promise.allSettled(ids.map(id=>{const mine=els.filter(e=>e.dataset.k.split('.')[0]==id);
  return getId(id).then(s=>mine.forEach(e=>{const v=s[e.dataset.k.slice(id.length+1)];e.textContent=v==null?'–':v}),
   err=>{console.error(err);mine.forEach(e=>{e.textContent='(not available right now)';e.classList.add('na')});throw err})}))}

window.EI={get:getId,fill,NAMES};
})();
