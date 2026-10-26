import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App as AntApp } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Router } from './app/Router';
import { ApiError } from './shared/api/http';
import './styles/app.css';
import { userMessage } from './shared/lib/userMessage';
const query = new QueryClient({
  defaultOptions: {
    queries: {
      networkMode: 'always',
      retry: (count, error) =>
        !(
          error instanceof ApiError &&
          [401, 403, 404, 409, 412, 422, 429, 503].includes(error.status)
        ) && count < 1,
      staleTime: 15000,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false, networkMode: 'always' },
  },
});
async function start() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <ConfigProvider
        locale={ruRU}
        theme={{
          token: {
            colorPrimary: '#d82e28',
            colorInfo: '#496c9f',
            colorSuccess: '#378264',
            borderRadius: 10,
            fontFamily: '"Segoe UI", Arial, sans-serif',
            fontSize: 14,
            controlHeight: 42,
          },
          components: { Button: { primaryShadow: 'none' }, Checkbox: { colorPrimary: '#d82e28' } },
        }}
      >
        <AntApp>
          <QueryClientProvider client={query}>
            <Router />
          </QueryClientProvider>
        </AntApp>
      </ConfigProvider>
    </React.StrictMode>,
  );
}
void start().catch((error) => {
  const root = document.getElementById('root')!;
  root.textContent = userMessage(error instanceof Error ? error.message : undefined,'Не удалось открыть кабинет. Обновите страницу или попробуйте позже.');
  root.setAttribute('role', 'alert');
});
