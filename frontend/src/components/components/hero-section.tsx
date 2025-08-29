import { Button } from "@/components/components/ui/button"
import { Card } from "@/components/components/ui/card"
import { FaPlay, FaStar, FaBolt } from "react-icons/fa"

type HeroSectionProps = {
  onGetStarted?: () => void
}

export function HeroSection({ onGetStarted }: HeroSectionProps = {}) {
  return (
    <section className="relative py-20 lg:py-32 overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold font-serif text-foreground mb-6">
            Create Stunning
            <span className="text-primary block">AI Videos</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto mb-8 leading-relaxed">
            Transform your ideas into professional videos with our AI-powered platform. Generate scripts, add
            voiceovers, and create compilations with just a few clicks.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Button 
              size="lg" 
              className="bg-primary hover:bg-primary/90 text-lg px-8 py-3"
              onClick={onGetStarted}
            >
              <FaPlay className="mr-2 h-5 w-5" />
              Start Creating
            </Button>
            <Button variant="outline" size="lg" className="text-lg px-8 py-3 bg-transparent">
              Watch Demo
            </Button>
          </div>

          {/* Feature Cards */}
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            <Card className="p-6 bg-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-center w-12 h-12 bg-primary/10 rounded-lg mb-4 mx-auto">
                <FaStar className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">AI Script Generation</h3>
              <p className="text-muted-foreground text-sm">Generate engaging video scripts with advanced AI models</p>
            </Card>

            <Card className="p-6 bg-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-center w-12 h-12 bg-accent/10 rounded-lg mb-4 mx-auto">
                <FaPlay className="h-6 w-6 text-accent" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Voice Synthesis</h3>
              <p className="text-muted-foreground text-sm">
                Choose from multiple TTS voices with preview functionality
              </p>
            </Card>

            <Card className="p-6 bg-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-center w-12 h-12 bg-secondary/10 rounded-lg mb-4 mx-auto">
                <FaBolt className="h-6 w-6 text-secondary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Real-time Preview</h3>
              <p className="text-muted-foreground text-sm">
                See your video come together with live preview and editing
              </p>
            </Card>
          </div>
        </div>
      </div>
    </section>
  )
}
