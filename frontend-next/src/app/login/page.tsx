'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { FaFilm, FaLock, FaUser } from 'react-icons/fa';
import { useToast } from '@/hooks/use-toast';
import { loginAction } from './actions';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!username || !password) {
      toast({
        title: 'Error',
        description: 'Please enter both username and password',
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);

    try {
      const result = await loginAction(username, password);

      if (result.success) {
        toast({
          title: 'Success',
          description: 'Logged in successfully',
        });
        router.push('/creator');
        router.refresh(); // Refresh to update auth state
      } else {
        toast({
          title: 'Login Failed',
          description: result.error || 'Invalid credentials',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'An unexpected error occurred',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden p-4">
      {/* Animated Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-50/80 via-purple-50/80 to-emerald-50/80 dark:from-blue-950/20 dark:via-purple-950/20 dark:to-emerald-950/20" />
      <div className="absolute inset-0 bg-grid-pattern opacity-5" />

      {/* Floating Orbs */}
      <div className="absolute top-20 left-20 size-32 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-20 right-20 size-40 bg-purple-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 size-48 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />

      <div className="w-full max-w-md relative z-10 fade-in">
        <div className="bg-card/80 backdrop-blur-2xl rounded-3xl shadow-2xl p-10 border-2 border-border/50 hover:border-border/80 transition-all">
          {/* Logo and Title */}
          <div className="flex flex-col items-center mb-8">
            <div className="size-20 rounded-3xl bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center shadow-2xl mb-4 hover:scale-110 transition-transform">
              <FaFilm className="size-10 text-white" />
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 bg-clip-text text-transparent">
              VideoHelper
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              AI Video Generation Platform
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-3">
              <Label htmlFor="username" className="text-sm font-semibold">
                Username
              </Label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none group-focus-within:text-primary transition-colors">
                  <FaUser className="h-5 w-5 text-muted-foreground" />
                </div>
                <Input
                  id="username"
                  type="text"
                  placeholder="Enter your username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-12 h-12 border-2 focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                  disabled={isLoading}
                  autoFocus
                />
              </div>
            </div>

            <div className="space-y-3">
              <Label htmlFor="password" className="text-sm font-semibold">
                Password
              </Label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none group-focus-within:text-primary transition-colors">
                  <FaLock className="h-5 w-5 text-muted-foreground" />
                </div>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-12 h-12 border-2 focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                  disabled={isLoading}
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full h-12 text-base font-semibold btn-primary shadow-xl"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="size-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign In
                  <span className="ml-2">→</span>
                </>
              )}
            </Button>
          </form>

          {/* Info Footer */}
          <div className="mt-8 pt-6 border-t-2 border-border/50">
            <div className="bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-emerald-500/10 rounded-xl p-4 border border-primary/20">
              <p className="text-xs text-center text-muted-foreground font-medium mb-2">
                Default Credentials
              </p>
              <p className="text-sm text-center font-mono bg-card/50 rounded-lg p-2 border">
                admin / admin123
              </p>
              <p className="text-xs text-center text-muted-foreground mt-3 leading-relaxed">
                Change via <code className="text-primary">AUTH_USERNAME</code> and{' '}
                <code className="text-primary">AUTH_PASSWORD</code> environment variables
              </p>
            </div>
          </div>

          {/* Additional Info */}
          <div className="mt-6 text-center">
            <p className="text-xs text-muted-foreground">
              By signing in, you agree to our Terms of Service
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
