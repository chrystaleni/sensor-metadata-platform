import {describe,it,expect} from 'vitest';
import {extractImportErrors} from './excelErrors';
describe('Excel import error presentation',()=>{
 it('handles row errors',()=>{
  expect(extractImportErrors({row_errors:[{sheet:'Devices',row:4,field:'id',message:'Required'}]})).toEqual([{sheet:'Devices',row:4,field:'id',message:'Required'}]);
 });
 it('handles field validation errors and Django-style arrays',()=>{
  expect(extractImportErrors({validation_errors:{file:['Invalid format']}})[0]).toMatchObject({field:'file',message:'Invalid format'});
 });
 it('handles detail objects',()=>{
  expect(extractImportErrors({detail:[{loc:['body','file'],msg:'Missing file'}]})[0]).toMatchObject({field:'body.file',message:'Missing file'});
 });
});
