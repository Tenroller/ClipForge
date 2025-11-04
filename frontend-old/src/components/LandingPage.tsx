import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'
import { Badge } from '@/components/components/ui/badge'
import { 
  FaFilm, 
  FaStar, 
  FaBrain, 
  FaMicrochip, 
  FaFont, 
  FaPlay, 
  FaCheckCircle, 
  FaArrowRight,
  FaBolt,
  FaDownload,
  FaUsers,
  FaGlobe
} from 'react-icons/fa'
import ThemeToggle from './ThemeToggle'

type LandingPageProps = {
  onGetStarted: () => void
}

export default function LandingPage({ onGetStarted }: LandingPageProps) {
  const [isHovered, setIsHovered] = useState<string | null>(null)

  const features = [
    {
      id: 'ai-powered',
      icon: <FaStar className="size-6 text-blue-500" />,
      title: 'AI-Powered Video Creation',
      description: 'Generate engaging videos from just a topic using advanced AI models like Gemini 2.0 Flash.',
      gradient: 'from-blue-500 to-cyan-500'
    },
    {
      id: 'compilation-mode',
      icon: <FaBrain className="size-6 text-purple-500" />,
      title: 'Smart Compilations',
      description: 'Create compilation videos from existing YouTube content with intelligent clip selection.',
      gradient: 'from-purple-500 to-pink-500'
    },
    {
      id: 'tiktok-subtitles',
      icon: <FaFont className="size-6 text-green-500" />,
      title: 'TikTok-Style Subtitles',
      description: 'Word-by-word highlighting with customizable fonts, colors, and animations.',
      gradient: 'from-green-500 to-emerald-500'
    },
    {
      id: 'gpu-acceleration',
      icon: <FaMicrochip className="size-6 text-orange-500" />,
      title: 'GPU Acceleration',
      description: 'Lightning-fast processing with local GPU support and cloud computing options.',
      gradient: 'from-orange-500 to-red-500'
    },
    {
      id: 'voice-synthesis',
      icon: <FaPlay className="size-6 text-indigo-500" />,
      title: 'Premium Voice Synthesis',
      description: 'High-quality text-to-speech with multiple voice options and natural pronunciation.',
      gradient: 'from-indigo-500 to-blue-500'
    },
    {
      id: 'realtime-progress',
      icon: <FaBolt className="size-6 text-yellow-500" />,
      title: 'Real-time Progress',
      description: 'Live updates and preview as your video is being generated with REST API integration.',
      gradient: 'from-yellow-500 to-orange-500'
    }
  ]

  const stats = [
    { label: 'Videos Generated', value: '10,000+', icon: <FaPlay className="size-5" /> },
    { label: 'Active Users', value: '500+', icon: <FaUsers className="size-5" /> },
    { label: 'Processing Speed', value: '3x Faster', icon: <FaBolt className="size-5" /> },
    { label: 'Global Reach', value: '50+ Countries', icon: <FaGlobe className="size-5" /> }
  ]

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 mb-8 rounded-2xl glass-header mx-4 mt-4 px-6 py-5">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center shadow-lg">
              <FaFilm className="size-6 text-white" />
            </div>
            <div>
              <h1 className="section-title flex items-center gap-2 text-2xl">
                AI Video Creator
              </h1>
              <p className="section-subtitle mt-1">Create stunning videos with AI</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Badge variant="outline" className="hidden sm:flex items-center gap-2 px-3 py-1.5">
              <div className="size-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-xs font-medium">Service Online</span>
            </Badge>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="container-page max-w-7xl mx-auto">
        {/* Hero Section */}
        <section className="text-center py-16 lg:py-24 fade-in">
          <div className="max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-muted/50 border border-border/50 mb-8">
              <FaStar className="size-4 text-blue-500" />
              <span className="text-sm font-medium">Powered by Advanced AI</span>
            </div>
            
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
              Create <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400 bg-clip-text text-transparent">Amazing Videos</span> in Minutes
            </h1>
            
            <p className="text-xl md:text-2xl text-muted-foreground mb-12 leading-relaxed">
              Transform your ideas into engaging videos using AI. Generate scripts, add voices, 
              create subtitles, and produce professional content without any video editing experience.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16">
              <Button 
                size="lg" 
                className="btn-primary text-lg px-8 py-6 h-auto group"
                onClick={onGetStarted}
              >
                <FaStar className="size-5 mr-2 group-hover:animate-pulse" />
                Get Started Free
                <FaArrowRight className="size-5 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
              
              <Button 
                variant="outline" 
                size="lg" 
                className="text-lg px-8 py-6 h-auto group border-border/50 hover:border-border/70"
              >
                <FaPlay className="size-5 mr-2" />
                Watch Demo
              </Button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
              {stats.map((stat, index) => (
                <div key={index} className="text-center">
                  <div className="inline-flex items-center justify-center size-12 rounded-lg bg-muted/30 border border-border/30 mb-3">
                    {stat.icon}
                  </div>
                  <div className="text-2xl md:text-3xl font-bold text-foreground">{stat.value}</div>
                  <div className="text-sm text-muted-foreground">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-16 lg:py-24">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold mb-6">
              Everything You Need to Create
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              Our platform combines cutting-edge AI technology with intuitive tools 
              to make video creation accessible to everyone.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <Card 
                key={feature.id}
                className={`enhanced-card group cursor-pointer transition-all duration-300 ${
                  isHovered === feature.id ? 'scale-105' : ''
                }`}
                onMouseEnter={() => setIsHovered(feature.id)}
                onMouseLeave={() => setIsHovered(null)}
              >
                <CardHeader>
                  <div className={`size-12 rounded-lg bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-4 shadow-lg group-hover:shadow-xl transition-shadow`}>
                    <div className="text-white">
                      {feature.icon}
                    </div>
                  </div>
                  <CardTitle className="text-xl group-hover:text-blue-500 transition-colors">
                    {feature.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground leading-relaxed">
                    {feature.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* How It Works Section */}
        <section className="py-16 lg:py-24">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold mb-6">
              How It Works
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              Create professional videos in just a few simple steps
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Step 1 */}
            <div className="text-center group">
              <div className="relative">
                <div className="size-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto mb-6 text-white text-2xl font-bold shadow-lg group-hover:shadow-xl transition-shadow">
                  1
                </div>
                {/* Connector line */}
                <div className="hidden md:block absolute top-8 left-1/2 w-full h-0.5 bg-gradient-to-r from-blue-500/30 to-purple-600/30 transform translate-x-8"></div>
              </div>
              <h3 className="text-xl font-semibold mb-4">Describe Your Video</h3>
              <p className="text-muted-foreground">
                Simply enter a topic or description of the video you want to create. 
                Our AI will understand your vision.
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center group">
              <div className="relative">
                <div className="size-16 rounded-full bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center mx-auto mb-6 text-white text-2xl font-bold shadow-lg group-hover:shadow-xl transition-shadow">
                  2
                </div>
                {/* Connector line */}
                <div className="hidden md:block absolute top-8 left-1/2 w-full h-0.5 bg-gradient-to-r from-purple-600/30 to-pink-600/30 transform translate-x-8"></div>
              </div>
              <h3 className="text-xl font-semibold mb-4">AI Generates Content</h3>
              <p className="text-muted-foreground">
                Our AI creates a script, finds relevant footage, generates voiceover, 
                and adds engaging subtitles automatically.
              </p>
            </div>

            {/* Step 3 */}
            <div className="text-center group">
              <div className="size-16 rounded-full bg-gradient-to-br from-pink-600 to-emerald-500 flex items-center justify-center mx-auto mb-6 text-white text-2xl font-bold shadow-lg group-hover:shadow-xl transition-shadow">
                3
              </div>
              <h3 className="text-xl font-semibold mb-4">Download & Share</h3>
              <p className="text-muted-foreground">
                Your video is ready! Download in high quality and share across 
                social media platforms instantly.
              </p>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-16 lg:py-24">
          <Card className="enhanced-card bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-emerald-500/10 border-gradient">
            <CardContent className="text-center py-16 px-8">
              <div className="max-w-3xl mx-auto">
                <div className="size-20 rounded-full bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center mx-auto mb-8 shadow-2xl">
                  <FaFilm className="size-10 text-white" />
                </div>
                
                <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold mb-6">
                  Ready to Create Your First Video?
                </h2>
                
                <p className="text-xl text-muted-foreground mb-8 leading-relaxed">
                  Join thousands of creators who are already using AI to produce 
                  amazing video content. No credit card required.
                </p>
                
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button 
                    size="lg" 
                    className="btn-primary text-lg px-8 py-6 h-auto group"
                    onClick={onGetStarted}
                  >
                    <FaStar className="size-5 mr-2 group-hover:animate-pulse" />
                    Start Creating Now
                    <FaArrowRight className="size-5 ml-2 group-hover:translate-x-1 transition-transform" />
                  </Button>
                </div>
                
                <div className="flex items-center justify-center gap-6 mt-8 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <FaCheckCircle className="size-4 text-green-500" />
                    Free to start
                  </div>
                  <div className="flex items-center gap-2">
                    <FaCheckCircle className="size-4 text-green-500" />
                    No watermarks
                  </div>
                  <div className="flex items-center gap-2">
                    <FaCheckCircle className="size-4 text-green-500" />
                    High quality exports
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>

      {/* Footer */}
      <footer className="border-t border-border/30 py-8 mt-16">
        <div className="container-page max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="size-8 rounded-lg bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center">
                <FaFilm className="size-4 text-white" />
              </div>
              <div>
                <div className="font-semibold">AI Video Creator</div>
                <div className="text-xs text-muted-foreground">Powered by AI</div>
              </div>
            </div>
            
            <div className="text-sm text-muted-foreground">
              © 2024 AI Video Creator. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
