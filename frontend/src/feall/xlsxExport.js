// Dependency-free OOXML writer for exporting a single worksheet (Excel .xlsx).
const encoder = new TextEncoder();
const xml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const letters = index => {let result='';for(let n=index+1;n;n=Math.floor((n-1)/26))result=String.fromCharCode(65+(n-1)%26)+result;return result;};
const text = value => value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const crcTable = Array.from({length:256},(_,n)=>{let c=n;for(let i=0;i<8;i++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
const crc32 = bytes => {let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return (c^0xffffffff)>>>0;};
function zip(files){
 const parts=[],central=[];let offset=0;
 const u16=(v)=>[v&255,(v>>>8)&255],u32=v=>[v&255,(v>>>8)&255,(v>>>16)&255,(v>>>24)&255];
 for(const [name,body] of Object.entries(files)){
  const path=encoder.encode(name),data=encoder.encode(body),crc=crc32(data);
  const header=new Uint8Array([80,75,3,4,20,0,0,8,0,0,0,0,0,0,...u32(crc),...u32(data.length),...u32(data.length),...u16(path.length),0,0]);
  parts.push(header,path,data);
  central.push(new Uint8Array([80,75,1,2,20,0,20,0,0,8,0,0,0,0,0,0,...u32(crc),...u32(data.length),...u32(data.length),...u16(path.length),0,0,0,0,0,0,0,0,0,0,0,0,...u32(offset)]),path);
  offset+=header.length+path.length+data.length;
 }
 const centralLength=central.reduce((sum,p)=>sum+p.length,0);
 const end=new Uint8Array([80,75,5,6,0,0,0,0,...u16(Object.keys(files).length),...u16(Object.keys(files).length),...u32(centralLength),...u32(offset),0,0]);
 return new Blob([...parts,...central,end],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
export function workbookFromRows(rows,fields){
 const grid=[fields,...rows.map(row=>fields.map(key=>text(row[key])))];
 const sheet=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${grid.map((values,i)=>`<row r="${i+1}">${values.map((value,j)=>`<c r="${letters(j)}${i+1}" t="inlineStr"><is><t>${xml(value)}</t></is></c>`).join('')}</row>`).join('')}</sheetData></worksheet>`;
 return zip({
  '[Content_Types].xml':'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
  '_rels/.rels':'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
  'xl/workbook.xml':'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Metadata" sheetId="1" r:id="rId1"/></sheets></workbook>',
  'xl/_rels/workbook.xml.rels':'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
  'xl/worksheets/sheet1.xml':sheet,
 });
}
