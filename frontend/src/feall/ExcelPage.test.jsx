import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import ExcelPage from './ExcelPage';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('imports into the selected membership and signals a dashboard/map refresh',async()=>{
 const onImported=vi.fn();const fetch=vi.fn(async()=>({ok:true,status:201,json:async()=>({created:{measurements:1}})}));vi.stubGlobal('fetch',fetch);
 render(<ExcelPage department="7" onImported={onImported}/>);
 fireEvent.change(screen.getByLabelText(/Select Excel workbook/),{target:{files:[new File(['test'], 'data.xlsx')]}});
 fireEvent.click(screen.getByText('Import workbook'));
 await screen.findByText(/Workbook imported successfully/);
 expect(fetch.mock.calls[0][1].body.get('department')).toBe('7');expect(onImported).toHaveBeenCalledTimes(1);
});
it('disables imports for viewers',async()=>{
 vi.stubGlobal('fetch',vi.fn());render(<ExcelPage department="7" canWrite={false}/>);
 expect(screen.getByText('Import workbook')).toBeDisabled();expect(screen.getByLabelText(/Select Excel workbook/)).toBeDisabled();
});


it('retains row-level validation errors and does not refresh on failure',async()=>{
 const onImported=vi.fn();vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:400,json:async()=>({errors:[{sheet:'Measurements',row:2,errors:{name:['Required.']}}]})})));
 render(<ExcelPage department="7" onImported={onImported}/>);
 fireEvent.change(screen.getByLabelText(/Select Excel workbook/),{target:{files:[new File(['test'],'bad.xlsx')]}});
 fireEvent.click(screen.getByText('Import workbook'));
 await screen.findByText('Required.');expect(onImported).not.toHaveBeenCalled();
});

it('names the Department the workbook will be imported into',()=>{
 vi.stubGlobal('fetch',vi.fn());render(<ExcelPage department="2" departmentName="Nicosia"/>);
 expect(screen.getByRole('note')).toHaveTextContent('Records will be imported into Nicosia (Department ID 2)');
});
