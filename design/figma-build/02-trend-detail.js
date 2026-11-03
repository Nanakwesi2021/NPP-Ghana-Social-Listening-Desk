// use_figma script · fileKey V3AeKWDIKpfXyd5ET413US · skillNames: resource:figma-use,resource:figma-generate-design
// Adds the "Platform breakdown row" component to the Patterns board (Design system page),
// then builds "02 · Trend detail — Electricity tariff increase" on the Desktop page at x 1540.
// Written 2026-11-03; not yet run (Figma MCP Starter limit reached).

const all=await figma.variables.getLocalVariablesAsync();const V={},VID={};for(const v of all){V[v.name]=v;VID[v.id]=v}
const res=v=>{let val=Object.values(v.valuesByMode)[0];while(val&&val.type==='VARIABLE_ALIAS'){val=Object.values(VID[val.id].valuesByMode)[0]}return {r:val.r,g:val.g,b:val.b}};
const paint=(t,o=1)=>figma.variables.setBoundVariableForPaint({type:'SOLID',color:res(V[t]),opacity:o},'color',V[t]);
const TS={}; for (const s of await figma.getLocalTextStylesAsync()) TS[s.name]=s;
await Promise.all([['Archivo','ExtraBold'],['Archivo','Bold'],['Archivo Narrow','Bold'],['IBM Plex Sans','Regular'],['IBM Plex Sans','Medium'],['IBM Plex Sans','SemiBold']].map(([family,style])=>figma.loadFontAsync({family,style})));
const ICON_IDS={"flag":"4:198","chevron-left":"4:133","external-link":"4:162","check":"4:284"};
const IC={}; await Promise.all(Object.entries(ICON_IDS).map(async([n,id])=>{IC[n]=await figma.getNodeByIdAsync(id)}));
const [mastD,railSet,btnSet,selSet,chipSet,statusSet,evSet,caseSet,patBoard]=await Promise.all(['8:113','8:453','5:129','6:143','6:156','5:268','11:691','10:637','10:364'].map(id=>figma.getNodeByIdAsync(id)));
function I(name,size=16,tok='color/icon/default'){const i=IC[name].createInstance();i.resize(size,size);const w=Math.max(1.25,Math.round(200*size/24)/100);for(const n of i.findAll(n=>n.type==='VECTOR')){if(n.strokes.length){n.strokes=[paint(tok)];n.strokeWeight=w}}i.name='Icon/'+name;return i}
async function T(s,style,tok='color/text/primary',name){const t=figma.createText();await t.setTextStyleIdAsync(TS[style].id);t.characters=s;t.fills=[paint(tok)];t.name=name||s.slice(0,28);return t}
const AL=(dir,o={})=>{const f=figma.createAutoLayout(dir);f.fills=o.fill?[paint(o.fill,o.fo??1)]:[];if(o.gap!=null)f.itemSpacing=o.gap;if(o.px!=null){f.paddingLeft=f.paddingRight=o.px}if(o.py!=null){f.paddingTop=f.paddingBottom=o.py}f.counterAxisAlignItems=o.align||'CENTER';if(o.r!=null)f.cornerRadius=o.r;if(o.name)f.name=o.name;if(o.stroke){f.strokes=[paint(o.stroke)];f.strokeWeight=1}return f};
const pick=(set,q)=>set.children.find(c=>Object.entries(q).every(([k,v])=>c.name.includes(`${k}=${v}`)));
function fillT(p,t){p.appendChild(t);t.textAutoResize='HEIGHT';t.layoutSizingHorizontal='FILL';return t}
function fill(p,c){p.appendChild(c);c.layoutSizingHorizontal='FILL';return c}
function fixW(n,w){n.resize(w,n.height);n.layoutSizingHorizontal='FIXED'}
function bottomRule(f){f.strokes=[paint('color/border/default')];f.strokeTopWeight=0;f.strokeLeftWeight=0;f.strokeRightWeight=0;f.strokeBottomWeight=1;f.strokeAlign='INSIDE'}
function btn(label,{style='Secondary',state='Default',size='M',icon=null}={}){const b=pick(btnSet,{Style:style,State:state,Size:size}).createInstance();const p={'Label#5:0':label,'Show icon#5:25':!!icon};if(icon)p['Glyph#5:50']=IC[icon].id;b.setProperties(p);b.name='Button/'+label;return b}
function panel(name,w){const p=AL('VERTICAL',{gap:0,align:'MIN',fill:'color/bg/surface',r:4,stroke:'color/border/default',name});p.resize(w,100);p.counterAxisSizingMode='FIXED';p.primaryAxisSizingMode='AUTO';p.clipsContent=true;return p}
async function phead(p,title,sub){const h=AL('VERTICAL',{gap:2,align:'MIN',name:'Panel header'});h.paddingTop=18;h.paddingBottom=12;h.paddingLeft=h.paddingRight=20;fill(p,h);h.appendChild(await T(title,'Heading/H3'));if(sub){const s=await T(sub,'Caption','color/text/muted');fillT(h,s)}return h}

