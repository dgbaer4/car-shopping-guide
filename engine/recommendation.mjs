// v0.3 foundation. No network or AI dependencies.
export function normalize(profile) {
 if(profile?.schemaVersion !== '0.2' || !profile.answers || !profile.features) throw Error('Unsupported buyer profile');
 const a=profile.answers, warnings=[];
 const pick=(key,allowed)=>allowed.includes(a[key])?a[key]:null;
 const choices=(key,allowed)=>Array.isArray(a[key])?[...new Set(a[key].filter(x=>allowed.includes(x)))]:[];
 const range=(key,table)=>table[a[key]]??null;
 const power=choices('power',['Gasoline','Traditional hybrid','Plug-in hybrid','Fully electric']);
 const styles=['Sedan','Hatchback','Wagon','Compact crossover','Midsize SUV','Full-size SUV','Pickup'];
 const body=choices('body',styles),avoid=choices('avoid',styles);
 if(body.some(x=>avoid.includes(x)))warnings.push('Conflicting body preferences; exclusions take precedence');
 const plug=!power.length||power.some(x=>['Plug-in hybrid','Fully electric'].includes(x));
 const condition=pick('condition',['New only','Prefer new','Prefer used','Used only','No preference']);
 const f=a.equipment==='Yes, let’s explore'?profile.features:{};
 const featureKeys=status=>Object.keys(f).filter(k=>f[k]===status);
 const required=featureKeys('Required'),prohibited=featureKeys('Prohibited');
 for(const base of ['Apple CarPlay','Android Auto'])if(required.includes('Wireless '+base)&&prohibited.includes(base))warnings.push('Conflicting equipment: '+base);
 const budgetRange=range('budget',{'Under $15,000':[0,15000],'$15,000–$18,000':[15000,18000],'$18,000–$22,000':[18000,22000],'$22,000–$25,000':[22000,25000],'$25,000–$30,000':[25000,30000],'Over $30,000':[30000,null]});
 const budgetMode=a.budget==='No budget restriction'?'unrestricted':budgetRange?'range':["I'm not sure",'Unsure'].includes(a.budget)?'unsure':null;
 const flex=budgetMode==='unrestricted'?null:range('flex',{'None':0,'Up to $1,000':1000,'Up to $2,000':2000,'Up to $3,000':3000});
 const priorities=choices('priorities',['Reliability','Low maintenance','Purchase affordability','Operating costs','Safety','Comfort','Environmental impact','Technology','Driving enjoyment']);
 if(priorities.length>3)warnings.push('More than three priorities selected');
 const commute=range('commute',{'Under 10 miles':[0,10],'10–25 miles':[10,25],'26–50 miles':[26,50],'51–100 miles':[51,100],'Over 100 miles':[100,null],'I do not commute':[0,0]});
 const days=a.commute==='I do not commute'?[0,0]:range('days',{'1–2':[1,2],'3–4':[3,4],'5':[5,5],'6–7':[6,7]});
 const annualMiles=range('annual',{'Under 5,000':[0,5000],'5,000–10,000':[5000,10000],'10,000–15,000':[10000,15000],'Over 15,000':[15000,null]});
 const ownershipYears=range('keep',{'Under 3 years':[0,3],'3–5 years':[3,5],'6–10 years':[6,10],'Over 10 years':[10,null]});
 const work=plug?pick('work',['Almost always','Usually','Occasionally','Not available']):null;
 return {budgetMode,budget:budgetRange?.[1]??null,budgetRange,budgetExclusive:a.budget==='Under $15,000',flex,allIn:budgetMode==='unrestricted'?null:a.fees==='Yes, everything'?true:a.fees==='No, vehicle price only'?false:null,
 power,body,avoid,condition,maxAge:condition==='New only'?null:range('age',{'Up to 3 years':3,'Up to 5 years':5,'Up to 7 years':7,'Up to 10 years':10}),maxMileage:condition==='New only'?null:range('mileage',{'Under 30,000':30000,'Under 50,000':50000,'Under 75,000':75000,'Under 100,000':100000}),
 required,prohibited,desired:featureKeys('Desired'),warranty:pick('warranty',['Required','Desired','No preference']),seat:pick('seat',['Required','Desired','No preference','Prefer lower seating']),people:pick('people',['1–2 people','3–5 people','6 or more']),
 home:plug?pick('home',['Yes','No','Possibly']):null,work,public:plug?pick('public',['Yes','If convenient','Prefer not to','No']):null,roadcharge:plug?pick('roadcharge',['Not at all','Occasionally acceptable','Prefer to avoid them']):null,
 workRate:plug&&work!=='Not available'?range('rate',{'Free':[0,0],'Under $0.25/kWh':[0,.25],'$0.25–$0.40/kWh':[.25,.40],'Over $0.40/kWh':[.40,null]}):null,
 payment:pick('payment',['Cash','Finance','No preference']),commute,days,annualMiles,ownershipYears,annual:a.annual??null,keep:a.keep??null,trips:pick('trips',['Weekly','Monthly','A few times a year','Rarely']),cargo:pick('cargo',['Frequently','Occasionally','Rarely','No preference']),maintenance:pick('maintenance',['Yes','Possibly','No']),priorities,top:priorities.includes(a.top)?a.top:null,warnings};
}
const used2027Available = new Date(2027, 5, 30);

