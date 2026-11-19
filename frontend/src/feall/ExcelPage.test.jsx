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
it('does not refresh on failed validation and disables imports for viewers',async()=>{
 vi.stubGlobal('fetch',vi.fn());render(<ExcelPage department="7" canWrite={false}/>);
 expect(screen.getByText('Import workbook')).toBeDisabled();expect(screen.getByLabelText(/Select Excel workbook/)).toBeDisabled();
});
