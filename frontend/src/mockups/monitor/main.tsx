import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import i18next from 'i18next';
import { I18nextProvider, initReactI18next } from 'react-i18next';
import { MonitorMockup } from './MonitorMockup';
import { resources } from './locales';
import '../../index.css';
import './monitor.css';

// An isolated i18n instance and entry point keep the preview out of app sessions.
const i18n = i18next.createInstance();
void i18n.use(initReactI18next).init({
  resources,
  lng: new URLSearchParams(location.search).get('lang') === 'en' ? 'en' : 'uk',
  fallbackLng: 'uk', interpolation: { escapeValue: false },
}).then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode><I18nextProvider i18n={i18n}><MonitorMockup /></I18nextProvider></StrictMode>,
  );
});
