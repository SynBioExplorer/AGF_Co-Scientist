import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import './v2/styles/globals.css';
import App from './v2/App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
