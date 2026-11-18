import {describe,it,expect} from 'vitest';
import {workbookFromRows} from './xlsxExport';
describe('Excel export',()=>{
 it('creates a real ZIP-based XLSX with correct MIME type',async()=>{
  const file=workbookFromRows([{name:'Station & A',id:7}],['name','id']);
  expect(file.type).toContain('spreadsheetml.sheet');
  const bytes=new Uint8Array(await file.arrayBuffer());
  expect(Array.from(bytes.slice(0,4))).toEqual([80,75,3,4]);
  expect(new TextDecoder().decode(bytes)).toContain('Station &amp; A');
 });
});