// ---- component: Platform breakdown row (Design system page) ----
const sec=AL('VERTICAL',{gap:12,align:'MIN',name:'Section / Platform breakdown row'});patBoard.appendChild(sec);sec.appendChild(await T('Platform breakdown row','Heading/H2'));
const sd=await T('Count per platform inside the current window. A quiet platform shows 0 with a current check; a platform the desk cannot see shows a dash and its access status, so silence and missing coverage never look the same.','Body/S','color/text/muted');sec.appendChild(sd);sd.resize(900,sd.height);sd.textAutoResize='HEIGHT';
const pc=figma.createComponent();pc.name='Platform breakdown row';pc.layoutMode='VERTICAL';pc.counterAxisSizingMode='FIXED';pc.resize(376,40);pc.primaryAxisSizingMode='AUTO';pc.itemSpacing=6;pc.paddingTop=pc.paddingBottom=10;pc.fills=[];bottomRule(pc);sec.appendChild(pc);
const r1=AL('HORIZONTAL',{gap:12,name:'Count row'});fill(pc,r1);
const pn=await T('News','Body/S Strong','color/text/primary','Platform');r1.appendChild(pn);pn.textAutoResize='HEIGHT';fixW(pn,92);
const track=figma.createFrame();track.name='Track';track.resize(200,8);track.cornerRadius=2;track.fills=[paint('color/bg/subtle')];track.clipsContent=true;r1.appendChild(track);track.layoutGrow=1;
const bar=figma.createRectangle();bar.name='Bar';bar.resize(117,8);bar.fills=[paint('color/chart/current')];track.appendChild(bar);bar.x=0;bar.y=0;
const pcnt=await T('7','Data/Count M','color/text/primary','Count');pcnt.textAlignHorizontal='RIGHT';r1.appendChild(pcnt);pcnt.textAutoResize='HEIGHT';fixW(pcnt,36);
const r2=AL('HORIZONTAL',{gap:8,name:'Status row'});fill(pc,r2);
const ps=pick(statusSet,{State:'Current'}).createInstance();ps.name='Status';r2.appendChild(ps);ps.isExposedInstance=true;
const pdt=await T('3 outlets · checked 10:35 GMT','Caption','color/text/muted','Detail');fillT(r2,pdt);
const kP=pc.addComponentProperty('Platform','TEXT','News'),kC=pc.addComponentProperty('Count','TEXT','7'),kD=pc.addComponentProperty('Detail','TEXT','3 outlets · checked 10:35 GMT');
pn.componentPropertyReferences={characters:kP};pcnt.componentPropertyReferences={characters:kC};pdt.componentPropertyReferences={characters:kD};
pc.description='Per-platform count for a trend window. Bar width = count / topic total. Django: templates/desk/partials/_platform_row.html.';

