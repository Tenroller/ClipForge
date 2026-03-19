'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { Locale, locales } from '@/i18n/config';

type LanguageContextType = {
  locale: Locale;
  changeLanguage: (newLocale: Locale) => void;
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale: Locale;
}) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const router = useRouter();

  // Load locale from localStorage on mount (client-side only)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedLocale = localStorage.getItem('videohelper-ui-language');
      if (savedLocale && locales.includes(savedLocale as Locale)) {
        setLocale(savedLocale as Locale); // eslint-disable-line react-hooks/set-state-in-effect -- hydration from localStorage
      }
    }
  }, []);

  const changeLanguage = async (newLocale: Locale) => {
    if (!locales.includes(newLocale)) {
      console.error(`Invalid locale: ${newLocale}`);
      return;
    }

    // Update state
    setLocale(newLocale);

    // Persist to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('videohelper-ui-language', newLocale);
    }

    // Set cookie for server-side rendering
    document.cookie = `videohelper-ui-language=${newLocale}; path=/; max-age=31536000; SameSite=Lax`;

    // Refresh the page to apply new locale
    router.refresh();
  };

  return (
    <LanguageContext.Provider value={{ locale, changeLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
