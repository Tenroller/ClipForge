import { useState } from "react"
import { Button } from "@/components/components/ui/button"
import { FaBars, FaTimes, FaVideo, FaBolt, FaChartLine, FaDownload } from "react-icons/fa"
import { useNavigate, useLocation } from "react-router-dom"

export function Navigation() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const navItems = [
      { name: "AI Video Creator", href: "/creator", icon: FaVideo },
  { name: "Compilation Generator", href: "/compilations", icon: FaBolt },
  { name: "Activity", href: "/activity", icon: FaChartLine },
  { name: "Downloads", href: "/downloads", icon: FaDownload },
  ]

  const handleNavigation = (href: string) => {
    navigate(href)
    setIsMenuOpen(false)
  }

  const handleGetStarted = () => {
    navigate('/creator')
    setIsMenuOpen(false)
  }

  return (
    <nav className="sticky top-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <h1 className="text-2xl font-bold font-serif text-primary">VideoAI</h1>
            </div>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-4">
              {navItems.map((item) => (
                <button
                  key={item.name}
                  onClick={() => handleNavigation(item.href)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring ${
                    location.pathname === item.href 
                      ? 'text-primary bg-accent/20' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-accent/10'
                  }`}
                  aria-label={`Navigate to ${item.name}`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </button>
              ))}
            </div>
          </div>

          {/* Desktop CTA */}
          <div className="hidden md:block">
            <Button 
              className="bg-primary hover:bg-primary/90"
              onClick={handleGetStarted}
            >
              Get Started
            </Button>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-label="Toggle navigation menu"
            >
              {isMenuOpen ? <FaTimes className="h-6 w-6" /> : <FaBars className="h-6 w-6" />}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 border-t border-border">
              {navItems.map((item) => (
                <button
                  key={item.name}
                  onClick={() => handleNavigation(item.href)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md text-base font-medium transition-colors w-full text-left ${
                    location.pathname === item.href 
                      ? 'text-primary bg-accent/20' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-accent/10'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </button>
              ))}
              <div className="pt-4">
                <Button 
                  className="w-full bg-primary hover:bg-primary/90"
                  onClick={handleGetStarted}
                >
                  Get Started
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}