// ---- screen ----
const page=await figma.getNodeByIdAsync('3:2');await figma.setCurrentPageAsync(page);
const f=figma.createFrame();f.name='02 · Trend detail — Electricity tariff increase';f.x=1540;f.y=0;page.appendChild(f);f.resize(1440,1024);f.layoutMode='VERTICAL';f.primaryAxisSizingMode='AUTO';f.counterAxisSizingMode='FIXED';f.fills=[paint('color/bg/page')];f.clipsContent=true;
const m=mastD.createInstance();f.appendChild(m);m.name='Masthead';
const body=AL('HORIZONTAL',{gap:0,align:'MIN',name:'Body'});fill(f,body);
const rail=pick(railSet,{Current:'Trends'}).createInstance();rail.name='Rail';body.appendChild(rail);rail.layoutSizingVertical='FILL';
const main=AL('VERTICAL',{gap:20,align:'MIN',name:'Main'});main.paddingTop=24;main.paddingBottom=48;main.paddingLeft=main.paddingRight=32;body.appendChild(main);main.layoutGrow=1;main.layoutSizingHorizontal='FILL';
// breadcrumb
const bc=AL('HORIZONTAL',{gap:6,name:'Breadcrumb'});main.appendChild(bc);bc.appendChild(I('chevron-left',16,'color/icon/brand'));
const b1=await T('Desk overview','Label/S','color/text/link','Crumb/Overview');b1.textDecoration='UNDERLINE';bc.appendChild(b1);bc.appendChild(await T('/','Label/S','color/text/muted'));
bc.appendChild(await T('Trending Now','Label/S','color/text/muted'));bc.appendChild(await T('/','Label/S','color/text/muted'));bc.appendChild(await T('Electricity tariff increase','Label/S','color/text/primary'));
// header
const hdr=AL('HORIZONTAL',{gap:24,align:'MAX',name:'Page header'});fill(main,hdr);hdr.primaryAxisAlignItems='SPACE_BETWEEN';
const hl=AL('VERTICAL',{gap:4,align:'MIN',name:'Title'});hdr.appendChild(hl);hl.appendChild(await T('Electricity tariff increase','Heading/H1'));
hl.appendChild(await T('Topic: Utilities and cost of living · Subject: Government, Energy regulator · Window 09:37–10:37 GMT','Body/S','color/text/muted','Meta'));
const ha=AL('HORIZONTAL',{gap:8,name:'Actions'});hdr.appendChild(ha);ha.appendChild(btn('Export links',{style:'Tertiary',icon:'external-link'}));ha.appendChild(btn('Flag topic for review',{icon:'flag'}));
// comparison
const cmp=AL('HORIZONTAL',{gap:32,align:'MIN',fill:'color/bg/surface',r:4,stroke:'color/border/default',name:'Comparison'});cmp.paddingTop=cmp.paddingBottom=20;cmp.paddingLeft=cmp.paddingRight=24;fill(main,cmp);
const cl=AL('VERTICAL',{gap:6,align:'MIN',name:'Plain language'});cmp.appendChild(cl);cl.layoutGrow=1;cl.layoutSizingHorizontal='FILL';
fillT(cl,await T('12 distinct mentions this hour, up from 4.','Heading/Comparison','color/text/primary','Comparison sentence'));
fillT(cl,await T('An increase of 8 on the previous hour. Observed on News (7 items from 3 outlets) and X (5 posts from 4 accounts). X collection has been delayed since 09:40 GMT, so the X count may be low.','Body/M','color/text/secondary','Comparison detail'));
const dl=AL('HORIZONTAL',{gap:0,align:'MIN',name:'Windows'});cmp.appendChild(dl);
for(const [lab,win,val,tok] of [['This hour','09:37–10:37','12','color/text/primary'],['Last hour','08:37–09:37','4','color/text/secondary'],['Change','','+8','color/text/link']]){
 const c=AL('VERTICAL',{gap:2,align:'MIN',name:'Window/'+lab});c.paddingLeft=c.paddingRight=20;c.strokes=[paint('color/border/default')];c.strokeLeftWeight=1;c.strokeRightWeight=0;c.strokeTopWeight=0;c.strokeBottomWeight=0;dl.appendChild(c);
 c.appendChild(await T(lab,'Label/S','color/text/muted'));const v=await T(val,'Heading/H1',tok,'Value');c.appendChild(v);c.appendChild(await T(win?win+' GMT':'distinct items','Caption','color/text/muted'))}
