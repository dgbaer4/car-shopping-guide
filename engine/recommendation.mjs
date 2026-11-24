// v0.3 foundation. No network or AI dependencies.
export function normalize(profile) {
 if(profile?.schemaVersion !== '0.2' || !profile.answers || !profile.features) throw Error('Unsupported buyer profile');
 const a=profile.answers, f=a.equipment==='Yes, let’s explore'?profile.features:{};
 const numbers=s=>[...String(s??'').matchAll(/\d[\d,]*/g)].map(m=>Number(m[0].replaceAll(',','')));
 const max=s=>numbers(s).at(-1)??null;
 const choices=s=>Array.isArray(s)?s.filter(x=>!['No preference',"I'm not sure",'None'].includes(x)):[];
 const budget=/^(Under|\$)/.test(a.budget)?max(a.budget):null;
 return {budget,flex:a.flex==='None'?0:max(a.flex),allIn:a.fees==='Yes, everything'?true:a.fees==='No, vehicle price only'?false:null,
 power:choices(a.power),body:choices(a.body),avoid:choices(a.avoid),condition:a.condition,maxAge:max(a.age),maxMileage:max(a.mileage),
 required:Object.keys(f).filter(k=>f[k]==='Required'),prohibited:Object.keys(f).filter(k=>f[k]==='Prohibited'),desired:Object.keys(f).filter(k=>f[k]==='Desired'),
 warranty:a.warranty,seat:a.seat,people:a.people,home:a.home,work:a.work,public:a.public,priorities:choices(a.priorities),top:a.top,annual:a.annual,keep:a.keep};
}
export function evaluate(p,v,year) {
 const rejected=[],unknown=[],notes=[];
 const check=(label,value)=>{if(value===false)rejected.push(label);else if(value!==true)unknown.push(label)};
 if(p.power.length)check('Powertrain',v.power==null?null:p.power.includes(v.power));
 if(p.avoid.length)check('Excluded body style',v.body==null?null:!p.avoid.includes(v.body));
 if(p.condition==='New only'||p.condition==='Used only')check('Condition',v.condition==null?null:v.condition===(p.condition==='New only'?'new':'used'));
 if(p.maxAge!=null&&v.condition!=='new')check('Model age',v.year==null?null:year-v.year<=p.maxAge);
 if(p.maxMileage!=null&&v.condition!=='new')check('Mileage',v.mileage==null?null:v.mileage<p.maxMileage);
 if(p.budget!=null){const price=p.allIn===true?v.outTheDoorPrice:p.allIn===false?v.price:null;check('Budget',price==null?null:price<=p.budget+(p.flex??0));if(price!=null&&price>p.budget)notes.push('Above preferred budget');}
 if(p.warranty==='Required')check('Remaining manufacturer warranty',v.warranty);
 if(p.seat==='Required')check('Higher seating',v.highSeating);
 if(p.people==='6 or more'||p.people==='3–5 people')check('Passenger capacity',v.seats==null?null:v.seats>=(p.people==='6 or more'?6:5));
 for(const k of p.required)check(k,v.features?.[k]);
 for(const k of p.prohibited)check('Prohibited: '+k,typeof v.features?.[k]==='boolean'?!v.features[k]:null);
 const matched=p.desired.filter(k=>v.features?.[k]===true), missing=p.desired.filter(k=>v.features?.[k]===false), unverified=p.desired.filter(k=>typeof v.features?.[k]!=='boolean');
 if(['Fully electric','Plug-in hybrid'].includes(v.power)&&p.home==='No'&&!['Almost always','Usually'].includes(p.work))notes.push('Limited routine charging; verify charging costs and access.');
 if(v.power==='Fully electric'&&p.home==='No'&&p.work==='Not available'&&p.public==='No')rejected.push('No acceptable charging access');
 if(p.body.length&&v.body&&!p.body.includes(v.body))notes.push('Outside preferred body styles');
 return {id:v.id,status:rejected.length?'excluded':unknown.length?'conditional':'eligible',rejected,unknown,notes,matched,missing,unverified,equipmentScore:p.desired.length?matched.length/p.desired.length:null};
}
export function energyCost({miles,mpg,kwhPerMile,electricShare,gasPrice,electricPrice}) {
 if(!Number.isFinite(miles)||miles<0||!Number.isFinite(electricShare)||electricShare<0||electricShare>1)return null;
 if(electricShare<1&&(!(mpg>0)||!Number.isFinite(gasPrice)||gasPrice<0))return null;
 if(electricShare>0&&(!(kwhPerMile>0)||!Number.isFinite(electricPrice)||electricPrice<0))return null;
 return (electricShare<1?miles*(1-electricShare)/mpg*gasPrice:0)+(electricShare>0?miles*electricShare*kwhPerMile*electricPrice:0);
}
