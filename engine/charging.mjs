// Weekly energy balance, not a guarantee of charger availability or trip feasibility.
const valid=x=>typeof x==='number'&&Number.isFinite(x)&&x>=0;
export function chargingSuitability(a){
 const {power,weeklyMiles,electricRange,kwhPerMile,homeKwh,workKwh,publicKwh,publicAccepted}=a;
 if(!['Fully electric','Plug-in hybrid'].includes(power))return {status:'not-applicable',electricShare:power==='Traditional hybrid'||power==='Gasoline'?0:null};
 const missing=['weeklyMiles','electricRange','kwhPerMile','homeKwh','workKwh'].filter(k=>!valid(a[k]));
 if(publicAccepted!==false&&publicAccepted!==true)missing.push('publicAccepted');
 if(publicAccepted===true&&!valid(publicKwh))missing.push('publicKwh');
 if(missing.length||!(electricRange>0)||!(kwhPerMile>0))return {status:'unknown',electricShare:null,missing};
 const demand=weeklyMiles*kwhPerMile,routine=homeKwh+workKwh,available=routine+(publicAccepted?publicKwh:0);
 const deficit=Math.max(0,demand-available);
 const publicNeeded=Math.max(0,demand-routine);
 const share=power==='Fully electric'?1:null;
 return {status:power==='Fully electric'&&deficit>0?'insufficient':publicNeeded>0&&publicAccepted&&publicKwh>0?'public-dependent':deficit>0?'gasoline-needed':'weekly-energy-covered',electricShare:share,potentialElectricShare:power==='Plug-in hybrid'&&demand>0?Math.min(1,available/demand):null,weeklyDemandKwh:demand,weeklyDeficitKwh:deficit,publicNeededKwh:publicNeeded,notes:['Weekly energy balance only; verify charging schedule, usable range, charger access and road trips.','PHEV electric share requires trip-level charging and driving assumptions.']};
}
