import {useRef,useState} from 'react';
import {messageOf,groupedImportErrors} from './excelErrors';
import {csrfToken,createImportRequest,importSucceeded} from './excelImport';

export default function ExcelPage({department,canWrite=true,onImported=()=>{}}){
 const [file,setFile]=useState(null),[typedDepartment,setDepartmentId]=useState(''),[state,setState]=useState('idle');
 const [error,setError]=useState(''),[report,setReport]=useState(null);
 const fileInput=useRef(null);
 const departmentId=department??typedDepartment;
 // Confirmed metadata import contract: POST /api/v1/imports/excel/.
 const endpoint=import.meta.env.VITE_EXCEL_IMPORT_URL||`${(import.meta.env.VITE_API_BASE_URL||'/api/v1').replace(/\/+$/,'')}/imports/excel/`;
 const configured=true;
 const choose=e=>{
  const selected=e.target.files?.[0]||null;
  setFile(selected);setError(selected&&!/\.xlsx$/i.test(selected.name)?'Choose an .xlsx Excel workbook.':'');
  setReport(null);setState('idle');
 };
 async function upload(){
  if(!configured||!canWrite)return;
  if(!file||!/\.xlsx$/i.test(file.name)){setError('Choose an .xlsx Excel workbook.');return;}
  if(!/^\d+$/.test(departmentId)||Number(departmentId)<=0){setError('Enter a valid Department ID.');return;}
  setState('loading');setError('');setReport(null);
  try{
   const response=await fetch(endpoint,createImportRequest(file,departmentId,csrfToken()));
   const payload=await response.json().catch(()=>null);
   setReport(payload);
   const validation=groupedImportErrors(payload);
   if(!importSucceeded(response,payload)){
    setState('error');
    setError(messageOf(payload?.message||payload?.detail)||`Import not confirmed (HTTP ${response.status}).${validation.length?' Review validation errors below.':''}`);
   }else {setState('success');onImported();}
  }catch{
   setState('error');setError('Cannot connect to the import service. Please try again.');
  }
 }
 const rowErrors=groupedImportErrors(report);
 return <section className="fe-panel">
  <div className="fe-panel-head"><div><h2>Excel Import</h2></div></div>
  <div className="all-pad">
   {!configured&&<p role="status">Excel import is temporarily unavailable until the backend import API is connected.</p>}
   {!canWrite&&<p role="status">Import requires write permission for the selected Department.</p>}
   <label>Department ID <input readOnly={department!==undefined} type="number" min="1" step="1" value={departmentId} onChange={e=>setDepartmentId(e.target.value)} disabled={!configured||!canWrite||state==='loading'}/></label>
   <label className="all-upload">Select Excel workbook (.xlsx)
    <input ref={fileInput} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={choose} disabled={!configured||!canWrite||state==='loading'}/>
   </label>
   <p>{file?file.name:'No file selected'}</p>
   <button type="button" className="all-primary" disabled={!configured||!canWrite||state==='loading'||!file||!/\.xlsx$/i.test(file.name)||!/^\d+$/.test(departmentId)||Number(departmentId)<=0} onClick={upload}>
    {state==='loading'?'Uploading…':state==='error'?'Retry import':'Import workbook'}
   </button>
   {state==='loading'&&<p role="status">Uploading and validating workbook…</p>}
   {error&&<p role="alert" style={{color:'#b42318'}}>{error}</p>}
   {state==='success'&&<p role="status">{report?.created ? `Workbook imported successfully: ${Object.entries(report.created).map(([sheet,count])=>`${sheet}: ${count}`).join(', ')}` : messageOf(report?.message)||'Workbook imported successfully.'}</p>}
   {rowErrors.length>0&&<div><h3>Validation errors</h3><table><thead><tr><th>Sheet</th><th>Row</th><th>Field</th><th>Message</th></tr></thead><tbody>
    {rowErrors.map((r,i)=><tr key={i}><td>{r.sheet}</td><td>{r.row}</td><td>{r.field}</td><td>{r.message}</td></tr>)}
   </tbody></table></div>}
  </div>
 </section>;
}
