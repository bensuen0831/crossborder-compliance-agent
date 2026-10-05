import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import 'antd/dist/reset.css';
import './i18n';
import './styles.css';
import App from './App';

const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><BrowserRouter><QueryClientProvider client={client}><App /></QueryClientProvider></BrowserRouter></React.StrictMode>,
);
