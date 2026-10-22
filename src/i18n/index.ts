// i18n (HR15): every visible text comes from a locale file. Spanish is the
// only language populated (RNF-05); a missing key is shown as its key in
// development, which the checks catch (scripts/test-i18n-keys.mjs).
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import es from './locales/es.json';

export const DEFAULT_LANGUAGE = 'es';

void i18n.use(initReactI18next).init({
  resources: { es: { translation: es } },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
