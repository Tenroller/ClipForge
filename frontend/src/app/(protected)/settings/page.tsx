'use client';

import { useEffect, useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { useTheme } from '@/components/theme-provider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { User, Palette, Wifi, SlidersHorizontal, LogOut, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { API_BASE, api } from '@/lib/api';
import { useLanguage } from '@/components/providers/LanguageProvider';
import { locales, localeNames } from '@/i18n/config';
import { logoutAction } from '@/app/login/actions';

export default function SettingsPage() {
  const t = useTranslations('settings');
  const { theme, setTheme } = useTheme();
  const { locale, changeLanguage } = useLanguage();

  // API status state
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [apiLatency, setApiLatency] = useState<number | null>(null);

  const checkApiStatus = useCallback(async () => {
    setApiStatus('checking');
    const start = performance.now();
    try {
      const res = await api.get('/health');
      const latency = Math.round(performance.now() - start);
      if (res.ok) {
        setApiStatus('connected');
        setApiLatency(latency);
      } else {
        setApiStatus('disconnected');
      }
    } catch {
      setApiStatus('disconnected');
      setApiLatency(null);
    }
  }, []);

  useEffect(() => {
    checkApiStatus(); // eslint-disable-line react-hooks/set-state-in-effect -- initial data fetch
  }, [checkApiStatus]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      <div className="space-y-1 mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <SlidersHorizontal className="h-8 w-8 text-muted-foreground" />
          {t('title')}
        </h1>
        <p className="text-muted-foreground text-lg">{t('description')}</p>
      </div>

      <Tabs defaultValue="appearance" className="w-full">
        <TabsList className="grid w-full grid-cols-4 max-w-lg h-auto">
          <TabsTrigger value="account" className="gap-1.5 min-h-[44px]" aria-label={t('account.title')}>
            <User className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            <span className="hidden sm:inline">{t('account.title')}</span>
          </TabsTrigger>
          <TabsTrigger value="appearance" className="gap-1.5 min-h-[44px]" aria-label={t('appearance.title')}>
            <Palette className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            <span className="hidden sm:inline">{t('appearance.title')}</span>
          </TabsTrigger>
          <TabsTrigger value="defaults" className="gap-1.5 min-h-[44px]" aria-label={t('defaults.title')}>
            <SlidersHorizontal className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            <span className="hidden sm:inline">{t('defaults.title')}</span>
          </TabsTrigger>
          <TabsTrigger value="api" className="gap-1.5 min-h-[44px]" aria-label={t('api.title')}>
            <Wifi className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            <span className="hidden sm:inline">{t('api.title')}</span>
          </TabsTrigger>
        </TabsList>

        {/* Account Tab */}
        <TabsContent value="account" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('account.title')}</CardTitle>
              <CardDescription>{t('account.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-1">
                <Label className="text-muted-foreground text-xs">{t('account.username')}</Label>
                <p className="text-sm font-medium">admin</p>
              </div>
              <div className="grid gap-1">
                <Label className="text-muted-foreground text-xs">{t('account.role')}</Label>
                <Badge variant="secondary" className="w-fit">admin</Badge>
              </div>
              <Separator />
              <form action={logoutAction}>
                <Button variant="destructive" size="sm" type="submit">
                  <LogOut className="h-3.5 w-3.5 mr-1.5" />
                  {t('account.logout')}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Appearance Tab */}
        <TabsContent value="appearance" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('appearance.title')}</CardTitle>
              <CardDescription>{t('appearance.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <Label>{t('appearance.theme')}</Label>
                  <p className="text-xs text-muted-foreground">{t('appearance.themeDescription')}</p>
                </div>
                <Select value={theme} onValueChange={setTheme}>
                  <SelectTrigger className="w-full sm:w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">{t('appearance.light')}</SelectItem>
                    <SelectItem value="dark">{t('appearance.dark')}</SelectItem>
                    <SelectItem value="system">{t('appearance.system')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Separator />
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <Label>{t('appearance.language')}</Label>
                  <p className="text-xs text-muted-foreground">{t('appearance.languageDescription')}</p>
                </div>
                <Select value={locale} onValueChange={changeLanguage}>
                  <SelectTrigger className="w-full sm:w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {locales.map((loc) => (
                      <SelectItem key={loc} value={loc}>
                        {localeNames[loc]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Defaults Tab */}
        <TabsContent value="defaults" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('defaults.title')}</CardTitle>
              <CardDescription>{t('defaults.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <Label>{t('defaults.aiModel')}</Label>
                  <p className="text-xs text-muted-foreground">{t('defaults.aiModelDescription')}</p>
                </div>
                <Select defaultValue="gemini-2.0-flash">
                  <SelectTrigger className="w-full sm:w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gemini-2.0-flash">Gemini 2.0 Flash</SelectItem>
                    <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                    <SelectItem value="gemini-2.5-pro">Gemini 2.5 Pro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Separator />
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <Label>{t('defaults.subtitlePosition')}</Label>
                  <p className="text-xs text-muted-foreground">{t('defaults.subtitlePositionDescription')}</p>
                </div>
                <Select defaultValue="center">
                  <SelectTrigger className="w-full sm:w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="top">Top</SelectItem>
                    <SelectItem value="center">Center</SelectItem>
                    <SelectItem value="bottom">Bottom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* API Status Tab */}
        <TabsContent value="api" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('api.title')}</CardTitle>
              <CardDescription>{t('api.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-muted-foreground text-xs">{t('api.backendUrl')}</Label>
                <code className="text-xs bg-muted px-2 py-1 rounded">{API_BASE}</code>
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-muted-foreground text-xs">{t('api.status')}</Label>
                {apiStatus === 'checking' && (
                  <Badge variant="outline" className="gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {t('api.checking')}
                  </Badge>
                )}
                {apiStatus === 'connected' && (
                  <Badge variant="default" className="gap-1 bg-success">
                    <CheckCircle2 className="h-3 w-3" />
                    {t('api.connected')}
                  </Badge>
                )}
                {apiStatus === 'disconnected' && (
                  <Badge variant="destructive" className="gap-1">
                    <XCircle className="h-3 w-3" />
                    {t('api.disconnected')}
                  </Badge>
                )}
              </div>
              {apiLatency !== null && (
                <div className="flex items-center justify-between">
                  <Label className="text-muted-foreground text-xs">{t('api.latency')}</Label>
                  <span className="text-sm font-mono">{apiLatency}ms</span>
                </div>
              )}
              <Separator />
              <Button variant="outline" size="sm" onClick={checkApiStatus}>
                {t('api.status')}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
