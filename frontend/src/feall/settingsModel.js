export const ROLE_NAME={VIEWER:'Viewer',EDITOR:'Editor',DEPARTMENT_ADMIN:'Department Administrator',SYSTEM_ADMIN:'System Administrator'};
export const ROLE_ABOUT={
 VIEWER:'You can view and search metadata in your Departments.',
 EDITOR:'You can create, update, deactivate and import metadata in your Departments.',
 DEPARTMENT_ADMIN:'You manage users and API keys in your Departments, in addition to editing metadata.',
 SYSTEM_ADMIN:'You have full access across all Departments, Organisations, users and shared lists.',
};
export const DEFAULT_DEPARTMENT_KEY='sensor.defaultDepartment';
export const readDefaultDepartment=()=>{try{return localStorage.getItem(DEFAULT_DEPARTMENT_KEY)||''}catch{return ''}};
