import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { useTranslations } from 'next-intl';
import { ArrowRight, Clapperboard, Layers, Wand2, Play, CheckCircle2, Github } from 'lucide-react';

export default function HomePage() {
  const t = useTranslations('landing');

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero Section */}
      <section className="pt-20 pb-32 lg:pt-32 lg:pb-40">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
            {t('hero.title')}{' '}
            <span className="text-foreground">
              {t('hero.titleHighlight')}
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-lg sm:text-xl text-muted-foreground mb-10 leading-relaxed">
            {t('hero.subtitle')}
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button asChild size="lg" className="h-12 px-8 text-base group">
              <Link href="/login">
                {t('hero.ctaStart')}
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-8 text-base">
              <Link href="https://github.com/Tenroller/ai-video-generator" target="_blank">
                <Github className="mr-2 h-4 w-4" />
                {t('hero.ctaSignIn')}
              </Link>
            </Button>
          </div>

          {/* Stats Preview */}
          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto px-4">
            {[
              { label: t('hero.stats.aiModels'), value: '10+' },
              { label: t('hero.stats.ttsVoices'), value: '50+' },
              { label: t('hero.stats.gpuPowered'), value: '100%' },
              { label: t('hero.stats.processingSpeed'), value: '10x' },
            ].map((stat, i) => (
              <div key={i} className="flex flex-col items-center space-y-1">
                <div className="text-3xl font-bold">{stat.value}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-24 border-t">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-4">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('workflows.title')}</h2>
            <p className="text-lg text-muted-foreground">{t('workflows.subtitle')}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-7xl mx-auto">
            {/* Main Feature - MoneyPrinter */}
            <Card className="md:col-span-2 md:row-span-2 overflow-hidden">
              <CardHeader>
                <div className="mb-4">
                  <Wand2 className="h-6 w-6 text-muted-foreground" />
                </div>
                <CardTitle className="text-2xl">{t('workflows.creator.title')}</CardTitle>
                <CardDescription className="text-base">{t('workflows.creator.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  {[
                    t('workflows.creator.features.scriptGeneration'),
                    t('workflows.creator.features.stockFootage'),
                    t('workflows.creator.features.tts'),
                    t('workflows.creator.features.subtitles'),
                  ].map((feature, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="h-4 w-4 text-foreground" />
                      {feature}
                    </div>
                  ))}
                </div>
                <div className="relative h-48 sm:h-64 rounded-lg bg-muted border overflow-hidden">
                  <div className="absolute inset-x-4 top-4 bottom-0 bg-background rounded-t-lg border p-4">
                    <div className="space-y-3">
                      <div className="h-2 w-1/3 bg-muted rounded"></div>
                      <div className="h-2 w-2/3 bg-muted rounded"></div>
                      <div className="h-24 w-full bg-muted rounded-lg mt-4"></div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Feature 2 - Compilations */}
            <Card className="min-h-[300px] overflow-hidden">
              <CardHeader>
                <div className="mb-4">
                  <Layers className="h-5 w-5 text-muted-foreground" />
                </div>
                <CardTitle>{t('workflows.compilations.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground text-sm mb-4">{t('workflows.compilations.description')}</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-foreground" />
                    {t('workflows.compilations.features.youtube')}
                  </li>
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-foreground" />
                    {t('workflows.compilations.features.sceneDetection')}
                  </li>
                </ul>
              </CardContent>
            </Card>

            {/* Feature 3 - Podcast Clips */}
            <Card className="min-h-[300px] overflow-hidden">
              <CardHeader>
                <div className="mb-4">
                  <Clapperboard className="h-5 w-5 text-muted-foreground" />
                </div>
                <CardTitle>{t('workflows.podcastClips.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground text-sm mb-4">{t('workflows.podcastClips.description')}</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-foreground" />
                    {t('workflows.podcastClips.features.viralDetection')}
                  </li>
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-foreground" />
                    {t('workflows.podcastClips.features.faceTracking')}
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 border-t">
        <div className="container mx-auto px-4 text-center mb-16">
          <p className="text-sm text-muted-foreground uppercase tracking-widest mb-4">{t('howItWorks.title')}</p>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">{t('howItWorks.subtitle')}</h2>
        </div>

        <div className="container mx-auto px-4">
          <div className="relative grid grid-cols-1 md:grid-cols-4 gap-8">
            {/* Connecting Line (Desktop) */}
            <div className="hidden md:block absolute top-12 left-[12%] right-[12%] h-px bg-border" />

            {[
              { icon: '1', title: t('howItWorks.steps.choose.title'), desc: t('howItWorks.steps.choose.description') },
              { icon: '2', title: t('howItWorks.steps.processing.title'), desc: t('howItWorks.steps.processing.description') },
              { icon: '3', title: t('howItWorks.steps.monitoring.title'), desc: t('howItWorks.steps.monitoring.description') },
              { icon: '4', title: t('howItWorks.steps.download.title'), desc: t('howItWorks.steps.download.description') },
            ].map((step, i) => (
              <div key={i} className="relative flex flex-col items-center text-center">
                <div className="relative z-10 flex h-24 w-24 items-center justify-center rounded-lg bg-card border">
                  <span className="text-3xl font-bold">{step.icon}</span>
                </div>
                <h3 className="mt-6 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground max-w-[200px]">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t">
        <div className="container mx-auto px-4">
          <div className="py-16 sm:py-24 text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-6">
              {t('cta.title')}
            </h2>
            <p className="max-w-2xl mx-auto text-lg text-muted-foreground mb-10">
              {t('cta.subtitle')}
            </p>
            <Button asChild size="lg" className="px-8 h-12 text-base">
              <Link href="/login">{t('cta.start')}</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t">
        <div className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="space-y-4">
              <div className="flex items-center gap-2 font-bold text-xl">
                <Play className="h-4 w-4 text-muted-foreground" />
                ClipForge
              </div>
              <p className="text-sm text-muted-foreground">
                {t('footer.tagline')}
              </p>
              <div className="flex gap-2">
                <Button variant="ghost" size="icon" className="h-10 w-10" aria-label="GitHub">
                  <Github className="h-5 w-5" />
                </Button>
              </div>
            </div>

            <div>
              <h4 className="font-semibold mb-4">{t('footer.product')}</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.productLinks.features')}</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.productLinks.workflows')}</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.productLinks.pricing')}</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4">{t('footer.resources')}</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.resourcesLinks.documentation')}</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.resourcesLinks.apiReference')}</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4">{t('footer.company')}</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.companyLinks.about')}</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">{t('footer.companyLinks.contact')}</Link></li>
              </ul>
            </div>
          </div>

          <div className="mt-12 pt-8 border-t text-center text-sm text-muted-foreground">
            {t('footer.copyright', { year: new Date().getFullYear() })}
          </div>
        </div>
      </footer>
    </div>
  );
}
