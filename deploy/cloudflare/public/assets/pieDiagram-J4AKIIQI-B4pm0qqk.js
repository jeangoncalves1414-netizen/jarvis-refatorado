import{p as tt}from"./chunk-JWPE2WC7--Vz6N74M.js";import{g as et,s as at,a as rt,b as it,y as nt,x as st,c as l,l as E,d as ot,R as lt,U as ct,V as dt,W as I,X as gt,e as ht,D as pt,Y as ut,S as ft}from"./vendor-mermaid-DMzIeuR7.js";import{p as mt}from"./cynefin-EF2NZ3EQ-CIKxS4pU.js";import"./vendor-icons-De-6aXjJ.js";var vt=ft.pie,R={sections:new Map,showData:!1},T=R.sections,W=R.showData,St=structuredClone(vt),xt=l(()=>structuredClone(St),"getConfig"),wt=l(()=>{T=new Map,W=R.showData,pt()},"clear"),$t=l(({label:t,value:a})=>{if(a<0)throw new Error(`"${t}" has invalid value: ${a}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);T.has(t)||(T.set(t,a),E.debug(`added new section: ${t}, with value: ${a}`))},"addSection"),Ct=l(()=>T,"getSections"),Dt=l(t=>{W=t},"setShowData"),yt=l(()=>W,"getShowData"),U={getConfig:xt,clear:wt,setDiagramTitle:st,getDiagramTitle:nt,setAccTitle:it,getAccTitle:rt,setAccDescription:at,getAccDescription:et,addSection:$t,getSections:Ct,setShowData:Dt,getShowData:yt},Tt=l((t,a)=>{tt(t,a),a.setShowData(t.showData),t.sections.map(a.addSection)},"populateDb"),bt={parse:l(async t=>{const a=await mt("pie",t);E.debug(a),Tt(a,U)},"parse")},At=l(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieCircle.highlighted{
    scale: 1.05;
    opacity: 1;
  }
  .pieCircle.highlightedOnHover:hover{
    transition-duration: 250ms;
    scale: 1.05;
    opacity: 1;
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),kt=At,_t=l(t=>{const a=[...t.values()].reduce((s,m)=>s+m,0),L=[...t.entries()].map(([s,m])=>({label:s,value:m})).filter(s=>s.value/a*100>=1);return ut().value(s=>s.value).sort(null)(L)},"createPieArcs"),zt=l((t,a,L,F)=>{E.debug(`rendering pie chart
`+t);const s=F.db,m=ot(),p=lt(s.getConfig(),m.pie),H=40,i=18,c=4,$=450,S=$,b=ct(a),C=b.append("g");C.attr("transform","translate("+S/2+","+$/2+")");const{themeVariables:n}=m;let[M]=dt(n.pieOuterStrokeWidth);M??=2;const V=p.legendPosition,O=p.textPosition,X=p.donutHole>0&&p.donutHole<=.9?p.donutHole:0,u=Math.min(S,$)/2-H,Y=I().innerRadius(X*u).outerRadius(u),Z=I().innerRadius(u*O).outerRadius(u*O),x=C.append("g");x.append("circle").attr("cx",0).attr("cy",0).attr("r",u+M/2).attr("class","pieOuterCircle");const D=s.getSections(),j=_t(D),q=[n.pie1,n.pie2,n.pie3,n.pie4,n.pie5,n.pie6,n.pie7,n.pie8,n.pie9,n.pie10,n.pie11,n.pie12];let A=0;D.forEach(e=>{A+=e});const P=j.filter(e=>(e.data.value/A*100).toFixed(0)!=="0"),k=gt(q).domain([...D.keys()]);x.selectAll("mySlices").data(P).enter().append("path").attr("d",Y).attr("fill",e=>k(e.data.label)).attr("class",e=>{let r="pieCircle";return p.highlightSlice==="hover"?r+=" highlightedOnHover":p.highlightSlice===e.data.label&&(r+=" highlighted"),r}),x.selectAll("mySlices").data(P).enter().append("text").text(e=>(e.data.value/A*100).toFixed(0)+"%").attr("transform",e=>"translate("+Z.centroid(e)+")").style("text-anchor","middle").attr("class","slice");const J=C.append("text").text(s.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText"),w=[...D.entries()].map(([e,r])=>({label:e,value:r})),f=C.selectAll(".legend").data(w).enter().append("g").attr("class","legend");f.append("rect").attr("width",i).attr("height",i).style("fill",e=>k(e.label)).style("stroke",e=>k(e.label)),f.append("text").attr("x",i+c).attr("y",i-c).text(e=>s.getShowData()?`${e.label} [${e.value}]`:e.label);const v=Math.max(...f.selectAll("text").nodes().map(e=>e?.getBoundingClientRect().width??0));let y=$,_=S+H;const o=i+c,z=w.length*o;switch(V){case"center":f.attr("transform",(e,r)=>{const d=o*w.length/2,g=-v/2-(i+c),h=r*o-d;return"translate("+g+","+h+")"});break;case"top":y+=z,f.attr("transform",(e,r)=>{const d=u,g=-v/2-(i+c),h=r*o-d;return`translate(${g}, ${h})`}),x.attr("transform",()=>`translate(0, ${z+o})`);break;case"bottom":y+=z,f.attr("transform",(e,r)=>{const d=-u-o,g=-v/2-(i+c),h=r*o-d;return"translate("+g+","+h+")"});break;case"left":_+=i+c+v,f.attr("transform",(e,r)=>{const d=o*w.length/2,g=-u-(i+c),h=r*o-d;return"translate("+g+","+h+")"}),x.attr("transform",()=>`translate(${v+i+c}, 0)`);break;default:_+=i+c+v,f.attr("transform",(e,r)=>{const d=o*w.length/2,g=12*i,h=r*o-d;return"translate("+g+","+h+")"});break}const G=J.node()?.getBoundingClientRect().width??0,K=S/2-G/2,Q=S/2+G/2,B=Math.min(0,K),N=Math.max(_,Q)-B;b.attr("viewBox",`${B} 0 ${N} ${y}`),ht(b,y,N,p.useMaxWidth)},"draw"),Et={draw:zt},Mt={parser:bt,db:U,renderer:Et,styles:kt};export{Mt as diagram};