// filters
const fb=AL('HORIZONTAL',{gap:8,name:'Filters'});fill(main,fb);
fb.appendChild(await T('Platform','Label/S','color/text/muted'));
for(const [lab,cnt,sel] of [['All','12',true],['News','7',false],['X','5',false],['YouTube','0',false],['Facebook','0',false]]){const c=pick(chipSet,{State:sel?'Selected':'Default'}).createInstance();c.setProperties({'Label#6:22':lab,'Count#6:26':cnt});c.name='Chip/'+lab;fb.appendChild(c)}
const sp1=figma.createFrame();sp1.fills=[];sp1.resize(12,8);sp1.name='Gap';fb.appendChild(sp1);
for(const [a,b] of [['Topic','Electricity tariff increase'],['Subject','All subjects']]){const s=pick(selSet,{State:'Default'}).createInstance();s.setProperties({'Field label#6:14':a,'Value#6:18':b});s.name='Filter/'+a;fb.appendChild(s)}
const grow=figma.createFrame();grow.fills=[];grow.resize(10,8);grow.name='Spacer';fb.appendChild(grow);grow.layoutGrow=1;
fb.appendChild(await T('Showing 5 of 12 items','Caption','color/text/muted'));
// row A
const rowA=AL('HORIZONTAL',{gap:24,align:'MIN',name:'Row A'});fill(main,rowA);
const tl=panel('Timeline',848);rowA.appendChild(tl);
const tlh=AL('HORIZONTAL',{gap:16,name:'Panel header'});tlh.paddingTop=18;tlh.paddingBottom=8;tlh.paddingLeft=tlh.paddingRight=20;fill(tl,tlh);tlh.primaryAxisAlignItems='SPACE_BETWEEN';
tlh.appendChild(await T('Last two hours · 10-minute buckets','Heading/H3'));
const lg=AL('HORIZONTAL',{gap:16,name:'Legend'});tlh.appendChild(lg);
for(const [tok,lab,o] of [['color/chart/previous','08:37–09:37 · 4',1],['color/chart/current','09:37–10:37 · 12',1],['color/bg/warning','X partial from 09:40',1]]){const it=AL('HORIZONTAL',{gap:6,name:'Key'});lg.appendChild(it);const sw=figma.createRectangle();sw.resize(12,12);sw.cornerRadius=2;sw.fills=[paint(tok,o)];if(tok==='color/bg/warning'){sw.strokes=[paint('color/border/warning')];sw.strokeWeight=1}it.appendChild(sw);it.appendChild(await T(lab,'Caption','color/text/secondary'))}
const ch=figma.createFrame();ch.name='Chart';ch.fills=[];ch.resize(808,236);ch.clipsContent=false;const cw=AL('VERTICAL',{name:'Chart wrap'});cw.paddingLeft=cw.paddingRight=20;cw.paddingBottom=16;fill(tl,cw);cw.appendChild(ch);
const PX=36,PW=808-PX-8,TOP=34,BASE=196,UNIT=48;const step=PW/12;
for(let g=0;g<=3;g++){const y=BASE-g*UNIT;const ln=figma.createRectangle();ln.name='Grid '+g;ln.resize(PW,1);ln.fills=[paint('color/chart/grid')];ch.appendChild(ln);ln.x=PX;ln.y=y;const lt=await T(String(g),'Caption','color/text/muted','Y '+g);ch.appendChild(lt);lt.x=PX-18;lt.y=y-8}
const vals=[0,1,0,1,1,1,1,1,2,3,2,3];
for(let i=0;i<12;i++){const v=vals[i];const x=PX+i*step+(step-36)/2;if(v>0){const b=figma.createRectangle();b.name=`Bar ${i}`;b.resize(36,v*UNIT);b.topLeftRadius=2;b.topRightRadius=2;b.fills=[paint(i<6?'color/chart/previous':'color/chart/current')];ch.appendChild(b);b.x=x;b.y=BASE-v*UNIT}
 const vl=await T(String(v),'Label/S',i<6?'color/text/muted':'color/text/primary','Value '+i);ch.appendChild(vl);vl.textAlignHorizontal='CENTER';vl.textAutoResize='HEIGHT';vl.resize(36,vl.height);vl.x=x;vl.y=BASE-v*UNIT-18}
