'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useLanguage } from '@/components/providers/LanguageProvider';
import { locales, localeNames, localeFlags, Locale } from '@/i18n/config';
import { Languages } from 'lucide-react';

export function LanguageSwitcher() {
  const { locale, changeLanguage } = useLanguage();
  const t = useTranslations('sidebar.footer');
  const tCommon = useTranslations('common');
  const [mounted, setMounted] = useState(false);

  // Prevent hydration mismatch by only rendering after mount
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    // Return a placeholder with matching dimensions to prevent layout shift
    return (
      <div className="flex items-center justify-between px-2">
        <span className="text-xs font-medium text-muted-foreground">{t('language')}</span>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-2 px-3 text-xs"
          disabled
        >
          <Languages className="size-3.5" />
          <span>🌐</span>
          <span>{tCommon('loading')}</span>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between px-2">
      <span className="text-xs font-medium text-muted-foreground">{t('language')}</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-2 px-3 text-xs hover:bg-primary/10 hover:text-primary hover:border-primary/50 transition-all"
          >
            <Languages className="size-3.5" />
            <span>{localeFlags[locale]}</span>
            <span>{localeNames[locale]}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          {locales.map((loc) => (
            <DropdownMenuItem
              key={loc}
              onClick={() => changeLanguage(loc)}
              className={`flex items-center gap-3 cursor-pointer ${locale === loc ? 'bg-primary/10 text-primary font-semibold' : ''
                }`}
            >
              <span className="text-lg">{localeFlags[loc]}</span>
              <span className="flex-1">{localeNames[loc]}</span>
              {locale === loc && (
                <svg
                  className="size-4 text-primary"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
