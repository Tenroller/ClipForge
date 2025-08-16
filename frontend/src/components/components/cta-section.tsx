import { Button } from "@/components/components/ui/button"
import { Card } from "@/components/components/ui/card"
import { ArrowRight, Star } from "lucide-react"

type CTASectionProps = {
  onGetStarted?: () => void
}

export function CTASection({ onGetStarted }: CTASectionProps = {}) {
  return (
    <section className="py-20">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <Card className="bg-gradient-to-r from-primary/5 to-accent/5 border-primary/20 p-8 lg:p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="h-5 w-5 fill-primary text-primary" />
              ))}
            </div>
          </div>

          <h2 className="text-3xl sm:text-4xl font-bold font-serif text-foreground mb-4">
            Ready to Create Amazing Videos?
          </h2>

          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto leading-relaxed">
            Join thousands of creators who are already using our AI-powered platform to generate professional videos in
            minutes, not hours.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              className="bg-primary hover:bg-primary/90 text-lg px-8 py-3"
              onClick={onGetStarted}
            >
              Start Free Trial
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button variant="outline" size="lg" className="text-lg px-8 py-3 bg-transparent">
              View Pricing
            </Button>
          </div>

          <p className="text-sm text-muted-foreground mt-6">
            No credit card required • 14-day free trial • Cancel anytime
          </p>
        </Card>
      </div>
    </section>
  )
}
