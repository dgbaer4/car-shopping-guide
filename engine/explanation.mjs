// Deterministic, evidence-limited presentation of evaluated candidates.
export function explain(profile, vehicle, result) {
 if (!['eligible','conditional','excluded'].includes(result?.status)) throw Error('Invalid evaluation status');
 const strengths=[], tradeoffs=[], verify=[];
 const features=vehicle.features??{};
 for(const name of profile.required??[]) if(features[name]===true) strengths.push('Required equipment confirmed: '+name);
 for(const name of result.matched??[]) strengths.push('Desired equipment confirmed: '+name);
 for(const name of profile.desired??[]) {
  if(features[name]===false) tradeoffs.push('Desired equipment absent: '+name);
  else if(typeof features[name]!=='boolean') verify.push('Desired equipment unverified: '+name);
 }
 if(profile.power?.includes(vehicle.power)) strengths.push('Matches selected powertrain: '+vehicle.power);
 if(profile.body?.includes(vehicle.body)) strengths.push('Matches preferred body style: '+vehicle.body);
 for(const reason of result.rejected??[]) tradeoffs.push('Requirement not met: '+reason);
 for(const reason of result.unknown??[]) verify.push('Requirement unverified: '+reason);
 for(const note of result.notes??[]) tradeoffs.push(note);
 const missingMetrics=Object.keys(result.weights??{}).filter(k=>!Object.hasOwn(result.components??{},k));
 for(const key of missingMetrics) verify.push('Scoring evidence unavailable: '+key);
 const headline={eligible:'Meets evaluated requirements',conditional:'Candidate requiring verification',excluded:'Does not meet selected requirements'}[result.status];
 return {status:result.status,headline,strengths:[...new Set(strengths)],tradeoffs:[...new Set(tradeoffs)],verify:[...new Set(verify)],score:result.status==='eligible'&&missingMetrics.length===0&&Number.isFinite(result.score)?result.score:null,scoreRange:Number.isFinite(result.scoreLower)&&Number.isFinite(result.scoreUpper)?[result.scoreLower,result.scoreUpper]:null};
}
