import { FaFilm, FaLink, FaMoon, FaSun, FaCogs, FaBrain } from "react-icons/fa"
import { Tabs, TabsList, TabsTrigger } from "@/components/components/ui/tabs"
import { Badge } from "@/components/components/ui/badge"
import { Button } from "@/components/components/ui/button"
import { useTheme } from "next-themes"

export default function Header() {
  const { theme, setTheme } = useTheme()

  return (
    <header className="px-4 md:px-6 lg:px-8 py-4">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="size-9 rounded-lg bg-muted border flex items-center justify-center">
            <FaFilm className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold leading-none">AI Video Creator</h1>
            <p className="text-xs text-muted-foreground">Create videos purrely with AI or from compilations</p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Badge variant="outline" className="gap-1">
            <FaLink className="size-3" />
            API: localhost:8080
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle theme"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            <FaSun className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <FaMoon className="absolute size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          </Button>
        </div>
      </div>

      <div className="mt-4">
        <Tabs defaultValue="moneyprinter" className="w-full">
          <TabsList className="w-fit">
            <TabsTrigger value="moneyprinter" className="gap-2">
              <FaCogs className="size-4" /> Create videos purrely with AI
            </TabsTrigger>
            <TabsTrigger value="brainrot" disabled className="gap-2">
              <FaBrain className="size-4" /> Create videos from compilations
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </header>
  )
}