export function evaluate(p,v,year,asOf = new Date()) {
 const rejected=[],unknown=[],notes=[];
 const check=(label,value)=>{if(value===false)rejected.push(label);else if(value!==true)unknown.push(label)};
 if(p.power.length)check('Powertrain',v.power==null?null:p.power.includes(v.power));
 if(p.avoid.length)check('Excluded body style',v.body==null?null:!p.avoid.includes(v.body));
 if(p.condition==='New only'||p.condition==='Used only')check('Condition',v.condition==null?null:v.condition===(p.condition==='New only'?'new':'used'));
 if(p.condition==='Used only'&&v.year===2027&&asOf<used2027Available)rejected.push('Model year not yet eligible for used-only recommendations');
 if(p.maxAge!=null&&v.condition!=='new')check('Model age',v.year==null?null:year-v.year<=p.maxAge);
 if(p.maxMileage!=null&&v.condition!=='new')check('Mileage',v.mileage==null?null:v.mileage<p.maxMileage);
 if(p.budget!=null){const price=p.allIn===true?v.outTheDoorPrice:p.allIn===false?v.price:null;check('Budget',price==null?null:price<p.budget||(!p.budgetExclusive&&price===p.budget)?true:p.flex==null?null:p.budgetExclusive?price<p.budget+p.flex:price<=p.budget+p.flex);if(price!=null&&price>p.budget)notes.push('Above preferred budget');}
 if(p.warranty==='Required')check('Remaining manufacturer warranty',v.warranty);
 if(p.seat==='Required')check('Higher seating',v.highSeating);
 if(p.people==='6 or more'||p.people==='3–5 people')check('Passenger capacity',v.seats==null?null:v.seats>=(p.people==='6 or more'?6:5));
 for(const k of p.required)check(k,v.features?.[k]);
 for(const k of p.prohibited)check('Prohibited: '+k,typeof v.features?.[k]==='boolean'?!v.features[k]:null);
 const matched=p.desired.filter(k=>v.features?.[k]===true), missing=p.desired.filter(k=>v.features?.[k]===false), unverified=p.desired.filter(k=>typeof v.features?.[k]!=='boolean');
 if(['Fully electric','Plug-in hybrid'].includes(v.power)&&p.home==='No'&&!['Almost always','Usually'].includes(p.work))notes.push('Limited routine charging; verify charging costs and access.');
 if(v.power==='Fully electric'&&p.home==='No'&&p.work==='Not available'&&p.public==='No')rejected.push('No acceptable charging access');
 if(p.body.length&&v.body&&!p.body.includes(v.body))notes.push('Outside preferred body styles');
 return {id:v.id,status:rejected.length?'excluded':unknown.length?'conditional':'eligible',rejected,unknown,notes,matched,missing,unverified,equipmentScore:p.desired.length&&!unverified.length?matched.length/p.desired.length:null};
}
export function energyCost({miles,mpg,kwhPerMile,electricShare,gasPrice,electricPrice}) {
 if(!Number.isFinite(miles)||miles<0||!Number.isFinite(electricShare)||electricShare<0||electricShare>1)return null;
 if(electricShare<1&&(!(mpg>0)||!Number.isFinite(gasPrice)||gasPrice<0))return null;
 if(electricShare>0&&(!(kwhPerMile>0)||!Number.isFinite(electricPrice)||electricPrice<0))return null;
 return (electricShare<1?miles*(1-electricShare)/mpg*gasPrice:0)+(electricShare>0?miles*electricShare*kwhPerMile*electricPrice:0);
}
