import test from 'node:test';import assert from 'node:assert/strict';import {ownershipCost} from '../engine/ownership-cost.mjs';
const a={years:5,purchasePrice:20000,taxesFees:2000,downPayment:22000,apr:0,loanMonths:0,annualMiles:10000,mpg:40,electricShare:0,gasPrice:4,annualMaintenance:500,annualInsurance:1000,annualRegistration:200,resaleValue:10000};
test('cash cost',()=>assert.equal(ownershipCost(a).total,25500));
test('unknown insurance',()=>assert.equal(ownershipCost({...a,annualInsurance:null}).total,null));
test('zero interest financing',()=>{const r=ownershipCost({...a,downPayment:2000,loanMonths:60});assert.equal(r.total,25500);assert.ok(Math.abs(r.remainingLoanBalance)<1e-8)});
test('positive interest and remaining balance',()=>{const r=ownershipCost({...a,years:2,downPayment:2000,apr:.06,loanMonths:60});assert.ok(r.components.interest>0);assert.ok(r.remainingLoanBalance>0)});
