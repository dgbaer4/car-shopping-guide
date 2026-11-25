import test from 'node:test';
import assert from 'node:assert/strict';
import {explain} from '../engine/explanation.mjs';
const p={required:['Backup camera'],desired:['Spare tire','Heated front seats'],power:['Traditional hybrid'],body:['Sedan']};
const v={power:'Traditional hybrid',body:'Sedan',features:{'Backup camera':true,'Spare tire':false}};
test('distinguishes absent and unknown equipment',()=>{
 const r=explain(p,v,{status:'eligible',matched:[],weights:{safety:1},components:{},scoreLower:0,scoreUpper:100});
 assert.ok(r.strengths.includes('Required equipment confirmed: Backup camera'));
 assert.ok(r.tradeoffs.includes('Desired equipment absent: Spare tire'));
 assert.ok(r.verify.includes('Desired equipment unverified: Heated front seats'));
 assert.equal(r.score,null);
});
test('conditional candidates never receive definitive scores',()=>{
 const r=explain(p,v,{status:'conditional',unknown:['Budget'],score:90});
 assert.equal(r.score,null);
 assert.ok(r.verify.includes('Requirement unverified: Budget'));
});
test('excluded candidates retain rejection reasons',()=>{
 const r=explain(p,v,{status:'excluded',rejected:['Mileage']});
 assert.ok(r.tradeoffs.includes('Requirement not met: Mileage'));
 assert.equal(r.score,null);
});
