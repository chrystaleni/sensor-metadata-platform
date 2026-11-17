export function messageOf(value){
  if(typeof value==='string')return value;
  if(Array.isArray(value))return value.map(messageOf).filter(Boolean).join('; ');
  if(value&&typeof value==='object')return Object.entries(value).map(([key,val])=>`${key}: ${messageOf(val)}`).join('; ');
  return value==null?'':String(value);
}

export function extractImportErrors(payload){
  if(!payload || typeof payload!=='object')return [];
  const candidates=[payload.errors,payload.row_errors,payload.validation_errors,payload.detail];
  const results=[];
  for(const value of candidates){
    if(!value || typeof value==='string')continue;
    if(Array.isArray(value)){
      for(const item of value){
        if(item&&typeof item==='object')results.push({sheet:item.sheet||'—',row:item.row??'—',field:item.field||item.loc?.join('.')||'—',message:messageOf(item.message||item.msg||item.detail||item.error||item)});
        else results.push({sheet:'—',row:'—',field:'—',message:messageOf(item)});
      }
    }else if(typeof value==='object'){
      for(const [field,errors] of Object.entries(value))results.push({sheet:'—',row:'—',field,message:messageOf(errors)});
    }
  }
  return results;
}


// Flatten grouped errors such as {errors: {Devices: {4: {name: ['Required']}}}}.
export function groupedImportErrors(payload){
 const existing=extractImportErrors(payload);
 const grouped=payload?.errors_by_sheet||payload?.sheet_errors;
 if(!grouped||typeof grouped!=='object'||Array.isArray(grouped))return existing;
 const result=[...existing];
 for(const [sheet,rows] of Object.entries(grouped)){
  if(!rows||typeof rows!=='object')continue;
  for(const [row,fields] of Object.entries(rows)){
   if(fields&&typeof fields==='object'&&!Array.isArray(fields)){
    for(const [field,messages] of Object.entries(fields))result.push({sheet,row,field,message:messageOf(messages)});
   }else result.push({sheet,row,field:'—',message:messageOf(fields)});
  }
 }
 return result;
}
