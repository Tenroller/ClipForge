import { Navigation } from '@/components/components/navigation'
import { HeroSection } from '@/components/components/hero-section'
import { FeaturesSection } from '@/components/components/features-section'
import { CTASection } from '@/components/components/cta-section'
import { Footer } from '@/components/components/footer'

type NewLandingPageProps = {
  onGetStarted: () => void
}

export default function NewLandingPage({ onGetStarted }: NewLandingPageProps) {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <main>
        <HeroSection onGetStarted={onGetStarted} />
        <FeaturesSection />
        <CTASection onGetStarted={onGetStarted} />
      </main>
      
      <Footer />
    </div>
  )
}
