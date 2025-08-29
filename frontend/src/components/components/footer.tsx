import { FaVideo, FaGithub, FaTwitter, FaLinkedin, FaEnvelope } from "react-icons/fa"
import { useNavigate } from "react-router-dom"

export function Footer() {
  const navigate = useNavigate()
  
  const footerLinks = {
    product: [
      { name: "AI Video Creator", href: "/creator" },
      { name: "Compilation Generator", href: "/compilations" },
      { name: "Activity Monitor", href: "/activity" },
      { name: "Downloads", href: "/downloads" },
    ],
    company: [
      { name: "About Us", href: "/about" },
      { name: "Blog", href: "/blog" },
      { name: "Careers", href: "/careers" },
      { name: "Contact", href: "/contact" },
    ],
    support: [
      { name: "Help Center", href: "/help" },
      { name: "Documentation", href: "/docs" },
      { name: "API Reference", href: "/api" },
      { name: "Status", href: "/status" },
    ],
    legal: [
      { name: "Privacy Policy", href: "/privacy" },
      { name: "Terms of Service", href: "/terms" },
      { name: "Cookie Policy", href: "/cookies" },
      { name: "GDPR", href: "/gdpr" },
    ],
  }

  const handleNavigation = (href: string) => {
    if (href.startsWith('/')) {
      navigate(href)
    } else {
      window.open(href, '_blank')
    }
  }

  const socialLinks = [
    { name: "GitHub", icon: FaGithub, href: "#" },
    { name: "Twitter", icon: FaTwitter, href: "#" },
    { name: "LinkedIn", icon: FaLinkedin, href: "#" },
    { name: "Email", icon: FaEnvelope, href: "mailto:hello@videoai.com" },
  ]

  return (
    <footer className="bg-muted/50 border-t border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          {/* Brand */}
          <div className="col-span-2">
            <div className="flex items-center mb-4">
              <FaVideo className="h-8 w-8 text-primary mr-2" />
              <span className="text-2xl font-bold font-serif text-foreground">VideoAI</span>
            </div>
            <p className="text-muted-foreground mb-6 max-w-sm leading-relaxed">
              Create professional AI-powered videos with advanced customization, real-time preview, and seamless
              workflow management.
            </p>
            <div className="flex space-x-4">
              {socialLinks.map((social) => (
                <a
                  key={social.name}
                  href={social.href}
                  className="text-muted-foreground hover:text-primary transition-colors"
                  aria-label={`Follow us on ${social.name}`}
                >
                  <social.icon className="h-5 w-5" />
                </a>
              ))}
            </div>
          </div>

          {/* Links */}
          <div>
            <h3 className="font-semibold text-foreground mb-4">Product</h3>
            <ul className="space-y-2">
              {footerLinks.product.map((link) => (
                <li key={link.name}>
                  <button 
                    onClick={() => handleNavigation(link.href)}
                    className="text-muted-foreground hover:text-foreground transition-colors text-sm text-left"
                  >
                    {link.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-4">Company</h3>
            <ul className="space-y-2">
              {footerLinks.company.map((link) => (
                <li key={link.name}>
                  <button 
                    onClick={() => handleNavigation(link.href)}
                    className="text-muted-foreground hover:text-foreground transition-colors text-sm text-left"
                  >
                    {link.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-4">Support</h3>
            <ul className="space-y-2">
              {footerLinks.support.map((link) => (
                <li key={link.name}>
                  <button 
                    onClick={() => handleNavigation(link.href)}
                    className="text-muted-foreground hover:text-foreground transition-colors text-sm text-left"
                  >
                    {link.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-4">Legal</h3>
            <ul className="space-y-2">
              {footerLinks.legal.map((link) => (
                <li key={link.name}>
                  <button 
                    onClick={() => handleNavigation(link.href)}
                    className="text-muted-foreground hover:text-foreground transition-colors text-sm text-left"
                  >
                    {link.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-border mt-12 pt-8 flex flex-col sm:flex-row justify-between items-center">
          <p className="text-muted-foreground text-sm">© 2024 VideoAI. All rights reserved.</p>
          <p className="text-muted-foreground text-sm mt-4 sm:mt-0">Built with ❤️ using Next.js and Tailwind CSS</p>
        </div>
      </div>
    </footer>
  )
}
