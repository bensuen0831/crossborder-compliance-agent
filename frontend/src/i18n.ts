import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zhCN from './locales/zh-CN.json';
import zhHK from './locales/zh-HK.json';
import enUS from './locales/en-US.json';

export const supportedLocales = ['zh-CN', 'zh-HK', 'en-US'] as const;
export type Locale = typeof supportedLocales[number];
const preferenceKey = 'stage1-alpha.ui-locale';
function preference(): Locale {
  try {
    const stored = localStorage.getItem(preferenceKey);
    return supportedLocales.find(locale => locale === stored) ?? 'zh-HK';
  } catch { return 'zh-HK'; }
}
export function currentLocale(): Locale {
  return supportedLocales.find(locale => locale === i18n.resolvedLanguage) ?? 'en-US';
}
void i18n.use(initReactI18next).init({
  resources: { 'zh-CN': { translation: zhCN }, 'zh-HK': { translation: zhHK }, 'en-US': { translation: enUS } },
  lng: preference(), supportedLngs: [...supportedLocales], load: 'currentOnly', fallbackLng: 'en-US',
  keySeparator: false, showSupportNotice: false, interpolation: { escapeValue: false },
  parseMissingKeyHandler: key => {
    console.error('I18N_MISSING_KEY', key);
    return { 'zh-CN': zhCN, 'zh-HK': zhHK, 'en-US': enUS }[currentLocale()]['ui.translationUnavailable'];
  },
});
i18n.on('languageChanged', language => {
  if (!supportedLocales.some(locale => locale === language)) return;
  try { localStorage.setItem(preferenceKey, language); } catch { /* Preference is optional. */ }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = language;
    document.title = `${i18n.t('knowledge')} | ${i18n.t('ui.brand')}`;
  }
});
if (typeof document !== 'undefined') {
  document.documentElement.lang = currentLocale();
  document.title = `${i18n.t('knowledge')} | ${i18n.t('ui.brand')}`;
}
export default i18n;
