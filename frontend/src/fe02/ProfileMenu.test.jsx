import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {AppLayout} from './AppLayout';
afterEach(cleanup);
it('opens a profile window with the user, role and Log out, and closes on Escape',()=>{
 const onLogout=vi.fn();
 render(<AppLayout profile={{username:'admin',role:'SYSTEM_ADMIN',onLogout}}>{()=>null}</AppLayout>);
 expect(screen.queryByRole('dialog',{name:'Your profile'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Profile menu'}));
 expect(screen.getByRole('dialog',{name:'Your profile'})).toHaveTextContent('admin');
 expect(screen.getByRole('dialog',{name:'Your profile'})).toHaveTextContent('System Administrator');
 fireEvent.keyDown(document,{key:'Escape'});
 expect(screen.queryByRole('dialog',{name:'Your profile'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Profile menu'}));
 fireEvent.click(screen.getByRole('button',{name:'Log out'}));
 expect(onLogout).toHaveBeenCalledTimes(1);
});

it('lets the user see and switch the Department from the profile window',()=>{
 const onDepartment=vi.fn();
 render(<AppLayout profile={{username:'admin',role:'EDITOR',onLogout:()=>{},departments:[{id:2,name:'North',organisation:'Water'},{id:3,name:'South',organisation:'Water'}],department:'2',onDepartment}}>{()=>null}</AppLayout>);
 fireEvent.click(screen.getByRole('button',{name:'Profile menu'}));
 const select=screen.getByLabelText('Switch department');
 expect(select.value).toBe('2');
 fireEvent.change(select,{target:{value:'3'}});
 expect(onDepartment).toHaveBeenCalledWith('3');
});
