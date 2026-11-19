export const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '▦' },
  { id: 'measurements', label: 'Measurements', icon: '⌁' },
  { id: 'physical-devices', label: 'Physical Devices', icon: '▣' },
  { id: 'network-elements', label: 'Network Elements', icon: '⌖' },
  { id: 'gis-map', label: 'GIS Map', icon: '◎' },
  { id: 'controlled-lists', label: 'Controlled Lists', icon: '☷' },
  { id: 'excel-import-export', label: 'Excel Import/Export', icon: '⇅' },
  { id: 'api-keys', label: 'API Keys', icon: '⚿' },
  { id: 'administration', label: 'Administration', icon: '♙' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]
export const DEFAULT_PAGE = 'dashboard'
export function pageFromHash(hash) {
  const id = hash.replace(/^#\/?/, '')
  return NAV_ITEMS.some(item => item.id === id) ? id : DEFAULT_PAGE
}
