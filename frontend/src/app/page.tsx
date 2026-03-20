import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useTranslations } from 'next-intl';
import { ArrowRight, Wand2, Layers, Clapperboard, Play, Github } from 'lucide-react';

export default function HomePage() {
  const t = useTranslations('landing');

  const workflows = [
    {
      icon: Wand2,
      title: t('workflows.creator.title'),
      description: t('workflows.creator.description'),
      features: [
        t('workflows.creator.features.scriptGeneration'),
        t('workflows.creator.features.stockFootage'),
        t('workflows.creator.features.tts'),
        t('workflows.creator.features.subtitles'),
      ],
      href: '/creator',
    },
    {
      icon: Layers,
      title: t('workflows.compilations.title'),
      description: t('workflows.compilations.description'),
      features: [
        t('workflows.compilations.features.youtube'),
        t('workflows.compilations.features.sceneDetection'),
        t('workflows.compilations.features.clipExtraction'),
      ],
      href: '/compilations',
    },
    {
      icon: Clapperboard,
      title: t('workflows.podcastClips.title'),
      description: t('workflows.podcastClips.description'),
      features: [
        t('workflows.podcastClips.features.viralDetection'),
        t('workflows.podcastClips.features.faceTracking'),
        t('workflows.podcastClips.features.karaoke'),
      ],
      href: '/podcastclips',
    },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <section className="pt-24 pb-20 lg:pt-32 lg:pb-28">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6">
            {t('hero.title')}
          </h1>

          <p className="text-lg text-muted-foreground mb-10 leading-relaxed">
            {t('hero.subtitle')}
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button asChild size="lg" className="h-11 px-6 text-base group">
              <Link href="/login">
                {t('hero.ctaStart')}
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-11 px-6 text-base">
              <Link href="https://github.com/Tenroller/ai-video-generator" target="_blank">
                <Github className="mr-2 h-4 w-4" />
                GitHub
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Workflows */}
      <section className="py-20 border-t">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl">
          <div className="text-center mb-14">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">{t('workflows.title')}</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {workflows.map((wf) => (
              <Link
                key={wf.href}
                href={wf.href}
                className="group rounded-lg border bg-card p-6 transition-colors hover:bg-muted/50"
              >
                <wf.icon className="h-5 w-5 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">{wf.title}</h3>
                <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
                  {wf.description}
                </p>
                <ul className="space-y-1.5">
                  {wf.features.map((feature, i) => (
                    <li key={i} className="text-xs text-muted-foreground flex items-start gap-2">
                      <span className="mt-1.5 block h-1 w-1 rounded-full bg-muted-foreground/50 shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Play className="h-3.5 w-3.5 text-muted-foreground" />
              ClipForge
            </div>
            <div className="flex items-center gap-4">
              <Button asChild variant="ghost" size="icon" className="h-8 w-8" aria-label="GitHub">
                <Link href="https://github.com/Tenroller/ai-video-generator" target="_blank">
                  <Github className="h-4 w-4" />
                </Link>
              </Button>
              <span className="text-xs text-muted-foreground">
                {t('footer.copyright', { year: new Date().getFullYear() })}
              </span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
