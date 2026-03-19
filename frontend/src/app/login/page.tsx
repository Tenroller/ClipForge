'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { loginAction } from './actions';
import { useTranslations } from 'next-intl';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();
  const t = useTranslations('login');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!username || !password) {
      toast({
        title: t('errors.required'),
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);

    try {
      const result = await loginAction(username, password);

      if (result.success) {
        toast({
          title: t('success.loggedIn'),
        });
        router.push('/creator');
        router.refresh();
      } else {
        toast({
          title: t('errors.invalidCredentials'),
          description: result.error || t('errors.invalidCredentials'),
          variant: 'destructive',
        });
      }
    } catch {
      toast({
        title: t('errors.unexpectedError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-card rounded-lg border p-10">
          {/* Logo and Title */}
          <div className="flex flex-col items-center mb-8">
            <div className="size-20 rounded-lg bg-muted flex items-center justify-center mb-4 overflow-hidden">
              <img
                src="/logo.png"
                alt="ClipForge"
                className="size-16 object-contain"
              />
            </div>
            <h1 className="text-3xl font-bold">
              {t('title')}
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              {t('subtitle')}
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium">
                {t('username')}
              </Label>
              <Input
                id="username"
                type="text"
                placeholder={t('usernamePlaceholder')}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-10"
                disabled={isLoading}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">
                {t('password')}
              </Label>
              <Input
                id="password"
                type="password"
                placeholder={t('passwordPlaceholder')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10"
                disabled={isLoading}
              />
            </div>

            <Button
              type="submit"
              className="w-full h-10 text-base font-medium"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin mr-2" />
                  {t('signingIn')}
                </>
              ) : (
                t('signIn')
              )}
            </Button>
          </form>

        </div>
      </div>
    </div>
  );
}
