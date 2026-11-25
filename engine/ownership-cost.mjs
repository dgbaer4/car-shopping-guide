import {energyCost} from './recommendation.mjs';
const valid=x=>typeof x==='number'&&Number.isFinite(x)&&x>=0;

// All inputs are explicit USD or annual miles. Unknown costs stay unknown.
export function ownershipCost(a){
 const {years,purchasePrice,taxesFees,downPayment,apr,loanMonths,annualMiles,mpg,kwhPerMile,electricShare,gasPrice,electricPrice,annualMaintenance,annualInsurance,annualRegistration,resaleValue}=a;
 const netMissing=[];
 for(const k of ['purchasePrice','taxesFees','downPayment','apr','loanMonths','annualMaintenance','annualInsurance','annualRegistration','resaleValue'])if(!valid(a[k]))netMissing.push(k);
 if(!Number.isInteger(years)||years<=0)netMissing.push('years');
 const energy=energyCost({miles:annualMiles,mpg,kwhPerMile,electricShare,gasPrice,electricPrice});
 if(energy===null)netMissing.push('energy');
 const missing=netMissing.filter(field=>field!=='resaleValue');
 if(missing.length)return {total:null,missing:netMissing,cashOutlay:{total:null,missing}};
 const principal=purchasePrice+taxesFees-downPayment;
 if(principal<0||!Number.isInteger(loanMonths)||(principal>0&&loanMonths===0))throw Error('Invalid financing');
 const r=apr/12, n=loanMonths;
 const payment=principal===0?0:r===0?principal/n:principal*r/(-Math.expm1(-n*Math.log1p(r)));
 const payments=Math.min(n,years*12);
 let balance=principal,interest=0;
 for(let i=0;i<payments;i++){const charge=balance*r;interest+=charge;balance=Math.max(0,balance+charge-payment);}
 const operating={energy:energy*years,maintenance:annualMaintenance*years,insurance:annualInsurance*years,registration:annualRegistration*years};
 const operatingTotal=Object.values(operating).reduce((sum,value)=>sum+value,0);
 const cashTotal=downPayment+payments*payment+operatingTotal;
 const cashOutlay={total:cashTotal,annual:cashTotal/years,missing:[]};
 if(netMissing.length)return {total:null,missing:netMissing,cashOutlay,remainingLoanBalance:balance};
 const components={depreciation:purchasePrice-resaleValue,taxesFees,interest,...operating};
 const total=Object.values(components).reduce((x,y)=>x+y,0);
 return {total,annual:total/years,perMile:annualMiles>0?total/(annualMiles*years):null,monthlyLoanPayment:payment,remainingLoanBalance:balance,components,missing:[],cashOutlay};
}
export function ownershipScenarios(scenarios){return Object.fromEntries(Object.entries(scenarios).map(([k,v])=>[k,ownershipCost(v)]));}
