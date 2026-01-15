import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { Toaster } from '@/components/ui/toaster';
import { ThemeProvider } from '@/components/theme-provider';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, getLocale } from 'next-intl/server';
import { LanguageProvider } from '@/components/providers/LanguageProvider';
import type { Locale } from '@/i18n/config';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'ClipForge - AI Video Generation Platform',
  description:
    'Enterprise-grade AI video generation platform with MoneyPrinter (AI script + stock footage) and Brainrot (YouTube compilations) workflows.',
  keywords: [
    'video generation',
    'ai videos',
    'moneyprinter',
    'brainrot',
    'youtube automation',
    'video editing',
    'clipforge',
  ],
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = (await getLocale()) as Locale;
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        <NextIntlClientProvider messages={messages} locale={locale}>
          <LanguageProvider initialLocale={locale}>
            <ThemeProvider defaultTheme="system" storageKey="clipforge-ui-theme">
              <QueryProvider>
                {children}
                <Toaster />
              </QueryProvider>
            </ThemeProvider>
          </LanguageProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
