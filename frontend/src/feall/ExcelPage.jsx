import {useRef,useState} from 'react';

import {messageOf,extractImportErrors} from './excelErrors';

export default function ExcelPage(){
  const [file,setFile]=useState(null),[state,setState]=useState('idle');
  const [error,setError]=useState(''),[report,setReport]=useState(null);
  const fileInput=useRef(null);
  const endpoint=import.meta.env.VITE_EXCEL_IMPORT_URL;
  const configured=Boolean(endpoint);
  const choose=e=>{
    const selected=e.target.files?.[0]||null;
    setFile(selected);setError(selected&&!/\.xlsx$/i.test(selected.name)?'Choose an .xlsx Excel workbook.':'');
    setReport(null);setState('idle');
  };
  async function upload(){
    if(!configured)return;
    if(!file||!/\.xlsx$/i.test(file.name)){setError('Choose an .xlsx Excel workbook.');return;}
    setState('loading');setError('');setReport(null);
    try{
      const body=new FormData();body.append('file',file);
      const response=await fetch(endpoint,{method:'POST',body,credentials:'include'});
      const payload=await response.json().catch(()=>({}));
      setReport(payload);
      const validation=extractImportErrors(payload);
      if(!response.ok||validation.length){
        setState('error');
        setError(messageOf(payload.message||payload.detail)||`Import failed (HTTP ${response.status}). ${validation.length?'Review validation errors below.':''}`);
      }else setState('success');
    }catch{
      setState('error');setError('Cannot connect to the import service. Please try again.');
    }
  }
  const rowErrors=extractImportErrors(report);
  return <section className="fe-panel">
    <div className="fe-panel-head"><div><h2>Excel Import</h2></div></div>
    <div className="all-pad">
      {!configured&&<p role="status">Excel import is temporarily unavailable until the backend import API is connected.</p>}
      <label className="all-upload">Select Excel workbook (.xlsx)
        <input ref={fileInput} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={choose} disabled={!configured||state==='loading'}/>
      </label>
      <p>{file?file.name:'No file selected'}</p>
      <button type="button" className="all-primary" disabled={!configured||state==='loading'||!file||!/\.xlsx$/i.test(file.name)} onClick={upload}>
        {state==='loading'?'Uploading…':state==='error'?'Retry import':'Import workbook'}
      </button>
      {state==='loading'&&<p role="status">Uploading and validating workbook…</p>}
      {error&&<p role="alert" style={{color:'#b42318'}}>{error}</p>}
      {state==='success'&&<p role="status">{messageOf(report?.message)||'Workbook imported successfully.'}</p>}
      {rowErrors.length>0&&<div><h3>Validation errors</h3><table><thead><tr><th>Sheet</th><th>Row</th><th>Field</th><th>Message</th></tr></thead><tbody>
        {rowErrors.map((r,i)=><tr key={i}><td>{r.sheet}</td><td>{r.row}</td><td>{r.field}</td><td>{r.message}</td></tr>)}
      </tbody></table></div>}
    </div>
  </section>;
}
