import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useTranslations } from 'next-intl';
import { ArrowRight, Bot, Clapperboard, Layers, Sparkles, Wand2, Zap, Play, CheckCircle2, Globe, Github, Twitter } from 'lucide-react';

export default function HomePage() {
  const t = useTranslations('landing');

  return (
    <div className="min-h-screen bg-transparent flex flex-col">
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-20 pb-32 lg:pt-32 lg:pb-40">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background pointer-events-none" />

        <div className="container relative mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
            {t('hero.title')}{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-purple-600 animate-gradient-x">
              {t('hero.titleHighlight')}
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-lg sm:text-xl text-muted-foreground mb-10 leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
            {t('hero.subtitle')}
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center animate-in fade-in slide-in-from-bottom-8 duration-700 delay-300">
            <Button asChild size="lg" className="h-12 px-8 text-base shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all rounded-full group">
              <Link href="/login">
                {t('hero.ctaStart')}
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-8 text-base border-primary/20 hover:bg-primary/5 rounded-full">
              <Link href="https://github.com/Tenroller/ai-video-generator" target="_blank">
                <Github className="mr-2 h-4 w-4" />
                {t('hero.ctaSignIn')}
              </Link>
            </Button>
          </div>

          {/* Stats Preview */}
          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto px-4 animate-in fade-in slide-in-from-bottom-12 duration-1000 delay-500">
            {[
              { label: t('hero.stats.aiModels'), value: '10+', icon: Bot },
              { label: t('hero.stats.ttsVoices'), value: '50+', icon: Globe },
              { label: t('hero.stats.gpuPowered'), value: '100%', icon: Zap },
              { label: t('hero.stats.processingSpeed'), value: '10x', icon: Sparkles },
            ].map((stat, i) => (
              <div key={i} className="flex flex-col items-center space-y-2 p-4 rounded-2xl bg-muted/30 backdrop-blur border border-border/50 hover:border-primary/20 transition-colors">
                <stat.icon className="h-6 w-6 text-primary mb-1" />
                <div className="text-2xl font-bold">{stat.value}</div>
                <div className="text-sm text-muted-foreground font-medium">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid (Bento Style) */}
      <section className="py-24 bg-muted/30 relative">
        <div className="absolute inset-0 bg-[url('/grid-pattern.svg')] opacity-[0.03]" />
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-4">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('workflows.title')}</h2>
            <p className="text-lg text-muted-foreground">{t('workflows.subtitle')}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-7xl mx-auto">
            {/* Main Feature - MoneyPrinter */}
            <Card className="md:col-span-2 md:row-span-2 overflow-hidden border-border/50 bg-background/50 backdrop-blur-sm hover:border-primary/30 transition-all hover:shadow-xl group">
              <CardHeader>
                <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500 group-hover:scale-110 transition-transform duration-300">
                  <Wand2 className="h-6 w-6" />
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
                      <CheckCircle2 className="h-4 w-4 text-blue-500" />
                      {feature}
                    </div>
                  ))}
                </div>
                <div className="relative h-48 sm:h-64 rounded-xl bg-gradient-to-br from-blue-500/5 to-purple-500/5 border border-border/50 overflow-hidden group-hover:border-blue-500/20 transition-colors">
                  <div className="absolute inset-x-4 top-4 bottom-0 bg-background rounded-t-xl shadow-2xl border border-border/50 p-4 opacity-80 group-hover:opacity-100 transition-opacity">
                    {/* Mock UI */}
                    <div className="space-y-3">
                      <div className="h-2 w-1/3 bg-muted rounded"></div>
                      <div className="h-2 w-2/3 bg-muted rounded"></div>
                      <div className="h-24 w-full bg-muted/50 rounded-lg mt-4"></div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Feature 2 - Compilations */}
            <Card className="min-h-[300px] overflow-hidden border-border/50 bg-background/50 backdrop-blur-sm hover:border-primary/30 transition-all hover:shadow-lg group">
              <CardHeader>
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-500 group-hover:scale-110 transition-transform duration-300">
                  <Layers className="h-5 w-5" />
                </div>
                <CardTitle>{t('workflows.compilations.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground text-sm mb-4">{t('workflows.compilations.description')}</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-purple-500" />
                    {t('workflows.compilations.features.youtube')}
                  </li>
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-purple-500" />
                    {t('workflows.compilations.features.sceneDetection')}
                  </li>
                </ul>
              </CardContent>
            </Card>

            {/* Feature 3 - Podcast Clips */}
            <Card className="min-h-[300px] overflow-hidden border-border/50 bg-background/50 backdrop-blur-sm hover:border-primary/30 transition-all hover:shadow-lg group">
              <CardHeader>
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500 group-hover:scale-110 transition-transform duration-300">
                  <Clapperboard className="h-5 w-5" />
                </div>
                <CardTitle>{t('workflows.podcastClips.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground text-sm mb-4">{t('workflows.podcastClips.description')}</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    {t('workflows.podcastClips.features.viralDetection')}
                  </li>
                  <li className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    {t('workflows.podcastClips.features.faceTracking')}
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works - Step Process */}
      <section className="py-24 overflow-hidden">
        <div className="container mx-auto px-4 text-center mb-16">
          <Badge variant="outline" className="mb-4 border-primary/20 text-primary">{t('howItWorks.title')}</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">{t('howItWorks.subtitle')}</h2>
        </div>

        <div className="container mx-auto px-4">
          <div className="relative grid grid-cols-1 md:grid-cols-4 gap-8">
            {/* Connecting Line (Desktop) */}
            <div className="hidden md:block absolute top-12 left-[12%] right-[12%] h-0.5 bg-gradient-to-r from-transparent via-border to-transparent" />

            {[
              { icon: '1', title: t('howItWorks.steps.choose.title'), desc: t('howItWorks.steps.choose.description') },
              { icon: '2', title: t('howItWorks.steps.processing.title'), desc: t('howItWorks.steps.processing.description') },
              { icon: '3', title: t('howItWorks.steps.monitoring.title'), desc: t('howItWorks.steps.monitoring.description') },
              { icon: '4', title: t('howItWorks.steps.download.title'), desc: t('howItWorks.steps.download.description') },
            ].map((step, i) => (
              <div key={i} className="relative flex flex-col items-center text-center group">
                <div className="relative z-10 flex h-24 w-24 items-center justify-center rounded-2xl bg-card border border-border shadow-lg transition-all duration-300 group-hover:-translate-y-2 group-hover:border-primary/50 group-hover:shadow-primary/10">
                  <span className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-primary to-purple-600">{step.icon}</span>
                </div>
                <h3 className="mt-6 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground max-w-[200px]">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="relative rounded-3xl bg-primary/5 border border-primary/10 overflow-hidden px-6 py-16 sm:px-12 sm:py-24 text-center">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent pointer-events-none" />

            <h2 className="relative text-3xl font-bold tracking-tight sm:text-4xl mb-6">
              {t('cta.title')}
            </h2>
            <p className="relative max-w-2xl mx-auto text-lg text-muted-foreground mb-10">
              {t('cta.subtitle')}
            </p>
            <div className="relative flex flex-col sm:flex-row gap-4 justify-center">
              <Button asChild size="lg" className="rounded-full px-8 h-12 text-base">
                <Link href="/login">{t('cta.start')}</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t bg-muted/20">
        <div className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="space-y-4">
              <div className="flex items-center gap-2 font-bold text-xl">
                <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Play className="h-4 w-4 text-primary fill-primary" />
                </div>
                ClipForge
              </div>
              <p className="text-sm text-muted-foreground">
                {t('footer.tagline')}
              </p>
              <div className="flex gap-4">
                <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full">
                  <Twitter className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full">
                  <Github className="h-4 w-4" />
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
