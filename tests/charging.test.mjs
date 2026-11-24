import test from 'node:test';import assert from 'node:assert/strict';import {chargingSuitability as c} from '../engine/charging.mjs';
const a={power:'Fully electric',weeklyMiles:100,electricRange:200,kwhPerMile:.3,homeKwh:0,workKwh:10,publicAccepted:true,publicKwh:20};
test('public dependence',()=>assert.equal(c(a).status,'public-dependent'));
test('no public access',()=>assert.equal(c({...a,publicAccepted:false}).status,'insufficient'));
test('unknown work charging',()=>assert.equal(c({...a,workKwh:null}).status,'unknown'));
test('PHEV share not inferred from weekly energy',()=>assert.equal(c({...a,power:'Plug-in hybrid'}).electricShare,null));
test('routine charging',()=>assert.equal(c({...a,homeKwh:30}).status,'weekly-energy-covered'));
