import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useTranslations } from 'next-intl';

export default function HomePage() {
  const t = useTranslations('landing');
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
  {/* Animated background gradients */}
  <div className="absolute inset-0 bg-gradient-to-br from-blue-50/80 via-purple-50/80 to-emerald-50/80 pointer-events-none" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="mx-auto max-w-6xl pt-20 pb-24 sm:pt-28 sm:pb-32">
            <div className="text-center space-y-8">
              {/* Badge */}
              <div className="flex justify-center">
                <Badge className="px-4 py-2 text-sm bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-emerald-500/10 border-primary/20 hover:border-primary/40 transition-all">
                  <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-emerald-600 bg-clip-text text-transparent font-semibold">
                    {t('hero.badge')}
                  </span>
                </Badge>
              </div>

              {/* Main Heading */}
              <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl lg:text-7xl xl:text-8xl">
                <span className="block mb-2">{t('hero.title')}</span>
                <span className="block bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 bg-clip-text text-transparent">
                  {t('hero.titleHighlight')}
                </span>
              </h1>

              {/* Subtitle */}
              <p className="mx-auto max-w-2xl text-lg sm:text-xl lg:text-2xl text-muted-foreground leading-relaxed">
                {t('hero.subtitle')}
              </p>

              {/* CTA Buttons */}
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
                <Button asChild size="lg" className="text-base px-8 h-12 shadow-lg">
                  <Link href="/login">
                    {t('hero.ctaStart')}
                    <span className="ml-2">→</span>
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="text-base px-8 h-12 border-2">
                  <Link href="/login">
                    {t('hero.ctaSignIn')}
                  </Link>
                </Button>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-12 max-w-3xl mx-auto">
                {[
                  { label: t('hero.stats.aiModels'), value: '10+' },
                  { label: t('hero.stats.ttsVoices'), value: '50+' },
                  { label: t('hero.stats.gpuPowered'), value: '100%' },
                  { label: t('hero.stats.processingSpeed'), value: '10x' },
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
                {t('workflows.title')}
              </span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              {t('workflows.subtitle')}
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* MoneyPrinter Card */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
              <CardContent className="p-8 space-y-6 relative">
                <div className="size-14 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  <svg className="size-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>

                <div className="space-y-3">
                  <h3 className="text-2xl font-bold">{t('workflows.creator.title')}</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    {t('workflows.creator.description')}
                  </p>
                </div>

                <div className="space-y-2">
                  {[
                    t('workflows.creator.features.scriptGeneration'),
                    t('workflows.creator.features.stockFootage'),
                    t('workflows.creator.features.tts'),
                    t('workflows.creator.features.subtitles'),
                    t('workflows.creator.features.music'),
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
                    {t('workflows.creator.cta')}
                  </Link>
                </Button>
              </CardContent>
            </Card>

            {/* Brainrot/Compilations Card */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
              <CardContent className="p-8 space-y-6 relative">
                <div className="size-14 rounded-2xl bg-gradient-to-br from-purple-500 to-emerald-500 flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  <svg className="size-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                  </svg>
                </div>

                <div className="space-y-3">
                  <h3 className="text-2xl font-bold">{t('workflows.compilations.title')}</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    {t('workflows.compilations.description')}
                  </p>
                </div>

                <div className="space-y-2">
                  {[
                    t('workflows.compilations.features.youtube'),
                    t('workflows.compilations.features.sceneDetection'),
                    t('workflows.compilations.features.clipExtraction'),
                    t('workflows.compilations.features.backgroundVideo'),
                    t('workflows.compilations.features.assembly'),
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
                    {t('workflows.compilations.cta')}
                  </Link>
                </Button>
              </CardContent>
            </Card>

            {/* Podcast Clips Card */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
              <CardContent className="p-8 space-y-6 relative">
                <div className="size-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  <svg className="size-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                </div>

                <div className="space-y-3">
                  <h3 className="text-2xl font-bold">{t('workflows.podcastClips.title')}</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    {t('workflows.podcastClips.description')}
                  </p>
                </div>

                <div className="space-y-2">
                  {[
                    t('workflows.podcastClips.features.viralDetection'),
                    t('workflows.podcastClips.features.faceTracking'),
                    t('workflows.podcastClips.features.mixedMode'),
                    t('workflows.podcastClips.features.karaoke'),
                    t('workflows.podcastClips.features.parallel'),
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
                    {t('workflows.podcastClips.cta')}
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
              {t('features.title')}
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              {t('features.subtitle')}
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: '🚀',
                title: t('features.items.cloudGpu.title'),
                description: t('features.items.cloudGpu.description'),
              },
              {
                icon: '🎯',
                title: t('features.items.aiViral.title'),
                description: t('features.items.aiViral.description'),
              },
              {
                icon: '👤',
                title: t('features.items.faceTracking.title'),
                description: t('features.items.faceTracking.description'),
              },
              {
                icon: '📊',
                title: t('features.items.monitoring.title'),
                description: t('features.items.monitoring.description'),
              },
              {
                icon: '🔄',
                title: t('features.items.resume.title'),
                description: t('features.items.resume.description'),
              },
              {
                icon: '🎨',
                title: t('features.items.subtitles.title'),
                description: t('features.items.subtitles.description'),
              },
              {
                icon: '🗄️',
                title: t('features.items.database.title'),
                description: t('features.items.database.description'),
              },
              {
                icon: '🔊',
                title: t('features.items.voices.title'),
                description: t('features.items.voices.description'),
              },
              {
                icon: '🤖',
                title: t('features.items.models.title'),
                description: t('features.items.models.description'),
              },
              {
                icon: '⚡',
                title: t('features.items.parallel.title'),
                description: t('features.items.parallel.description'),
              },
              {
                icon: '🎬',
                title: t('features.items.mixedMode.title'),
                description: t('features.items.mixedMode.description'),
              },
              {
                icon: '🌐',
                title: t('features.items.api.title'),
                description: t('features.items.api.description'),
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
                {t('howItWorks.title')}
              </span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              {t('howItWorks.subtitle')}
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              {
                step: '01',
                title: t('howItWorks.steps.choose.title'),
                description: t('howItWorks.steps.choose.description'),
              },
              {
                step: '02',
                title: t('howItWorks.steps.processing.title'),
                description: t('howItWorks.steps.processing.description'),
              },
              {
                step: '03',
                title: t('howItWorks.steps.monitoring.title'),
                description: t('howItWorks.steps.monitoring.description'),
              },
              {
                step: '04',
                title: t('howItWorks.steps.download.title'),
                description: t('howItWorks.steps.download.description'),
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
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-emerald-500/10 pointer-events-none" />
            <CardContent className="relative p-12 text-center space-y-6">
              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
                {t('cta.title')}
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                {t('cta.subtitle')}
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
                <Button asChild size="lg" className="text-base px-8 h-12">
                  <Link href="/login">
                    {t('cta.start')}
                    <span className="ml-2">→</span>
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="text-base px-8 h-12">
                  <Link href="/login">
                    {t('cta.demo')}
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
                {t('footer.tagline')}
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="font-semibold">{t('footer.product')}</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.productLinks.features')}</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.productLinks.workflows')}</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.productLinks.pricing')}</Link></li>
              </ul>
            </div>

            <div className="space-y-3">
              <h4 className="font-semibold">{t('footer.resources')}</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.resourcesLinks.documentation')}</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.resourcesLinks.apiReference')}</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.resourcesLinks.support')}</Link></li>
              </ul>
            </div>

            <div className="space-y-3">
              <h4 className="font-semibold">{t('footer.company')}</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.companyLinks.about')}</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.companyLinks.blog')}</Link></li>
                <li><Link href="/login" className="hover:text-foreground transition-colors">{t('footer.companyLinks.contact')}</Link></li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-border/50">
            <p className="text-center text-sm text-muted-foreground">
              {t('footer.copyright', { year: new Date().getFullYear() })}
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
