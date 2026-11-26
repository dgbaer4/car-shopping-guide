import {evaluate} from './recommendation.mjs';
export const BASE_WEIGHTS=Object.freeze({safety:25,reliability:15,maintenance:10,economics:20,suitability:20,equipment:10});
const mapping={'Safety':'safety','Reliability':'reliability','Low maintenance':'maintenance','Operating costs':'economics','Purchase affordability':'economics'};
export function weightsFor(p){
 const w={...BASE_WEIGHTS};
 for(const key of new Set((p.priorities??[]).map(x=>mapping[x]).filter(Boolean)))w[key]*=1.25;
 if(mapping[p.top])w[mapping[p.top]]*=1.5;
 const total=Object.values(w).reduce((a,b)=>a+b,0);
 return Object.fromEntries(Object.entries(w).map(([k,v])=>[k,v/total]));
}
export function score(p,v,year,metrics={},asOf){
 const result=evaluate(p,v,year,asOf), weights=weightsFor(p);
 const values={...metrics,equipment:result.equipmentScore};
 const components={},missing=[];let lower=0,coverage=0;
 for(const [k,w] of Object.entries(weights)){
  const value=values[k];
  if(typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1){
   lower+=w*value;coverage+=w;components[k]=value;
  }else missing.push(k);
 }
 return {...result,weights,components,missing,coverage,scoreLower:100*lower,scoreUpper:100*(lower+1-coverage),score:missing.length||result.status!=='eligible'?null:100*lower};
}
// Confirmed matches precede conditional candidates; incomplete candidates are not ranked by invented values.
export function rank(p,vehicles,year,metricsById={},asOf){
 const rows=vehicles.map(v=>score(p,v,year,metricsById[v.id],asOf));
 const order={eligible:0,conditional:1,excluded:2};
 return rows.sort((a,b)=>order[a.status]-order[b.status]||(b.score??-1)-(a.score??-1)||a.id.localeCompare(b.id));
}