const times=['08:37','08:57','09:17','09:37','09:57','10:17','10:37'];for(let k=0;k<7;k++){const t=await T(times[k],'Caption','color/text/muted','X '+times[k]);ch.appendChild(t);t.x=PX+k*2*step-16;t.y=BASE+8}
const bd=figma.createRectangle();bd.name='Window boundary';bd.resize(1,BASE-TOP+8);bd.fills=[paint('color/border/strong')];ch.appendChild(bd);bd.x=PX+6*step;bd.y=TOP-8;
const bdl=await T('Window boundary 09:37','Caption','color/text/muted','Boundary label');ch.appendChild(bdl);bdl.x=PX+6*step-bdl.width-6;bdl.y=TOP-10;
const xs=PX+(6+3/10)*step;const band=figma.createRectangle();band.name='X partial band';band.resize(PX+PW-xs,6);band.fills=[paint('color/bg/warning')];band.strokes=[paint('color/border/warning')];band.strokeWeight=1;ch.appendChild(band);band.x=xs;band.y=TOP-14;
const bl=await T('X partial from 09:40','Caption','color/text/warning','Band label');ch.appendChild(bl);bl.x=xs+6;bl.y=0;
// platform breakdown
const pp=panel('Where it was observed',416);rowA.appendChild(pp);await phead(pp,'Where it was observed','Distinct items in 09:37–10:37 GMT · total 12');
const pl=AL('VERTICAL',{gap:0,align:'MIN',name:'Rows'});pl.paddingLeft=pl.paddingRight=20;pl.paddingBottom=12;fill(pp,pl);
const PR=[['News','7',7,'Current','3 outlets · checked 10:35 GMT'],['X','5',5,'Delayed','4 accounts · last check 09:40 GMT'],['YouTube','0',0,'Current','Checked 10:30 GMT · no mentions'],['Facebook','—',0,'Manual links','No links submitted this hour'],['TikTok','—',0,'Awaiting access','Not collected · research access pending'],['Instagram, Threads','—',0,'Awaiting access','Not collected'],['WhatsApp','1 tip',0,'Tips','Tips are not counted in trends']];
for(const [p,c,n,st,d] of PR){const r=pc.createInstance();r.name='Platform/'+p;fill(pl,r);r.setProperties({[kP]:p,[kC]:c,[kD]:d});r.findOne(x=>x.type==='INSTANCE'&&x.name==='Status').setProperties({State:st});const b=r.findOne(x=>x.type==='RECTANGLE'&&x.name==='Bar');const trk=r.findOne(x=>x.type==='FRAME'&&x.name==='Track');if(n===0){b.visible=false}else{b.resize(Math.round(trk.width*n/12),8)}}
// row B
const rowB=AL('HORIZONTAL',{gap:24,align:'MIN',name:'Row B'});fill(main,rowB);
const ip=panel('Representative items',848);rowB.appendChild(ip);await phead(ip,'Representative items','Chosen for spread of source and language. Original wording first; reviewed translations follow.');
const EV=[
 {kind:'Item',plat:'News',src:'Coastline News',time:'10:12 GMT',lang:'English',ex:'“Regulator publishes quarterly tariff adjustment; new rates take effect on 1 December.”',tr:null,foot:'Also carried by 2 outlets · grouped as 1 item'},
 {kind:'Claim',plat:'X',src:'@AccraVoices',time:'10:21 GMT',lang:'Ghanaian Pidgin',ex:'“Light bill go up from today o! Buy your prepaid now before dem change am.”',tr:'“The electricity bill goes up from today! Buy your prepaid credit now before they change it.”',foot:'14 grouped copies on X · counted once · first seen 10:21 GMT'},
 {kind:'Item',plat:'X',src:'@KumasiWatch',time:'10:26 GMT',lang:'English',ex:'“Second tariff rise this year and nobody has explained it. Who is speaking for ordinary customers?”',tr:null,foot:'1 post · 3 replies observed'},
 {kind:'Item',plat:'X',src:'@Ohemaa_Speaks',time:'10:29 GMT',lang:'Twi',ex:'“Kanea ka no bɛkɔ soro ɛnnɛ anaa? Obiara nnim.”',tr:'“Is the electricity bill going up today? Nobody knows.”',foot:'1 post · translation reviewed by K. Mensah'},
 {kind:'Item',plat:'News',src:'Kumasi Courier',time:'10:30 GMT',lang:'English',ex:'“Party spokespeople trade words over the timing of the tariff adjustment.”',tr:null,foot:'1 item · quotes both the governing party and the NPP'}];
