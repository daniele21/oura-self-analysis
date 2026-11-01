/* Private Oura dashboard: all health data stays in memory and is never cached. */
"use strict";
const state = { tab:"today", days:30, metric:"hrv_ms", sleepDay:null, data:null, loading:false, nightAbort:null };
const root = document.getElementById("view-root");
const notice = document.getElementById("notice");
const spinner = document.getElementById("load-state");
const labels = {
  today:["La tua panoramica","Una lettura chiara dei segnali che contano davvero.","PANORAMICA PERSONALE","PANORAMICA"],
  sleep:["Il tuo sonno","Dalla settimana alla singola notte: andamento, confronti e dettaglio.","SLEEP INTELLIGENCE","SONNO"],
  recovery:["Il tuo recupero","HRV e frequenza cardiaca minima rispetto alla tua storia personale.","CARDIOVASCULAR INTELLIGENCE","RECUPERO"],
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
  workout_history_available:"Storico allenamenti disponibile",
  recent_median:"Mediana ultimi 7 giorni",
  baseline_median:"Mediana dei 28 giorni precedenti",
  absolute_change:"Differenza assoluta",
  percentage_change:"Variazione percentuale",
  baseline_mad:"MAD della baseline",
  baseline_robust_sigma:"Dispersione robusta (σ)",
  standardized_shift:"Scostamento / dispersione storica",
  recent_cv_pct:"Variabilità degli ultimi 7 giorni (CV %)",
  personal_band:"Banda statistica individuale",
  days_outside_personal_band:"Giornate fuori banda (7 giorni)",
  longest_consecutive_outside:"Massima sequenza consecutiva",
  leave_one_out_direction_pct:"Coerenza leave-one-out (%)",
  bootstrap_80_delta_interval:"Intervallo bootstrap esplorativo 80%",
  paired_valid_n:"Notti con entrambi i segnali",
  paired_outside_n:"Notti con deviazione congiunta",
  hrv_personal_lower_ms:"HRV limite statistico inferiore (ms)",
  rhr_personal_upper_bpm:"FC limite statistico superiore (bpm)",
  recent_n:"Osservazioni recenti",baseline_n:"Osservazioni baseline",
  recent_coverage_pct:"Copertura recente (%)",baseline_coverage_pct:"Copertura baseline (%)"
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
  a(metricsSection,heading("Segnali principali","Apri Recupero",()=>selectTab("recovery")),cards);a(wrap,metricsSection);
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
  metrics.filter(m=>m.key==="hrv_ms"||m.key==="rhr_bpm").forEach(m=>{
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


/* 30-minute bin visualizations for one private Oura night.
   Both channels share elapsed minutes; missing bins are never connected. */
function cardioNightChart(profile){
  const box=e("div","cardio-chart-widget"),bins=profile.bins||[];
  if(!bins.length)return empty("Nessun intervallo disponibile",
    "La notte non contiene dati temporali utilizzabili.","heart");
  const dimensions={w:720,h:372,left:54,right:19,top:37,gap:64,plotHeight:113};
  const xMin=dimensions.left,xMax=dimensions.w-dimensions.right;
  const maxMinutes=Math.max(30,num(profile.duration_minutes)||30);
  const xOf=elapsed=>xMin+elapsed/maxMinutes*(xMax-xMin);
  const plotConfig=[
    {field:"heart_rate_bpm",title:"Frequenza cardiaca",unit:"bpm",cls:"cardio-hr",yTop:37},
    {field:"hrv_ms",title:"Variabilità cardiaca",unit:"ms",cls:"cardio-hrv",yTop:37+113+64}
  ];
  const chart=s("svg",{class:"cardio-profile-svg",viewBox:"0 0 720 372",role:"img",
    "aria-label":"Frequenza cardiaca e HRV della notte in intervalli di 30 minuti, con lacune visibili"});
  const title=s("title",{}, "HR e HRV allineate nel tempo trascorso da quando sei andato a letto");
  a(chart,title);
  const verticalMarkers=[];
  plotConfig.forEach(metric=>{
    const nums=bins.map(b=>num(b[metric.field])).filter(x=>x!==null);
    const yMin=nums.length?Math.min(...nums):0, yMax=nums.length?Math.max(...nums):1;
    const margin=Math.max(1,(yMax-yMin)*.16);
    const lower=yMin-margin,upper=yMax+margin;
    const yOf=value=>metric.yTop+(1-(value-lower)/(upper-lower))*dimensions.plotHeight;
    a(chart,s("text",{x:xMin,y:metric.yTop-15,class:"cardio-panel-label"},
      metric.title+" ("+metric.unit+")"));
    for(let j=0;j<=3;j++){
      const y=metric.yTop+j*dimensions.plotHeight/3;
      a(chart,s("line",{x1:xMin,y1:y,x2:xMax,y2:y,class:"graph-grid"}),
        s("text",{x:xMin-9,y:y+4,"text-anchor":"end",class:"graph-label"},
          nums.length?format(upper-(upper-lower)*j/3,0):"—"));
    }
    let points=[];
    const flush=()=>{
      if(points.length>1){
        a(chart,s("path",{class:"cardio-profile-line "+metric.cls,
          d:points.map(([x,y],i)=>(i?"L":"M")+x.toFixed(1)+" "+y.toFixed(1)).join(" ")}));
      }
      points=[];
    };
    bins.forEach(b=>{
      const value=num(b[metric.field]);
      if(value===null){flush();return;}
      const xx=xOf(b.elapsed_minutes+15),yy=yOf(value);
      points.push([xx,yy]);
      const circ=s("circle",{cx:xx,cy:yy,r:3.2,class:"cardio-point "+metric.cls});
      a(circ,s("title",{},"Dopo "+format(b.elapsed_minutes,0)+" minuti: "+
        format(value,1)+" "+metric.unit));
      a(chart,circ);
    });
    flush();
    const v=s("line",{x1:xOf(bins[0].elapsed_minutes+15),
      x2:xOf(bins[0].elapsed_minutes+15),y1:metric.yTop,
      y2:metric.yTop+dimensions.plotHeight,class:"cardio-crosshair"});
    a(chart,v);verticalMarkers.push(v);
    if(!nums.length)a(chart,s("text",{x:dimensions.w/2,y:metric.yTop+65,
       "text-anchor":"middle",class:"cardio-empty-label"},"Campioni insufficienti"));
  });
  const labelY=dimensions.h-13;
  for(let minutes=0;minutes<=maxMinutes;minutes+=120){
    a(chart,s("text",{x:xOf(minutes),y:labelY,
      "text-anchor":minutes===0?"start":"middle",class:"graph-label"},
      "+"+format(minutes/60,0)+"h"));
  }
  a(box,chart);
  const note=e("p","coverage-description",
    "Asse comune: tempo dall'inizio della sessione a letto. Ogni punto è la mediana di 30 minuti con almeno 4 campioni validi; le lacune restano vuote.");
  a(box,note);
  const cursor=e("div","cardio-cursor");
  const caption=e("label","cardio-cursor-label","Esplora lo stesso intervallo nei due grafici");
  const slider=e("input","cardio-cursor-range");
  slider.type="range";slider.min="0";slider.max=String(bins.length-1);slider.step="1";slider.value="0";
  const selected=e("output","cardio-selected-readout");
  caption.append(slider);
  function update(){
    const idx=Number(slider.value),current=bins[idx];
    const x=xOf(current.elapsed_minutes+15);
    verticalMarkers.forEach(line=>{line.setAttribute("x1",String(x));line.setAttribute("x2",String(x));});
    selected.textContent="+"+format(current.elapsed_minutes/60,1)+" h · HR "+
      (num(current.heart_rate_bpm)===null?"—":format(current.heart_rate_bpm,1)+" bpm")+
      " (n="+current.heart_rate_bpm_n+") · HRV "+
      (num(current.hrv_ms)===null?"—":format(current.hrv_ms,1)+" ms")+
      " (n="+current.hrv_ms_n+")";
  }
  slider.addEventListener("input",update);
  a(cursor,caption,selected);
  a(box,cursor);update();
  const quality=profile.channels||{};
  const infos=e("div","cardio-quality-grid");
  [["HR",quality.heart_rate],["HRV",quality.hrv]].forEach(([name,q])=>{
    if(!q)return;
    const tile=e("div","cardio-quality");
    a(tile,e("strong","",name+" · "+q.qualified_bins+"/"+q.total_bins+" intervalli"),
      e("span","",q.status==="ok"?
        (num(q.full_night_coverage_fraction)===null?"Copertura non calcolabile":
         format(q.full_night_coverage_fraction*100,0)+"% della notte campionata"):
        q.status==="missing"?"Serie non disponibile":
        "Formato o frequenza non standard: curva non interpretata"));
    a(infos,tile);
  });
  a(box,infos);
  const details=e("details","cardio-tabular"),
    summary=e("summary","","Tabella accessibile di tutti gli intervalli");
  a(summary,icon("chevron"));
  const tbl=e("table","feature-table"),thead=e("thead"),row=e("tr");
  ["Da inizio notte","HR (bpm)","HRV (ms)"].forEach(v=>a(row,e("th","",v)));
  a(thead,row);a(tbl,thead);
  const tbody=e("tbody");
  bins.forEach(bin=>{
    const tr=e("tr");
    a(tr,e("td","", "+"+format(bin.elapsed_minutes,0)+" min"),
      e("td","",num(bin.heart_rate_bpm)===null?"—":format(bin.heart_rate_bpm,1)+" (n="+bin.heart_rate_bpm_n+")"),
      e("td","",num(bin.hrv_ms)===null?"—":format(bin.hrv_ms,1)+" (n="+bin.hrv_ms_n+")"));
    a(tbody,tr);
  });
  a(tbl,tbody);a(details,tbl);a(box,details);
  a(box,hint("Le misure Oura sono esplorative. Frequenza cardiaca e HRV non consentono, da sole, di diagnosticare stress o recupero.","shield"));
  return box;
}
async function loadCardioNightProfile(day,host){
  if(state.nightAbort)state.nightAbort.abort();
  const controller=new AbortController();state.nightAbort=controller;
  try{
    const r=await fetch("/api/v2/recovery/night?day="+encodeURIComponent(day),{
      cache:"no-store",credentials:"same-origin",signal:controller.signal,
      headers:{Accept:"application/json"}});
    const data=await r.json();
    if(controller.signal.aborted||state.tab!=="recovery"||state.sleepDay!==day||!host.isConnected)return;
    if(r.status===404){
      host.replaceChildren(empty("Nessuna sessione notturna principale",
        "Per questa giornata non è disponibile il profilo di sonno principale.","heart"));
      return;
    }
    if(!r.ok)throw Error("La serie di questa notte non è disponibile.");
    if(!Array.isArray(data.bins)||!data.channels)throw Error("Formato del profilo inatteso.");
    host.replaceChildren(cardioNightChart(data));
  }catch(err){
    if(err.name==="AbortError"||controller.signal.aborted||!host.isConnected)return;
    host.replaceChildren(empty("Impossibile mostrare le curve",
      "I riepiloghi notturni restano disponibili. Aggiorna la pagina o scegli un'altra notte.","info"));
  }finally{
    if(state.nightAbort===controller)state.nightAbort=null;
  }
}

/* M1 Recupero: nightly aggregates plus private sampled 30-minute profile. */
function recoveryView(data){
  const wrap=e("div"),last=data.records[data.records.length-1];
  const filtered=data.records.filter(row=>num(row.hrv_ms)!==null||num(row.rhr_bpm)!==null);
  if(!filtered.length)return empty("Misurazioni cardiovascolari non disponibili",
    "La pagina mostrerà HR e HRV soltanto quando saranno presenti osservazioni notturne valide.","heart");
  if(!state.sleepDay||!filtered.some(x=>x.day===state.sleepDay)){
    state.sleepDay=filtered[filtered.length-1].day;
  }
  const current=filtered.find(x=>x.day===state.sleepDay);
  const head=section(),stats=e("div","cards-grid");
  a(head,heading("La tua fisiologia recente","7 giorni vs i 28 precedenti"));
  const hrvLast=last&&num(last.hrv_median_7d)!==null?last.hrv_median_7d:null;
  const hrLast=last&&num(last.rhr_median_7d)!==null?last.rhr_median_7d:null;
  a(stats,
    statCard("HRV · mediana 7 giorni",format(hrvLast),"ms",
      "Baseline precedenti 28 giorni: "+format(last?.hrv_median_previous_28d)+" ms",
      "heart"),
    statCard("FC minima · mediana 7 giorni",format(hrLast),"bpm",
      "Baseline precedenti 28 giorni: "+format(last?.rhr_median_previous_28d)+" bpm",
      "activity","blue"));
  a(head,stats);
  a(head,hint("Il selettore 7/30/90 cambia solo il periodo del grafico. Il confronto fisiologico utilizza sempre gli ultimi 7 giorni contro i 28 precedenti, senza sovrapposizioni."));
  a(wrap,head);
  const trends=section();
  a(trends,heading("L'andamento nel tempo","Misurazioni giornaliere"));
  a(trends,trendsView(data));
  a(wrap,trends);
  const night=section(),p=panel(),controls=e("div","sleep-date-picker"),label=e("label","", "Notte selezionata");
  label.htmlFor="cardio-night-select";
  const picker=e("select","sleep-select");picker.id="cardio-night-select";
  [...filtered].reverse().forEach(row=>{
    const opt=e("option","",fullDate(row.day));opt.value=row.day;
    opt.selected=row.day===state.sleepDay;a(picker,opt);
  });
  picker.addEventListener("change",()=>setSelectedNight(picker.value));
  a(controls,label,picker);
  a(p,subhead("moon","Profilo della notte","Misurazioni aggregate e profilo HR/HRV della notte selezionata"),controls);
  const nightStats=e("div","sleep-night-measures");
  [["HRV media notturna",current.hrv_ms,"ms"],
   ["FC minima notturna",current.rhr_bpm,"bpm"],
   ["Durata del sonno",current.sleep_minutes,"min"],
   ["Frequenza respiratoria",current.respiratory_rate_per_min,"atti/min"]].forEach(([title,value,unit])=>{
     const tile=e("div","sleep-night-measure");
     a(tile,e("span","",title),e("strong","",format(value,1)+(num(value)!==null?" "+unit:"")));
     a(nightStats,tile);
  });
  a(p,nightStats);
  const profileMount=e("div","cardio-profile-mount");
  a(profileMount,e("p","coverage-description","Caricamento del profilo notturno…"));
  a(p,profileMount);
  loadCardioNightProfile(state.sleepDay,profileMount);
  const go=e("button","recovery-action","Vedi il dettaglio del sonno di questa notte");
  go.type="button";a(go,icon("arrow"));
  go.addEventListener("click",()=>selectTab("sleep"));
  a(p,go);a(night,p);a(wrap,night);
  return wrap;
}
function setSelectedNight(day){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day))return;
  state.sleepDay=day;
  syncRoute();
  render();
}
function syncRoute(){
  const route="#/"+state.tab+(state.sleepDay&&(state.tab==="sleep"||state.tab==="recovery")?
    "/"+state.sleepDay:"");
  if(window.location.hash!==route)window.history.replaceState(null,"",route);
}
function applyRoute(){
  const parts=window.location.hash.replace(/^#\/?/,"").split("/");
  const alias={trends:"recovery",training:"training",insights:"insights"};
  const tab=alias[parts[0]]||parts[0];
  if(labels[tab])state.tab=tab;
  if((tab==="sleep"||tab==="recovery")&&/^\d{4}-\d{2}-\d{2}$/.test(parts[1]||""))
    state.sleepDay=parts[1];
}
function safeUrl(x){
  try{const u=new URL(x);return u.protocol==="https:"?u.href:null}catch{return null}
}
function kind(id){
  if(id.includes("sleep"))return ["SONNO","moon"];
  if(id.includes("autonomic")||id.includes("hrv")||id.includes("rhr")||
      id.includes("personal-variability"))return ["RECUPERO","heart"];
  if(id.includes("exercise"))return ["ALLENAMENTO","dumbbell"];
  return ["QUALITÀ DATI","shield"];
}
function presentMeasurement(value){
  if(value===null||value===undefined)return "—";
  if(typeof value==="boolean")return value?"Sì":"No";
  if(Array.isArray(value))return value.map(v=>format(v,2)).join(" – ");
  if(typeof value==="string")return value;
  return format(value,2);
}
function insightCard(item){
  const box=e("article","card insight-card"),h=e("div","insight-header");
  const [group,symbol]=kind(String(item.id||""));
  const tile=e("span","insight-icon");a(tile,icon(symbol));
  const headingBox=e("div");
  a(headingBox,e("p","insight-meta",group),e("h3","insight-title",item.title||"Osservazione"));
  a(h,tile,headingBox);
  a(box,h,e("p","insight-copy",item.summary||""));
  if(item.quality){
    const q=item.quality;
    const label=q.level==="adequate"?"Copertura adeguata per un'analisi esplorativa":
                q.level==="limited"?"Copertura parziale":"Dati insufficienti";
    a(box,e("p","insight-reliability",label));
  }
  const details=e("details","insight-expand"),summary=e("summary","","Come è stato calcolato");
  a(summary,icon("chevron"));a(details,summary);
  const content=e("div","insight-detail"),measurement=item.measurements||{};
  if(item.interpretation){
    const group=e("section");
    a(group,e("h4","","COME INTERPRETARE IL RISULTATO"),e("p","insight-detail-text",item.interpretation));
    a(content,group);
  }
  if(item.quality){
    const group=e("section"),q=item.quality;
    const coverage=(q.recent_n!==undefined && q.baseline_n!==undefined)?
       "Copertura: "+q.recent_n+"/7 giorni recenti e "+q.baseline_n+
       "/28 giorni di riferimento.":"Metodologia descrittiva.";
    a(group,e("h4","","QUALITÀ DELL'EVIDENZA"),e("p","insight-detail-text",coverage));
    if(q.method)a(group,e("p","insight-detail-text","Metodo: "+q.method+". Non è una validazione clinica."));
    a(content,group);
  }
  if(Object.keys(measurement).length){
    const groupEl=e("section"),list=e("div","measure-list");
    a(groupEl,e("h4","","DATI UTILIZZATI"));
    Object.entries(measurement).forEach(([name,value])=>{
      if(["metric","unit","quality","limitations","recent_days","baseline_days"].includes(name))return;
      const r=e("div","measure");
      a(r,e("span","",measureLabels[name]||name.replaceAll("_"," ")),
        e("strong","",presentMeasurement(value)));
      a(list,r);
    });
    a(groupEl,list);a(content,groupEl);
  }
  if(Array.isArray(item.alternative_explanations)&&item.alternative_explanations.length){
    const group=e("section"),items=e("ul");
    a(group,e("h4","","ALTRE POSSIBILI SPIEGAZIONI"));
    item.alternative_explanations.forEach(reason=>a(items,e("li","",reason)));
    a(group,items);a(content,group);
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
function recoveryCurveCard(response){
  const wrap=section();
  a(wrap,heading("Risposta nei 3 risvegli successivi","D+1 · D+2 · D+3"));
  if(!response || !response.recorded_workout_days){
    a(wrap,empty("Nessun workout nello storico di analisi",
      "Non ci sono eventi registrati nei giorni considerati. La registrazione dell'attività potrebbe essere incompleta.","dumbbell"));
    return wrap;
  }
  const isolated=response.eligible_isolated_days>=response.min_sample_per_lag;
  const observed=response.observed_event_days>=response.min_sample_per_lag;
  const points=isolated?response.outcomes:response.observed_outcomes;
  const p=panel();
  const chosen=isolated?"Sessioni isolate (senza altri workout registrati ±3 giorni)":
     "Tutte le giornate con workout (possibili sovrapposizioni)";
  a(p,subhead("activity","Confronto rispetto al risveglio D",chosen));
  const counts=e("p","training-caption",
    response.recorded_workout_days+" giorni con workout · "+
    response.observed_event_days+" con riferimento fisiologico · "+
    response.eligible_isolated_days+" isolati · "+
    response.excluded_overlapping_days+" con altri allenamenti vicini");
  a(p,counts);
  if(!isolated&&!observed){
    a(p,hint("Per stimare una curva servono almeno quattro coppie di misurazioni per ritardo. Questo non implica recupero insufficiente.", "info"));
  }else{
    if(!isolated)a(p,hint("Analisi osservazionale con allenamenti ravvicinati: gli effetti delle sessioni possono sovrapporsi e non essere separabili.", "alert"));
    const t=e("table","feature-table"),head=e("thead"),row=e("tr");
    ["Differenza mediana da D","D+1","D+2","D+3"].forEach(v=>a(row,e("th","",v)));
    a(head,row);a(t,head);
    const body=e("tbody");
    [["hrv_ms","HRV","ms"],["rhr_bpm","FC minima","bpm"],["sleep_minutes","Sonno","min"]].forEach(([key,label,unit])=>{
      const row=e("tr");
      a(row,e("td","",label));
      points.forEach(point=>{
        const v=point[key+"_delta_median"],n=point[key+"_n"];
        const cell=e("td");
        const str=num(v)===null?"—":(v>0?"+":"")+format(v,1)+" "+unit;
        a(cell,e("strong","",str),e("small","training-n","n="+n));
        a(row,cell);
      });
      a(body,row);
    });
    a(t,body);
    a(p,t,e("p","coverage-description","D significa risveglio nel giorno dell'allenamento; D+1/2/3 sono i risvegli nei successivi giorni di calendario, non intervalli esatti in ore."));
  }
  const activities=response.by_activity||[];
  const intensities=response.by_intensity||[];
  if(activities.length || intensities.length){
    const div=e("div","recovery-categories");
    a(div,e("h4","","CONFRONTI ESPLORATIVI DISPONIBILI"));
    const names={
      cross_training:"Cross training / HIIT",racket_sport:"Sport con racchetta",
      strength:"Forza",running:"Corsa",cycling:"Ciclismo",walking:"Camminata",
      other:"Altre attività", easy:"Facile (Oura)",moderate:"Moderata (Oura)",hard:"Intensa (Oura)"
    };
    activities.forEach(item=>a(div,e("p","coverage-description",
      (names[item.activity]||item.activity)+": "+item.observed_days+
      " giornate registrate; confronti inclusivi di workout vicini.")));
    intensities.forEach(item=>a(div,e("p","coverage-description",
      (names[item.intensity]||item.intensity)+": "+item.observed_days+
      " giornate con intensità registrata.")));
    a(p,div);
  }
  a(p,hint("Non è un tempo di recupero validato né una prescrizione di allenamento. Oura usa intensità easy/moderate/hard: non sono valori RPE.", "shield"));
  a(wrap,p);return wrap;
}
const SLEEP_LABELS={
  sleep_minutes:"Sonno totale",sleep_efficiency_pct:"Efficienza",
  sleep_latency_minutes:"Latenza",awake_minutes:"Tempo sveglio",
  sleep_score:"Sleep Score",deep_sleep_minutes:"Sonno profondo",
  rem_sleep_minutes:"Sonno REM",light_sleep_minutes:"Sonno leggero",
  time_in_bed_minutes:"Tempo a letto"
};
const SLEEP_UNITS={
  sleep_minutes:"min",sleep_efficiency_pct:"pp",sleep_latency_minutes:"min",
  awake_minutes:"min",sleep_score:"pt",deep_sleep_minutes:"min",
  rem_sleep_minutes:"min",light_sleep_minutes:"min"
};
function sleepDelta(v,unit){
  return num(v)===null?"—":(v>0?"+":"")+format(v,0)+(unit?" "+unit:"");
}
function sleepWeekCard(title,summary){
  const p=panel("sleep-week-card");
  a(p,subhead("moon",title,shortDate(summary.start)+" – "+shortDate(summary.end)));
  const average=summary.averages.sleep_minutes;
  a(p,e("div","training-big",duration(average)),
    e("div","training-caption","Durata media per notte, "+summary.available_nights+"/7 notti disponibili"));
  const stats=e("div","sleep-week-facts");
  [["Efficienza",summary.averages.sleep_efficiency_pct,"%"],
   ["Variabilità durata",summary.duration_sd_minutes,"min"],
   ["Regolarità orario",summary.bedtime_clock_sd_minutes,"min"],
   ["Sleep Score",summary.averages.sleep_score,"/100"]].forEach(([label,value,unit])=>{
     const cell=e("div","sleep-week-fact");
     a(cell,e("span","",label),e("strong","",format(value,0)+(num(value)!==null?" "+unit:"")));
     a(stats,cell);
  });
  a(p,stats);
  if(!summary.sufficient)a(p,hint("Copertura insufficiente: servono almeno 4 notti valide su 7 per mostrare medie e confronti.","info"));
  return p;
}
function sleepWeekly(data){
  const sleep=data.sleep_intelligence;
  const weekly=sleep.weekly;
  const container=section();
  a(container,heading("Come sta andando questa settimana","Ultimi 7 giorni contro i 7 precedenti"));
  const grid=e("div","training-grid");
  a(grid,sleepWeekCard("Ultimi 7 giorni",weekly.recent),
    sleepWeekCard("Sette giorni precedenti",weekly.previous));
  a(container,grid);
  const comparison=panel("section-block");
  a(comparison,subhead("trend","Cosa è cambiato","Confronto tra blocchi non sovrapposti di 7 giorni"));
  const metrics=[
    ["Durata media","sleep_minutes","min"],
    ["Efficienza media","sleep_efficiency_pct","pp"],
    ["Tempo sveglio","awake_minutes","min"],
    ["Latenza di addormentamento","sleep_latency_minutes","min"],
    ["Sleep Score","sleep_score","pt"]
  ];
  const table=e("table","feature-table"),head=e("thead"),tr=e("tr");
  ["Indicatore","Prima","Adesso","Differenza"].forEach(x=>a(tr,e("th","",x)));
  a(head,tr);a(table,head);
  const body=e("tbody");
  metrics.forEach(([title,key,unit])=>{
    const row=e("tr");
    const before=weekly.previous.averages[key],after=weekly.recent.averages[key];
    const d=weekly.delta_recent_vs_previous[key];
    a(row,e("td","",title),
      e("td","",key==="sleep_minutes"?duration(before):format(before,0)),
      e("td","",key==="sleep_minutes"?duration(after):format(after,0)),
      e("td","",sleepDelta(d,unit)));
    a(body,row);
  });
  a(table,body);
  a(comparison,table);
  const d=weekly.delta_recent_vs_previous.sleep_minutes;
  if(num(d)!==null){
    const text="La durata media del sonno negli ultimi sette giorni è "+
      (d===0?"in linea":d>0?"aumentata":"diminuita")+
      " di "+format(Math.abs(d),0)+" minuti rispetto ai sette precedenti. "+
      "Il risultato descrive una variazione: non stabilisce da solo se il sonno sia stato migliore.";
    a(comparison,hint(text,"info"));
  }else a(comparison,hint("Non ci sono abbastanza notti per confrontare con affidabilità i due periodi. Nessun dato mancante è stato trattato come zero.","info"));
  a(container,comparison);
  const hist=weekly.history||[];
  if(hist.length>2){
    const sec=section(),p=panel();
    a(sec,heading("Andamento dei periodi di 7 giorni","Cronologia dei blocchi settimanali"));
    const bars=e("div","sleep-week-history");
    hist.slice(0,8).forEach(w=>{
      const cell=e("div","sleep-history-row");
      const label=e("span","",shortDate(w.start)+" – "+shortDate(w.end));
      const avg=w.averages.sleep_minutes;
      const track=e("div","progress-track"),fill=e("div","progress-fill");
      fill.style.width=(num(avg)!==null?Math.min(100,avg/600*100):0)+"%";a(track,fill);
      a(cell,label,track,e("strong","",duration(avg)));
      a(bars,cell);
    });
    a(p,bars);a(sec,p);a(container,sec);
  }
  return container;
}
function sleepDaily(data){
  const report=data.sleep_intelligence,wrap=section();
  a(wrap,heading("Ogni notte a confronto","Seleziona un giorno per approfondire"));
  const nights=report.nights.filter(x=>x.main_sleep_available).slice().reverse();
  if(!nights.length){a(wrap,empty("Non ci sono notti registrate","Serve una sessione long_sleep valida.","moon"));return wrap;}
  if(!state.sleepDay||!nights.some(n=>n.day===state.sleepDay))
    state.sleepDay=nights[0].day;
  const picker=e("div","sleep-date-picker");
  const label=e("label","", "Notte da analizzare");
  label.htmlFor="sleep-date-select";
  const select=e("select","sleep-select");select.id="sleep-date-select";
  nights.forEach(n=>{
    const opt=e("option","",fullDate(n.day));
    opt.value=n.day;opt.selected=n.day===state.sleepDay;a(select,opt);
  });
  select.addEventListener("change",()=>setSelectedNight(select.value));
  a(picker,label,select);a(wrap,picker);
  const cards=e("div","sleep-night-rail");
  nights.slice(0,14).forEach(n=>{
    const chosen=n.day===state.sleepDay;
    const b=e("button","sleep-night-btn"+(chosen?" selected":""));
    b.type="button";b.setAttribute("aria-pressed",String(chosen));
    a(b,e("span","",shortDate(n.day)),e("strong","",duration(n.sleep_minutes)),
      e("small","",num(n.sleep_score)===null?"Score —":"Score "+format(n.sleep_score)));
    b.addEventListener("click",()=>setSelectedNight(n.day));
    a(cards,b);
  });
  a(wrap,cards);
  const night=nights.find(n=>n.day===state.sleepDay);
  const compare=report.daily_comparisons.find(c=>c.day===night.day);
  const split=e("div","sleep-night-detail");
  const main=panel("sleep-night-main");
  a(main,subhead("moon",fullDate(night.day),"Analisi della singola sessione principale di sonno"));
  const value=e("div","sleep-big-duration",duration(night.sleep_minutes));
  a(main,value,e("p","coverage-description",
    (night.bedtime_local||"—")+" → "+(night.wake_local||"—")+
    " · punto medio "+(night.sleep_midpoint_local||"—")));
  const measures=e("div","sleep-night-measures");
  [["Efficienza",night.sleep_efficiency_pct,"%"],
   ["Latenza",night.sleep_latency_minutes,"min"],
   ["Sveglio stimato",night.awake_minutes,"min"],
   ["Tempo a letto",night.time_in_bed_minutes,"min"],
   ["Sleep Score",night.sleep_score,"/100"],
   ["Periodi di irrequietezza",night.restless_periods,"stima Oura"],
   ["HRV notturna",night.hrv_ms,"ms"],
   ["FC minima",night.heart_rate_min_bpm,"bpm"],
   ["FC media",night.heart_rate_average_bpm,"bpm"],
   ["Respirazione",night.respiratory_rate,"atti/min"]].forEach(([name,val,unit])=>{
    const tile=e("div","sleep-night-measure");
    a(tile,e("span","",name),e("strong","",format(val,1)+(num(val)!==null?" "+unit:"")));
    a(measures,tile);
  });
  a(main,measures);
  const stages=panel("sleep-stage-panel");
  a(stages,subhead("activity","Composizione del sonno","Stime Oura, non polisonnografia"));
  const stageFields=[
    ["Profondo",night.deep_sleep_minutes,"deep"],
    ["REM",night.rem_sleep_minutes,"rem"],
    ["Leggero",night.light_sleep_minutes,"light"]
  ];
  stageFields.forEach(([label,val,kind])=>{
    const line=e("div","sleep-stage-item"),head=e("div","sleep-stage-header");
    const percentage=num(night.sleep_minutes)!==null && night.sleep_minutes>0 && num(val)!==null?
       val/night.sleep_minutes*100:null;
    a(head,e("span","",label),e("strong","",
      duration(val)+(percentage!==null?" · "+format(percentage,0)+"%":"")));
    const track=e("div","sleep-stage-track"),fill=e("div","sleep-stage-fill "+kind);
    fill.style.width=(percentage===null?0:Math.min(100,percentage))+"%";
    a(track,fill);a(line,head,track);a(stages,line);
  });
  if(night.phase_coverage!=="consistent")a(stages,hint(
    night.phase_coverage==="inconsistent"?
    "La somma delle fasi non coincide con il sonno totale: evita di interpretarne le percentuali come esatte.":
    "Alcune fasi non sono disponibili: la composizione non è completa.","info"));
  a(stages,hint("Le fasi REM/profondo hanno più incertezza delle metriche globali del sonno.","shield"));
  a(split,main,stages);a(wrap,split);
  const cardioLink=e("button","recovery-action","Analizza HRV e FC di questa notte");
  cardioLink.type="button";a(cardioLink,icon("heart"));
  cardioLink.addEventListener("click",()=>selectTab("recovery"));
  a(wrap,cardioLink);
  const comparisons=panel("section-block");
  a(comparisons,subhead("calendar","Questa notte rispetto alle altre",
    "Il confronto settimanale esclude sempre la notte selezionata"));
  const rows=e("table","feature-table"),head=e("thead"),h=e("tr");
  ["Metrica","Questa notte","Giorno prima","Media 7 precedenti"].forEach(v=>a(h,e("th","",v)));
  a(head,h);a(rows,head);
  const body=e("tbody");
  [["Durata","sleep_minutes","min"],["Efficienza","sleep_efficiency_pct","pp"],
   ["Tempo sveglio","awake_minutes","min"],["Latenza","sleep_latency_minutes","min"],
   ["REM","rem_sleep_minutes","min"],["Profondo","deep_sleep_minutes","min"],
   ["Sleep Score","sleep_score","pt"]].forEach(([label,key,unit])=>{
     const row=e("tr"),v=night[key],d=compare?.delta_vs_previous_day?.[key],
       w=compare?.delta_vs_previous7?.[key];
     a(row,e("td","",label),e("td","",key==="sleep_minutes"?duration(v):format(v,0)),
       e("td","",sleepDelta(d,unit)),e("td","",sleepDelta(w,unit)));
     a(body,row);
  });
  a(rows,body);a(comparisons,rows);
  if(!compare?.previous_day_exists)
    a(comparisons,hint("Manca una sessione principale il giorno precedente: quel confronto rimane vuoto.","info"));
  if((compare?.previous7_counts?.sleep_minutes||0)<4)
    a(comparisons,hint("Per la media delle sette notti precedenti servono almeno quattro misurazioni valide.","info"));
  a(comparisons,e("p","coverage-description","Le colonne 'Giorno prima' e 'Media 7 precedenti' mostrano la DIFFERENZA rispetto ai riferimenti, non i valori assoluti. Una differenza positiva non significa sempre miglioramento."));
  a(wrap,comparisons);
  return wrap;
}
function sleepView(data){
  if(!data.sleep_intelligence)return empty("Modulo non disponibile","Aggiorna il motore Oura sul Mac.","moon");
  const wrap=e("div"),tools=e("div","trend-toolbox");
  a(tools,e("span","section-subtitle","Esplora 7, 30 o 90 giorni"),
    segment([7,30,90],state.days,n=>load(n)));
  a(wrap,tools,sleepWeekly(data),sleepDaily(data),
    hint("Le analisi descrivono variazioni personali, non diagnosticano disturbi del sonno. L'assenza di dati non significa assenza di sonno.","shield"));
  return wrap;
}
function trainingView(data){
  const wrap=e("div");
  if(!data.meta.workout_history_available &&
      !(data.exercise_recovery && data.exercise_recovery.recorded_workout_days)){
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
  const minutes=rows.map(x=>num(x.workout_minutes_recorded)).filter(x=>x!==null);
  const sessionsWithDuration=rows.reduce((n,x)=>n+(num(x.workout_duration_sessions)||0),0);
  if(minutes.length){
    a(wrap,hint("Durata totale registrata: "+format(minutes.reduce((a,b)=>a+b,0),0)+
      " minuti su "+sessionsWithDuration+" sessioni con orario valido. Le altre durate sono sconosciute.", "clock"));
  }
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
  a(wrap,history,recoveryCurveCard(data.exercise_recovery));
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
  const views={today:todayView,sleep:sleepView,recovery:recoveryView,insights:insightsView,training:trainingView};
  a(root,views[state.tab](state.data));
}
function selectTab(tab){
  if(tab==="trends")tab="recovery";
  if(!labels[tab])return;
  state.tab=tab;syncRoute();render();
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
applyRoute();
window.addEventListener("hashchange",()=>{applyRoute();render();});
load(30);
