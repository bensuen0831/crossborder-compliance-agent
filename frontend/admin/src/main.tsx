import { createRoot } from 'react-dom/client';
import { AdminFeature } from './AdminFeature';
import type { AdminHost } from './contracts';

declare global { interface Window { crossborderAdminHost?: AdminHost; } }
const root = document.getElementById('admin-root');
if (root) createRoot(root).render(<AdminFeature host={window.crossborderAdminHost ?? { session: null }}/>);
