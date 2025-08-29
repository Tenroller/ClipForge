import { Card, CardContent, CardHeader, CardTitle } from "@/components/components/ui/card"
import { Badge } from "@/components/components/ui/badge"
import { FaVideo, FaMicrophone, FaFont, FaPalette, FaBolt, FaChartBar } from "react-icons/fa"

export function FeaturesSection() {
  const features = [
    {
      icon: FaVideo,
      title: "AI Video Creator",
      description: "Generate professional videos with customizable scripts, voice synthesis, and subtitle styling.",
      badges: ["AI-Powered", "Customizable"],
    },
    {
      icon: FaMicrophone,
      title: "Voice Selection",
      description: "Choose from multiple TTS voices with preview functionality and background music options.",
      badges: ["Multiple Voices", "Preview"],
    },
    {
      icon: FaFont,
      title: "Advanced Subtitles",
      description: "TikTok-style subtitles with extensive customization including fonts, colors, and positioning.",
      badges: ["TikTok Style", "Customizable"],
    },
    {
      icon: FaPalette,
      title: "Visual Customization",
      description: "Real-time color picker, position grid, and live preview in mobile 9:16 format.",
      badges: ["Real-time", "Mobile Format"],
    },
    {
      icon: FaBolt,
      title: "Performance Optimization",
      description: "Local GPU acceleration with CUDA support and cloud GPU processing options.",
      badges: ["GPU Accelerated", "Cloud Ready"],
    },
    {
      icon: FaChartBar,
      title: "Real-time Monitoring",
      description: "WebSocket-based live progress updates with step-by-step visual indicators.",
      badges: ["Live Updates", "Progress Tracking"],
    },
  ]

  return (
    <section className="py-20 bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold font-serif text-foreground mb-4">Powerful Features</h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Everything you need to create professional AI-generated videos with advanced customization options.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <Card key={index} className="bg-card hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <CardHeader>
                <div className="flex items-center justify-center w-12 h-12 bg-primary/10 rounded-lg mb-4">
                  <feature.icon className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-xl font-semibold">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4 leading-relaxed">{feature.description}</p>
                <div className="flex flex-wrap gap-2">
                  {feature.badges.map((badge, badgeIndex) => (
                    <Badge key={badgeIndex} variant="secondary" className="text-xs">
                      {badge}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
