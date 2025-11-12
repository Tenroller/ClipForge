export const locales = ['en', 'pt-BR'] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = 'en';

export const localeNames: Record<Locale, string> = {
  en: 'English',
  'pt-BR': 'Português',
};

export const localeFlags: Record<Locale, string> = {
  en: '🇺🇸',
  'pt-BR': '🇧🇷',
};