const evIds=[];
for(const d of EV){const e=pick(evSet,{Kind:d.kind}).createInstance();e.name='Item/'+d.src;fill(ip,e);
 e.setProperties({'Account or outlet#11:42':d.src,'Time#11:45':d.time,'Language#11:48':d.lang,'Excerpt#11:51':d.ex,'Translation#11:54':d.tr||'','Show translation#11:57':!!d.tr,'Grouping#11:60':d.foot});
 e.findOne(x=>x.type==='INSTANCE'&&x.name==='Platform').setProperties({'Label#5:75':d.plat});evIds.push(e.id)}
const ipf=AL('HORIZONTAL',{name:'Panel footer'});ipf.paddingTop=ipf.paddingBottom=14;ipf.paddingLeft=ipf.paddingRight=20;fill(ip,ipf);const va=await T('View all 12 items','Label/S','color/text/link');va.textDecoration='UNDERLINE';ipf.appendChild(va);
const rc=AL('VERTICAL',{gap:24,align:'MIN',name:'Side column'});rowB.appendChild(rc);fixW(rc,416);
const lp=panel('Open issue from this topic',416);fill(rc,lp);await phead(lp,'Open issue from this topic');
const ci=pick(caseSet,{State:'Default'}).createInstance();ci.name='Case/ISS-0412';fill(lp,ci);
ci.setProperties({'Case ID#10:60':'Government · ISS-0412','Claim#10:64':'“The new electricity tariff takes effect today.”','Why#10:68':'Why now: spreading inside the fastest-rising topic; customers may act on a wrong date today.','Show first report#10:76':false,'Owner#10:80':'Unassigned','Due#10:84':'Due 10:50 GMT','Next#10:88':'Next: assign a reviewer and compare with the dated notice.','Show decision#10:96':false});
ci.findOne(x=>x.type==='INSTANCE'&&x.name==='Owner avatar').setProperties({Tone:'Unassigned'});
const wp=panel('Why it rose',416);fill(rc,wp);await phead(wp,'Why it rose');
const wl=AL('VERTICAL',{gap:10,align:'MIN',name:'Sequence'});wl.paddingLeft=wl.paddingRight=20;wl.paddingBottom=18;fill(wp,wl);
for(const [t,s] of [['10:12','Coastline News reports the quarterly adjustment, effective 1 December.'],['10:21','One X post says the tariff starts today. Its 14 copies count as one item.'],['10:26–10:30','Comment on X and in news, including both parties’ spokespeople.']]){const r=AL('HORIZONTAL',{gap:12,align:'MIN',name:'Step '+t});fill(wl,r);const tt=await T(t,'Label/S','color/text/muted');r.appendChild(tt);tt.textAutoResize='HEIGHT';fixW(tt,72);fillT(r,await T(s,'Body/S','color/text/secondary'))}
fillT(wl,await T('Rule: +8 distinct items on the previous hour across 2 platforms (News, X). Ranked first by increase.','Caption','color/text/muted','Rule'));
return {frame:f.id,platformRow:pc.id,crumb:b1.id,claimItem:evIds[1],linkedCase:ci.id,rail:rail.id,shot:await f.screenshot({scale:0.5})};
