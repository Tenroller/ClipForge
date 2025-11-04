import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function HomePage() {
  return (
    <div className="container-page flex min-h-screen flex-col items-center justify-center">
      <div className="mx-auto max-w-3xl text-center space-y-8">
        {/* Hero Section */}
        <div className="space-y-4">
          <h1 className="text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
            <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400 bg-clip-text text-transparent">
              VideoHelper
            </span>
          </h1>
          <p className="text-xl text-muted-foreground sm:text-2xl">
            Enterprise-Grade AI Video Generation Platform
          </p>
        </div>

        {/* Description */}
        <div className="mx-auto max-w-2xl space-y-4 text-lg text-muted-foreground">
          <p>
            Dual workflows for automated video creation:
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border bg-card/40 p-6 text-left backdrop-blur">
              <h3 className="font-semibold text-foreground mb-2">MoneyPrinter</h3>
              <p className="text-sm">
                AI script generation + stock footage from Pexels with professional TTS
              </p>
            </div>
            <div className="rounded-lg border bg-card/40 p-6 text-left backdrop-blur">
              <h3 className="font-semibold text-foreground mb-2">Brainrot</h3>
              <p className="text-sm">
                YouTube compilation videos with scene detection and smart editing
              </p>
            </div>
          </div>
        </div>

        {/* CTA Buttons */}
        <div className="flex flex-col gap-4 sm:flex-row sm:justify-center">
          <Button asChild size="lg" className="btn-primary">
            <Link href="/login">
              Get Started
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/login">
              Sign In
            </Link>
          </Button>
        </div>

        {/* Features */}
        <div className="pt-8">
          <div className="flex flex-wrap justify-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="text-primary">✓</span>
              <span>Cloud GPU Acceleration</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-primary">✓</span>
              <span>Real-time Job Monitoring</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-primary">✓</span>
              <span>Resume Failed Jobs</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
