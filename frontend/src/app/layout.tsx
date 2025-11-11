import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { Toaster } from '@/components/ui/toaster';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'VideoHelper - AI Video Generation Platform',
  description:
    'Enterprise-grade AI video generation platform with MoneyPrinter (AI script + stock footage) and Brainrot (YouTube compilations) workflows.',
  keywords: [
    'video generation',
    'ai videos',
    'moneyprinter',
    'brainrot',
    'youtube automation',
    'video editing',
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <QueryProvider>
          {children}
          <Toaster />
        </QueryProvider>
      </body>
    </html>
  );
}
