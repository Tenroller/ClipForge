import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Animated background gradients */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50/80 via-purple-50/80 to-emerald-50/80" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="mx-auto max-w-6xl pt-20 pb-24 sm:pt-28 sm:pb-32">
            <div className="text-center space-y-8">
              {/* Badge */}
              <div className="flex justify-center">
                <Badge className="px-4 py-2 text-sm bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-emerald-500/10 border-primary/20 hover:border-primary/40 transition-all">
                  <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-emerald-600 bg-clip-text text-transparent font-semibold">
                    ⚡ Powered by AI
                  </span>
                </Badge>
              </div>

              {/* Main Heading */}
              <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl lg:text-7xl xl:text-8xl">
                <span className="block mb-2">Create Videos with</span>
                <span className="block bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 bg-clip-text text-transparent">
                  Artificial Intelligence
                </span>
              </h1>

              {/* Subtitle */}
              <p className="mx-auto max-w-2xl text-lg sm:text-xl lg:text-2xl text-muted-foreground leading-relaxed">
                Transform ideas into engaging videos in minutes. Enterprise-grade AI video generation platform with three powerful workflows: AI Video Creator, Compilations, and Podcast Viral Clips.
              </p>

              {/* CTA Buttons */}
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
                <Button asChild size="lg" className="text-base px-8 h-12 shadow-lg">
                  <Link href="/login">
                    Start Creating Free
                    <span className="ml-2">→</span>
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="text-base px-8 h-12 border-2">
                  <Link href="/login">
                    Sign In
                  </Link>
                </Button>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-12 max-w-3xl mx-auto">
                {[
                  { label: 'AI Models', value: '10+' },
                  { label: 'TTS Voices', value: '50+' },
                  { label: 'GPU Powered', value: '100%' },
                  { label: 'Processing Speed', value: '10x' },
                ].map((stat, i) => (
                  <div key={i} className="text-center space-y-1">
                    <div className="text-3xl sm:text-4xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                      {stat.value}
                    </div>
                    <div className="text-xs sm:text-sm text-muted-foreground font-medium">
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Workflows Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28">
        <div className="mx-auto max-w-7xl space-y-12">
          <div className="text-center space-y-4">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
              <span className="bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 bg-clip-text text-transparent">
                Three Powerful Workflows
              </span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Choose the perfect workflow for your content creation needs
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* MoneyPrinter Card */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
              <CardContent className="p-8 space-y-6 relative">
                <div className="size-14 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  <svg className="size-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>

                <div className="space-y-3">
                  <h3 className="text-2xl font-bold">AI Video Creator</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Generate complete videos from a simple topic. AI writes the script, sources stock footage from Pexels, creates professional voiceovers, and adds animated subtitles.
                  </p>
                </div>

                <div className="space-y-2">
                  {[
                    'AI Script Generation with Gemini',
                    'Automated Stock Footage Selection',
                    'Professional Text-to-Speech (50+ voices)',
                    'Word-Level Animated Subtitles',
                    'Background Music Integration',
                  ].map((feature, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <div className="size-5 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0">
                        <svg className="size-3 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>

                <Button asChild className="w-full">
                  <Link href="/login">
                    Try AI Video Creator
                  </Link>
                </Button>
              </CardContent>
            </Card>

            {/* Brainrot/Compilations Card */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
              <CardContent className="p-8 space-y-6 relative">
                <div className="size-14 rounded-2xl bg-gradient-to-br from-purple-500 to-emerald-500 flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  <svg className="size-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                  </svg>
                </div>

                <div className="space-y-3">
                  <h3 className="text-2xl font-bold">Video Compilations</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Create engaging compilation videos from YouTube content or podcasts. Smart scene detection, automated editing, and optional background overlays.
                  </p>
                </div>

                <div className="space-y-2">
                  {[
                    'YouTube Video Download & Processing',
                    'AI-Powered Scene Detection',
                    'Smart Clip Extraction',
                    'Background Video Overlay',
                    'Automated Compilation Assembly',
                  ].map((feature, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <div className="size-5 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
                        <svg className="size-3 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>

                <Button asChild className="w-full" variant="outline">
                  <Link href="/login">
                    Try Compilations
                  </Link>
                </Button>
              </CardContent>
            </Card>

            {/* Podcast Clips Card */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
              <CardContent className="p-8 space-y-6 relative">
                <div className="size-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  <svg className="size-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                </div>

                <div className="space-y-3">
                  <h3 className="text-2xl font-bold">Podcast Viral Clips</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Transform long-form podcasts into viral short clips. AI-powered moment detection, smart face tracking, and karaoke-style subtitles optimized for social media.
                  </p>
                </div>

                <div className="space-y-2">
                  {[
                    'AI Viral Moment Detection with Gemini',
                    'Smart Face Tracking & 9:16 Cropping',
                    'Mixed-Mode Content Detection (Face/Screen)',
                    'Karaoke-Style Word Highlighting',
                    'Parallel Clip Generation (3x Faster)',
                  ].map((feature, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <div className="size-5 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
                        <svg className="size-3 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>

                <Button asChild className="w-full" variant="default">
                  <Link href="/login">
                    Try Podcast Clips
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28 bg-muted/30">
        <div className="mx-auto max-w-6xl space-y-12">
          <div className="text-center space-y-4">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
              Enterprise-Grade Features
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Built for creators, optimized for scale
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: '🚀',
                title: 'Cloud GPU Acceleration',
                description: 'Leverage powerful L40S, A100, and H100 GPUs for lightning-fast video processing',
              },
              {
                icon: '🎯',
                title: 'AI Viral Detection',
                description: 'Gemini-powered analysis identifies the most engaging moments in your podcasts',
              },
              {
                icon: '👤',
                title: 'Smart Face Tracking',
                description: 'MediaPipe face detection with intelligent 9:16 cropping for social media',
              },
              {
                icon: '📊',
                title: 'Real-Time Monitoring',
                description: 'Track job progress with detailed metrics, step-by-step updates, and comprehensive logs',
              },
              {
                icon: '🔄',
                title: 'Job Resume & Retry',
                description: 'Automatically resume failed jobs from the last successful step, never lose progress',
              },
              {
                icon: '🎨',
                title: 'Karaoke Subtitles',
                description: 'Word-by-word highlighting with customizable colors, positions, and animations',
              },
              {
                icon: '🗄️',
                title: 'PostgreSQL Backend',
                description: 'Enterprise-grade persistence with full job history and artifact management',
              },
              {
                icon: '🔊',
                title: '50+ TTS Voices',
                description: 'Professional text-to-speech powered by Kokoro with diverse voice options',
              },
              {
                icon: '🤖',
                title: 'Multiple AI Models',
                description: 'Choose from Gemini Flash, Pro, and other cutting-edge AI models',
              },
              {
                icon: '⚡',
                title: 'Parallel Processing',
                description: 'Generate multiple clips simultaneously with GPU acceleration (3x faster)',
              },
              {
                icon: '🎬',
                title: 'Mixed-Mode Detection',
                description: 'Automatically switches between face-focused and screen recording modes',
              },
              {
                icon: '🌐',
                title: 'REST API',
                description: 'Full-featured API with JWT authentication for integration with your tools',
              },
            ].map((feature, i) => (
              <Card key={i} className="p-6 hover:shadow-lg transition-all">
                <CardContent className="p-0 space-y-3">
                  <div className="text-4xl">{feature.icon}</div>
                  <h3 className="text-lg font-semibold">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {feature.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28">
        <div className="mx-auto max-w-5xl space-y-12">
          <div className="text-center space-y-4">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
              <span className="bg-gradient-to-r from-emerald-500 to-blue-500 bg-clip-text text-transparent">
                How It Works
              </span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              From idea to video in four simple steps
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              {
                step: '01',
                title: 'Choose Workflow',
                description: 'Select AI Creator, Compilations, or Podcast Clips based on your needs',
              },
              {
                step: '02',
                title: 'AI Processing',
                description: 'Our AI generates scripts, finds footage, detects viral moments, and creates voiceovers',
              },
              {
                step: '03',
                title: 'Real-Time Monitoring',
                description: 'Track progress with live updates, detailed metrics, and step-by-step logs',
              },
              {
                step: '04',
                title: 'Download & Share',
                description: 'Get your finished videos ready to upload to any platform',
              },
            ].map((item, i) => (
              <div key={i} className="relative text-center space-y-4 group">
                <div className="mx-auto size-16 rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center text-2xl font-bold text-white shadow-xl group-hover:scale-110 transition-transform">
                  {item.step}
                </div>
                <h3 className="text-lg font-semibold">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
                {i < 3 && (
                  <div className="hidden lg:block absolute top-8 left-[calc(50%+2rem)] w-[calc(100%-4rem)] h-0.5 bg-gradient-to-r from-primary to-accent opacity-20" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28">
        <div className="mx-auto max-w-4xl">
          <Card className="overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-emerald-500/10" />
            <CardContent className="relative p-12 text-center space-y-6">
              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
                Ready to Create Amazing Videos?
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Join creators using VideoHelper to automate their video production workflow
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
                <Button asChild size="lg" className="text-base px-8 h-12">
                  <Link href="/login">
                    Get Started Now
                    <span className="ml-2">→</span>
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="text-base px-8 h-12">
                  <Link href="/login">
                    View Demo
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/50 bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="size-8 rounded-lg bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center">
                  <svg className="size-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
                  </svg>
                </div>
                <span className="font-bold text-lg">VideoHelper</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Enterprise-grade AI video generation platform
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="font-semibold">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/login" className="hover:text-foreground transition-colors">Features</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">Workflows</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">Pricing</Link></li>
              </ul>
            </div>

            <div className="space-y-3">
              <h4 className="font-semibold">Resources</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/login" className="hover:text-foreground transition-colors">Documentation</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">API Reference</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">Support</Link></li>
              </ul>
            </div>

            <div className="space-y-3">
              <h4 className="font-semibold">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/login" className="hover:text-foreground transition-colors">About</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">Blog</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">Contact</Link></li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-border/50">
            <p className="text-center text-sm text-muted-foreground">
              © {new Date().getFullYear()} VideoHelper. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
