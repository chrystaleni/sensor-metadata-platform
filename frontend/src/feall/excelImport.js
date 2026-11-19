import {extractImportErrors} from './excelErrors';
export function csrfToken(cookie = typeof document==='undefined'?'':document.cookie){
 const entry=cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('csrftoken='));
 try{return entry?decodeURIComponent(entry.slice('csrftoken='.length)):'';}catch{return '';}
}
export function createImportRequest(file,departmentId,token){
 const body=new FormData();body.append('file',file);body.append('department',String(departmentId));
 const headers={};if(token)headers['X-CSRFToken']=token;
 return {method:'POST',body,headers,credentials:'include'};
}
export function importSucceeded(response,payload){
 if(!response.ok||!payload||typeof payload!=='object'||Array.isArray(payload)||extractImportErrors(payload).length)return false;
 if(payload.success===false||payload.status==='error'||payload.status==='failed')return false;
 return response.status===201&&payload.created&&typeof payload.created==='object'&&!Array.isArray(payload.created)&&Object.values(payload.created).every(v=>Number.isInteger(v)&&v>=0);
}
