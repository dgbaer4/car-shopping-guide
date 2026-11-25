import test from 'node:test';
import assert from 'node:assert/strict';
import {results,classification} from '../engine/results.mjs';
const p={power:[],avoid:[],required:[],prohibited:[],desired:[],body:[],priorities:[]};
const vehicles=Array.from({length:7},(_,i)=>({id:String(i),make:'Fixture',model:'Test',year:2025}));
test('five initial results and expansion',()=>{
 const r=results(p,vehicles,2026);
 assert.equal(r.items.length,5);assert.equal(r.hasMore,true);
 assert.equal(results(p,vehicles,2026,{limit:r.nextLimit}).items.length,7);
 assert.equal(r.items[0].ownership.monthly,null);
 assert.equal(r.items[0].classification,'Potential match');
 assert.equal('score' in r.items[0].explanation,false);
});
test('classification requires complete eligible score',()=>{
 assert.equal(classification({status:'conditional',score:99}),'Potential match');
 assert.equal(classification({status:'eligible',score:85}),'Strong match');
 assert.equal(classification({status:'eligible',score:70}),'Good match');
});
