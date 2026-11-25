import {rank} from './scoring.mjs';
import {explain} from './explanation.mjs';
import {ownershipCost} from './ownership-cost.mjs';
export const PAGE_SIZE=5;
export function classification(row){
 if(row.status==='excluded')return 'Does not match';
 if(row.status==='conditional'||!Number.isFinite(row.score))return 'Potential match';
 return row.score>=85?'Strong match':row.score>=70?'Good match':'Potential match';
}
export function results(profile,vehicles,year,{metricsById={},costById={},limit=PAGE_SIZE}={}){
 if(!Number.isInteger(limit)||limit<1)throw Error('Invalid results limit');
 const byId=new Map(vehicles.map(v=>[v.id,v]));
 if(byId.size!==vehicles.length)throw Error('Duplicate vehicle ID');
 const ranked=rank(profile,vehicles,year,metricsById);
 const candidates=ranked.filter(r=>r.status!=='excluded');
 const items=candidates.slice(0,limit).map(r=>{
  const v=byId.get(r.id), input=costById[r.id];
  const cost=input?ownershipCost(input):{total:null,missing:['Ownership assumptions']};
  const {score,scoreRange,...explanation}=explain(profile,v,r);
  return {id:r.id,make:v.make,model:v.model,year:v.year,trim:v.trim,power:v.power,classification:classification(r),explanation,ownership:{years:input?.years??null,total:cost.total,annual:cost.annual??null,monthly:cost.annual==null?null:cost.annual/12,missing:cost.missing,assumptions:input??null}};
 });
 return {items,totalCandidates:candidates.length,excludedCount:ranked.length-candidates.length,hasMore:candidates.length>limit,nextLimit:limit+PAGE_SIZE};
}
