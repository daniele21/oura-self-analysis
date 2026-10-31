/* Private Oura dashboard: all health data stays in memory and is never cached. */
"use strict";
const state = { tab:"today", days:30, metric:"hrv_ms", data:null, loading:false };
const root = document.getElementById("view-root");
const notice = document.getElementById("notice");
const spinner = document.getElementById("load-state");
const labels = {
  today:["La tua panoramica","Una lettura chiara dei segnali che contano davvero.","PANORAMICA PERSONALE","PANORAMICA"],
  trends:["I tuoi trend","Osserva l'andamento nel tempo, senza dare peso a una sola notte.","LETTURA LONGITUDINALE","TREND"],
  insights:["Insight e contesto","Osservazioni con misure, limiti ed evidenze scientifiche.","EVIDENZE PERSONALI","INSIGHT"],
  training:["Allenamento e recupero","Cosa mostrano i dati dopo le giornate con attività.","MOVIMENTO E RECUPERO","ALLENAMENTI"]
};
const measureLabels = {
  mean_sleep_hours:"Durata media sonno (h)",n_nights:"Notti considerate",
  bedtime_sd_minutes:"Variabilità orari (min)",
  hrv_recent_median_ms:"HRV mediana 7g (ms)",hrv_previous28_median_ms:"HRV baseline 28g (ms)",
  hrv_change_pct:"HRV vs baseline (%)",rhr_recent_median_bpm:"FC minima mediana 7g (bpm)",
  rhr_previous28_median_bpm:"FC minima baseline 28g (bpm)",rhr_change_bpm:"FC minima vs baseline (bpm)",
  next_day_hrv_after_workout_median_ms:"HRV dopo workout (ms)",
  next_day_hrv_without_workout_median_ms:"HRV altri giorni (ms)",
  difference_ms:"Differenza (ms)",n_post_training:"Notti dopo workout",n_other:"Notti di confronto",
  observed_days:"Giorni osservati",calendar_days:"Giorni nel periodo",
  workout_history_available:"Storico allenamenti disponibile"
};
const metrics = [
  {key:"hrv_ms",label:"HRV",unit:"ms",tone:"mint",digits:0},
  {key:"rhr_bpm",label:"FC minima",unit:"bpm",tone:"blue",digits:0},
  {key:"sleep_minutes",label:"Sonno",unit:"h",tone:"mint",digits:1,hours:true},
  {key:"sleep_score",label:"Sleep Score",unit:"pt",tone:"blue",digits:0},
  {key:"readiness_score",label:"Readiness",unit:"pt",tone:"mint",digits:0},
  {key:"steps",label:"Passi",unit:"",tone:"blue",digits:0}
];
const svgNs = "http://www.w3.org/2000/svg";
function e(tag,cls,text){
  const node=document.createElement(tag);
  if(cls)node.className=cls;
  if(text!==undefined && text!==null)node.textContent=String(text);
  return node;
}
function icon(id){
  const svg=document.createElementNS(svgNs,"svg");
  svg.setAttribute("aria-hidden","true");
  const use=document.createElementNS(svgNs,"use");
  use.setAttribute("href","#i-"+id);
  svg.append(use);
  return svg;
}
function a(parent,...children){children.forEach(n=>{if(n!==null && n!==undefined)parent.append(n)});return parent}
function num(n){return typeof n==="number" && Number.isFinite(n)?n:null}
function format(n,d=0){
  if(n===null || n===undefined || !Number.isFinite(Number(n)))return "—";
  return new Intl.NumberFormat("it-IT",{maximumFractionDigits:d}).format(Number(n));
}
function duration(n){
  if(num(n)===null)return "—";
  const minutes=Math.round(n);
  return Math.floor(minutes/60)+"h "+String(minutes%60).padStart(2,"0")+"m";
}
function parseDay(s){return new Date(s+"T12:00:00Z")}
function shortDate(day){
  if(!day)return "—";
  const dt=parseDay(day);
  return Number.isNaN(dt.getTime())?"—":new Intl.DateTimeFormat("it-IT",{day:"numeric",month:"short",timeZone:"UTC"}).format(dt);
}
function fullDate(day){
  if(!day)return "Nessuna data";
  return new Intl.DateTimeFormat("it-IT",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}).format(parseDay(day));
}
function daysArray(n,end){
  const ms=parseDay(end).getTime();
  return Array.from({length:n},(_,i)=>new Date(ms-(n-1-i)*86400000).toISOString().slice(0,10));
}
function recent(data,n){const dates=new Set(daysArray(n,data.range.end));return data.records.filter(x=>dates.has(x.day))}
function mean(values){return values.length?values.reduce((v,w)=>v+w,0)/values.length:null}
function empty(title,message,symbol="info"){
  const c=e("article","card empty-state");
  a(c,icon(symbol),e("h3","",title),e("p","",message));
  return c;
}
function hint(message,symbol="info"){
  const d=e("div","data-quality-strip");
  a(d,icon(symbol),e("span","",message));
  return d;
}
function heading(title,trail="",fn){
  const div=e("div","section-header");
  a(div,e("h2","",title));
  if(fn){
    const btn=e("button","ghost-link",trail);
    btn.type="button";a(btn,icon("arrow"));btn.addEventListener("click",fn);a(div,btn);
  }else if(trail){a(div,e("span","section-subtitle",trail));}
  return div;
}
function panel(cls=""){return e("article","card panel "+cls)}
function section(){return e("section","section-block")}
function subhead(symbol,title,desc){
  const box=e("div");
  const h=e("h3","panel-title");a(h,icon(symbol),document.createTextNode(title));
  a(box,h,e("p","panel-subtitle",desc));return box;
}
function statCard(title,value,unit,description,symbol,tone=""){
  const c=e("article","card metric-card");
  const top=e("div","metric-top"), badge=e("span","icon-tile "+tone);
  a(badge,icon(symbol));a(top,e("span","metric-title",title),badge);
  const large=e("div","metric-value",value);
  if(unit)a(large,e("span","metric-unit"," "+unit));
  return a(c,top,large,e("div","metric-foot",description));
}
function segment(values,current,callback){
  const div=e("div","tab-segment");
  div.setAttribute("role","group");div.setAttribute("aria-label","Periodo temporale");
  values.forEach(val=>{
    const btn=e("button",current===val?"selected":"",val+" giorni");
    btn.type="button";btn.setAttribute("aria-pressed",String(current===val));
    btn.addEventListener("click",()=>callback(val));a(div,btn);
  });
  return div;
}
function s(tag,attrs,text){
  const node=document.createElementNS(svgNs,tag);
  Object.entries(attrs||{}).forEach(([k,v])=>node.setAttribute(k,String(v)));
  if(text!==undefined)node.textContent=String(text);
  return node;
}
function graph(data,metric,baseline){
  const dates=daysArray(data.range.days,data.range.end), byDay=new Map(data.records.map(x=>[x.day,x]));
  const values=dates.map(day=>{
    const value=num(byDay.get(day)?.[metric.key]);
    return value===null?null:(metric.hours?value/60:value);
  });
  const present=values.filter(v=>v!==null);
  if(!present.length)return empty("Nessuna misurazione","Questo indicatore non è disponibile nel periodo selezionato.","trend");
  const base=num(baseline);
  const ref=base===null?null:(metric.hours?base/60:base);
  const extrema=ref===null?present:[...present,ref];
  let low=Math.min(...extrema),high=Math.max(...extrema);
  const pad=Math.max(2,(high-low)*.2);low-=pad;high+=pad;
  const width=720,height=245,left=47,right=14,top=20,bottom=32;
  const innerWidth=width-left-right,innerHeight=height-top-bottom;
  const xp=i=>left+(dates.length===1?innerWidth/2:i/(dates.length-1)*innerWidth);
  const yp=v=>top+(1-(v-low)/(high-low))*innerHeight;
  const svg=s("svg",{viewBox:"0 0 720 245",class:"trend-chart",role:"img",
    "aria-label":"Andamento "+metric.label+" negli ultimi "+data.range.days+" giorni"});
  for(let i=0;i<4;i++){
    const y=top+innerHeight*i/3;
    a(svg,s("line",{x1:left,y1:y,x2:width-right,y2:y,class:"graph-grid"}),
      s("text",{x:left-10,y:y+4,"text-anchor":"end",class:"graph-label"},
        format(high-(high-low)*i/3,metric.hours?1:0)));
  }
  if(ref!==null)a(svg,s("line",{x1:left,y1:yp(ref),x2:width-right,y2:yp(ref),class:"graph-baseline"}));
  [...new Set([0,Math.floor((dates.length-1)/3),Math.floor((dates.length-1)*2/3),dates.length-1])]
    .forEach(i=>a(svg,s("text",{x:xp(i),y:height-6,
      "text-anchor":i===0?"start":i===dates.length-1?"end":"middle",class:"graph-label"},shortDate(dates[i]))));
  let consecutive=[];
  const segments=[];
  values.forEach((v,i)=>{if(v===null){if(consecutive.length)segments.push(consecutive);consecutive=[]}
    else consecutive.push([i,v])});
  if(consecutive.length)segments.push(consecutive);
  segments.forEach(part=>{
    if(part.length<2)return;
    const d=part.map(([i,v],j)=>(j?"L ":"M ")+xp(i).toFixed(2)+" "+yp(v).toFixed(2)).join(" ");
    a(svg,s("path",{d,class:"graph-line"+(metric.tone==="blue"?" blue":"")}));
  });
  values.forEach((v,i)=>{
    if(v===null)return;
    const circle=s("circle",{cx:xp(i),cy:yp(v),r:dates.length>50?3:4,
      class:"graph-circle"+(metric.tone==="blue"?" blue":"")});
    a(circle,s("title",{},shortDate(dates[i])+": "+format(v,metric.digits)+" "+metric.unit));
    a(svg,circle);
  });
  const box=e("div","chart-area");return a(box,svg);
}
function legend(hasRef){
  const wrap=e("div","chart-legend"), l=e("span","legend-item");
  a(l,e("span","legend-dot"),document.createTextNode("Misurazioni"));a(wrap,l);
  if(hasRef){const b=e("span","legend-item");
    a(b,e("span","legend-dot baseline"),document.createTextNode("Baseline precedente"));a(wrap,b);}
  return wrap;
}
function trendCard(data,metricKey,compact=false){
  const metric=metrics.find(m=>m.key===metricKey)||metrics[0];
  const latest=data.records[data.records.length-1];
  const baseline=metricKey==="hrv_ms"?latest?.hrv_median_previous_28d:
    metricKey==="rhr_bpm"?latest?.rhr_median_previous_28d:null;
  const p=panel(compact?"compact-graph-panel":"trend-panel");
  a(p,subhead("trend",metric.label+" nel tempo",data.range.days+" giorni di calendario"));
  if(compact){
    const vals=recent(data,7).map(r=>num(r[metric.key])).filter(v=>v!==null);
    const av=mean(vals);
    a(p,e("div","trend-stat",(av===null?"—":format(metric.hours?av/60:av,metric.digits))+" "+metric.unit));
  }
  a(p,graph(data,metric,baseline),legend(num(baseline)!==null));
  return p;
}
function qualityCard(data){
  const p=panel();
  a(p,subhead("shield","Copertura dei dati","Completezza delle giornate osservate."));
  const big=e("div","coverage-figure",data.meta.coverage_percent+"%");
  a(big,e("span",""," di copertura"));
  const track=e("div","progress-track");
  track.setAttribute("role","progressbar");
  track.setAttribute("aria-valuenow",String(data.meta.coverage_percent));
  track.setAttribute("aria-valuemin","0");track.setAttribute("aria-valuemax","100");
  track.setAttribute("aria-label","Copertura giornate");
  const fill=e("div","progress-fill");fill.style.width=data.meta.coverage_percent+"%";
  a(track,fill);
  a(p,big,track,e("p","coverage-description",data.meta.observed_days+" giornate su "+
    data.range.days+". I giorni senza dati non vengono inventati."));
  return p;
}
function todayView(data){
  if(!data.records.length)return empty("Nessun dato","Esegui il sync Oura sul Mac.");
  const last=data.records[data.records.length-1],wrap=e("div");
  const hero=e("section","card hero-card"),inside=e("div","hero-inner");
  const kicker=e("div","hero-kicker");a(kicker,icon("moon"),document.createTextNode("ULTIMA NOTTE REGISTRATA"));
  a(inside,kicker,e("div","hero-headline",duration(last.sleep_minutes)),
    e("p","hero-context",last.bedtime_local&&last.wake_local?
      "Sonno dalle "+last.bedtime_local+" alle "+last.wake_local+" secondo Oura.":
      "Durata stimata dai dati disponibili."),
    e("p","hero-caption",fullDate(last.day)+" · misurazione, non valutazione clinica"));
  const right=e("div","hero-indicator");
  a(right,e("span","","MEDIA 7 GIORNI"),e("strong","",duration(last.sleep_minutes_avg_7d)));
  a(hero,inside,right);a(wrap,hero);
  const cards=e("div","cards-grid");
  const hd=num(last.hrv_change_pct),rd=num(last.rhr_change_bpm);
  a(cards,
    statCard("HRV notturna",format(last.hrv_ms),"ms",hd===null?"Baseline non disponibile":
      (hd>=0?"+":"")+format(hd,1)+"% · trend 7/28 giorni","heart"),
    statCard("FC minima",format(last.rhr_bpm),"bpm",rd===null?"Baseline non disponibile":
      (rd>=0?"+":"")+format(rd,1)+" bpm · trend 7/28 giorni","activity","blue"),
    statCard("Sleep Score",format(last.sleep_score),"/ 100","Punteggio proprietario Oura","moon","violet"),
    statCard("Readiness",format(last.readiness_score),"/ 100","Punteggio proprietario Oura","spark","warm"));
  const metricsSection=section();
  a(metricsSection,heading("Segnali principali","Ultima osservazione"),cards);a(wrap,metricsSection);
  const summarySection=section(),layout=e("div","overview-layout");
  a(layout,trendCard(data,"hrv_ms",true),qualityCard(data));
  a(summarySection,heading("Il quadro generale","Esplora i trend",()=>selectTab("trends")),layout);
  a(wrap,summarySection);
  const extras=section(),grid=e("div","cards-grid");
  a(grid,statCard("Respirazione",format(last.respiratory_rate_per_min,1),"atti/min","Media durante il sonno","activity","blue"),
    statCard("Efficienza",format(last.sleep_efficiency_pct),"%","Tempo effettivamente dormito","moon"),
    statCard("Latenza",format(last.sleep_latency_minutes),"min","Tempo per addormentarsi","clock","warm"),
    statCard("Passi",format(last.steps),"","Attività giornaliera riportata","dumbbell","violet"));
  a(extras,heading("Contesto dell'ultima notte"),grid);
  a(wrap,extras,hint("Una variazione di HRV o frequenza cardiaca, da sola, non indica una malattia."));
  return wrap;
}
function trendsView(data){
  const wrap=e("div"),filters=e("div","trend-toolbox");
  a(filters,e("span","section-subtitle","Seleziona indicatore e finestra temporale"),
    segment([7,30,90],state.days,n=>load(n)));
  const picker=e("div","graph-switcher");
  metrics.forEach(m=>{
    const b=e("button",state.metric===m.key?"selected":"",m.label);
    b.type="button";b.setAttribute("aria-pressed",String(state.metric===m.key));
    b.addEventListener("click",()=>{state.metric=m.key;render()});a(picker,b);
  });
  const sec=section();
  a(sec,filters,picker,trendCard(data,state.metric));
  a(wrap,sec);
  const chosen=metrics.find(m=>m.key===state.metric);
  const vals=data.records.map(r=>num(r[state.metric])).filter(v=>v!==null);
  const stats=panel("section-block"),bar=e("div","trend-summary");
  const left=e("div"),right=e("div");
  const av=mean(vals);
  a(left,e("div","figure",av===null?"—":
    format(chosen.hours?av/60:av,chosen.digits)+" "+chosen.unit),
    e("small","","Media delle misurazioni disponibili"));
  a(right,e("div","figure",vals.length+" / "+data.range.days),
    e("small","","Giornate con la metrica"));
  a(bar,left,e("span","divider-vertical"),right);
  a(stats,bar,hint("I grafici non interpolano giornate mancanti. I confronti non rappresentano prescrizioni cliniche."));
  a(wrap,stats);
  return wrap;
}
function safeUrl(x){
  try{const u=new URL(x);return u.protocol==="https:"?u.href:null}catch{return null}
}
function kind(id){
  if(id.includes("sleep"))return ["SONNO","moon"];
  if(id.includes("autonomic"))return ["RECUPERO","heart"];
  if(id.includes("exercise"))return ["ALLENAMENTO","dumbbell"];
  return ["QUALITÀ DATI","shield"];
}
function insightCard(item){
  const box=e("article","card insight-card"),h=e("div","insight-header");
  const [group,symbol]=kind(String(item.id||""));
  const tile=e("span","insight-icon");a(tile,icon(symbol));
  const headingBox=e("div");
  a(headingBox,e("p","insight-meta",group),e("h3","insight-title",item.title||"Osservazione"));
  a(h,tile,headingBox);
  a(box,h,e("p","insight-copy",item.summary||""));
  const details=e("details","insight-expand"),summary=e("summary","","Come è stato calcolato");
  a(summary,icon("chevron"));a(details,summary);
  const content=e("div","insight-detail"),measurement=item.measurements||{};
  if(Object.keys(measurement).length){
    const groupEl=e("section"),list=e("div","measure-list");
    a(groupEl,e("h4","","DATI UTILIZZATI"));
    Object.entries(measurement).forEach(([name,value])=>{
      const r=e("div","measure");
      a(r,e("span","",measureLabels[name]||name.replaceAll("_"," ")),
        e("strong","",typeof value==="boolean"?(value?"Sì":"No"):format(value,2)));
      a(list,r);
    });
    a(groupEl,list);a(content,groupEl);
  }
  if(Array.isArray(item.limitations)&&item.limitations.length){
    const g=e("section"),list=e("ul");
    a(g,e("h4","","LIMITI DI INTERPRETAZIONE"));
    item.limitations.forEach(value=>a(list,e("li","",value)));
    a(g,list);a(content,g);
  }
  if(Array.isArray(item.evidence_urls)&&item.evidence_urls.length){
    const g=e("section");a(g,e("h4","","FONTI E STUDI"));
    item.evidence_urls.forEach((source,i)=>{
      const href=safeUrl(source);if(!href)return;
      const link=e("a","reference-link","Fonte "+(i+1)+" · "+new URL(href).host);
      link.href=href;link.target="_blank";link.rel="noopener noreferrer";
      a(link,icon("link"));a(g,link);
    });
    a(content,g);
  }
  a(details,content);a(box,details);return box;
}
function insightsView(data){
  const wrap=e("div");
  a(wrap,heading(data.insights.length+" osservazioni","Regole deterministiche, non AI"));
  const list=e("div","insight-list");
  if(!data.insights.length)a(list,empty("Nessun insight disponibile",
    "Servono più notti valide per confrontare i segnali.","spark"));
  data.insights.forEach(item=>a(list,insightCard(item)));
  a(wrap,list,hint("Le correlazioni non dimostrano causalità. Questa dashboard non genera diagnosi né allerte mediche.","shield"));
  return wrap;
}
function trainingView(data){
  const wrap=e("div");
  if(!data.meta.workout_history_available){
    a(wrap,empty("Dati workout non disponibili",
      "Non risultano allenamenti importati. Questo non significa assenza di attività: sincronizza la collezione workout per confrontare i giorni con sessioni registrate.","dumbbell"));
    return wrap;
  }
  const rows=recent(data,data.range.days);
  const count=rows.reduce((sum,r)=>sum+(num(r.training_sessions)||0),0);
  const active=rows.filter(r=>num(r.training_sessions)>0).length;
  const duo=e("div","training-grid"),one=panel(),two=panel();
  a(one,subhead("dumbbell","Attività registrate",data.range.days+" giorni di calendario"),
    e("div","training-big",format(count)),e("div","training-caption","sessioni Oura registrate"));
  a(two,subhead("calendar","Giorni con workout","Presenza di almeno una sessione registrata"),
    e("div","training-big",format(active)),e("div","training-caption","giornate su "+data.range.days));
  a(duo,one,two);a(wrap,duo);
  const history=section(),p=panel(),bars=e("div","workout-bars");
  const map=new Map(rows.map(r=>[r.day,r]));
  const days=daysArray(14,data.range.end);
  const maximum=Math.max(1,...days.map(d=>num(map.get(d)?.training_sessions)||0));
  days.forEach(d=>{
    const n=num(map.get(d)?.training_sessions);
    const cell=e("div","workout-day"),bar=e("span","workout-bar"+(n===null?" unknown":n===0?" none":""));
    bar.style.height=(n===null?6:Math.max(3,n/maximum*95))+"px";
    bar.title=shortDate(d)+": "+(n===null?"dato mancante":format(n)+" sessioni");
    a(cell,bar,e("small","",shortDate(d).split(" ")[0]));a(bars,cell);
  });
  a(p,bars,e("p","coverage-description","L'assenza di un workout registrato non equivale necessariamente a riposo."));
  a(history,heading("Ultime due settimane","Sessioni registrate per giorno"),p);
  a(wrap,history);
  const sec=section(),trainingInsight=data.insights.find(x=>x.id==="exercise-following-day");
  a(sec,heading("Confronto HRV del giorno successivo"));
  if(trainingInsight)a(sec,insightCard(trainingInsight));
  else a(sec,empty("Dati insufficienti per un confronto attendibile",
    "Servono almeno quattro notti dopo giorni con allenamento e quattro notti di confronto, tutte con HRV disponibile.","heart"));
  a(wrap,sec);
  const items=rows.filter(x=>num(x.training_sessions)>0).slice(-5).reverse();
  if(items.length){
    const recentSec=section(),panelEl=panel(),table=e("table","feature-table");
    const thead=e("thead"),tr=e("tr");
    ["Giorno","Sessioni","HRV risveglio seguente"].forEach(v=>a(tr,e("th","",v)));
    a(thead,tr);a(table,thead);
    const body=e("tbody");
    items.forEach(item=>{
      const row=e("tr"),next=new Date(parseDay(item.day).getTime()+86400000).toISOString().slice(0,10);
      const value=num(map.get(next)?.hrv_ms);
      a(row,e("td","",shortDate(item.day)),e("td","",format(item.training_sessions)),
        e("td","",value===null?"—":format(value)+" ms"));
      a(body,row);
    });
    a(table,body);a(panelEl,table);a(recentSec,heading("Sessioni recenti"),panelEl);a(wrap,recentSec);
  }
  return wrap;
}
function shell(data){
  const meta=data?.meta;
  document.getElementById("report-date").textContent=meta?fullDate(meta.last_observed_day):"Senza dati";
  const badge=document.getElementById("status-badge");
  badge.classList.toggle("stale",!meta||meta.age_days>2);
  document.getElementById("status-label").textContent=!meta?"Dati assenti":
    meta.age_days>2?"Da aggiornare":"Dati locali";
}
function render(){
  const entry=labels[state.tab];
  const name=document.getElementById("page-title");
  name.textContent=entry[0];a(name,e("span","teal-dot","."));
  document.getElementById("page-subtitle").textContent=entry[1];
  document.getElementById("eyebrow").textContent=entry[2];
  document.getElementById("breadcrumb-label").textContent=entry[3];
  document.querySelectorAll("[data-tab]").forEach(btn=>{
    const active=btn.getAttribute("data-tab")===state.tab;
    btn.classList.toggle("is-active",active);
    if(active)btn.setAttribute("aria-current","page");
    else btn.removeAttribute("aria-current");
  });
  root.replaceChildren();
  if(!state.data)return;
  const views={today:todayView,trends:trendsView,insights:insightsView,training:trainingView};
  a(root,views[state.tab](state.data));
}
function selectTab(tab){
  if(!labels[tab])return;
  state.tab=tab;render();
  if(window.scrollY>170)window.scrollTo({top:0,behavior:"smooth"});
}
async function load(days=state.days){
  if(state.loading)return;
  state.days=days;state.loading=true;spinner.hidden=false;notice.hidden=true;
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
  try{
    const response=await fetch("/api/dashboard?days="+days,{cache:"no-store",
      credentials:"same-origin",signal:controller.signal,headers:{Accept:"application/json"}});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.error||"Dati non disponibili");
    if(!Array.isArray(payload.records)||!Array.isArray(payload.insights)||!payload.meta)
      throw new Error("Formato dati non valido");
    state.data=payload;shell(payload);render();
    if(payload.meta.age_days>2){
      notice.textContent="Ultima osservazione del "+fullDate(payload.meta.last_observed_day)+
        ". Esegui una nuova sincronizzazione Oura sul Mac per aggiornare i dati.";
      notice.hidden=false;
    }
  }catch(err){
    if(!state.data)root.replaceChildren(empty("Non ci sono ancora dati",
      "La dashboard è pronta. Esegui il sync Oura sul Mac per popolarla.","info"));
    notice.textContent=err.name==="AbortError"?"Il caricamento richiede troppo tempo. Riprova.":
      (err.message||"Impossibile caricare i dati.");
    notice.hidden=false;shell(state.data);
  }finally{clearTimeout(timeout);spinner.hidden=true;state.loading=false;}
}
document.querySelectorAll("[data-tab]").forEach(btn=>btn.addEventListener("click",
  ()=>selectTab(btn.getAttribute("data-tab"))));
document.getElementById("refresh").addEventListener("click",()=>load());
if("serviceWorker" in navigator && window.isSecureContext)
  window.addEventListener("load",()=>navigator.serviceWorker.register("/sw.js").catch(()=>{}));
load(30);
