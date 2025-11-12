import { getRequestConfig } from 'next-intl/server';
import { cookies } from 'next/headers';
import { defaultLocale, locales } from './config';

export default getRequestConfig(async () => {
  // Get locale from cookie
  const cookieStore = await cookies();
  const localeCookie = cookieStore.get('videohelper-ui-language');

  let locale = localeCookie?.value || defaultLocale;

  // Validate locale
  if (!locales.includes(locale as any)) {
    locale = defaultLocale;
  }

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
