"use client"

import { useId, useRef, useState } from "react"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/components/ui/card"
import { Label } from "@/components/components/ui/label"
import { Input } from "@/components/components/ui/input"
import { Textarea } from "@/components/components/ui/textarea"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/components/ui/select"
import { Switch } from "@/components/components/ui/switch"
import { HelpCircle, RefreshCw } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/components/ui/tooltip"
import { Button } from "@/components/components/ui/button"

export type MoneyPrinterFormProps = {
  models: string[]
  aiModel: string
  onChangeAiModel: (value: string) => void
  voices: string[]
  voice: string
  onChangeVoice: (value: string) => void
  subtitleColor: string
  onChangeSubtitleColor: (value: string) => void
  subtitlesPosition: string
  apiBase?: string
  busy?: boolean
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void
  onReset?: () => void
}

export default function MoneyPrinterForm({
  models,
  aiModel,
  onChangeAiModel,
  voices,
  voice,
  onChangeVoice,
  subtitleColor,
  onChangeSubtitleColor,
  subtitlesPosition,
  apiBase,
  busy,
  onSubmit,
  onReset,
}: MoneyPrinterFormProps) {
  const [useMusic, setUseMusic] = useState(false)
  const [voiceLoading, setVoiceLoading] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const subjectId = useId()
  const modelId = useId()
  const parasId = useId()
  const threadsId = useId()
  const colorId = useId()
  const voiceId = useId()
  const promptId = useId()
  const musicZipId = useId()

  return (
    <TooltipProvider>
      <Card className="sticky top-4">
        <form onSubmit={onSubmit}>
          <CardHeader>
            <CardTitle className="text-base">Create videos purrely with AI</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-5">
            {/* Hidden fields to ensure form has values expected by backend */}
            <input type="hidden" name="aiModel" value={aiModel} />
            <input type="hidden" name="voice" value={voice} />
            <input type="hidden" name="subtitlesPosition" value={subtitlesPosition} />
            <input type="hidden" name="useMusic" value={useMusic ? "1" : ""} />

            <fieldset className="grid gap-4">
              <legend className="text-sm font-medium">Content</legend>
              <div className="grid gap-2">
                <Label htmlFor={subjectId}>Subject</Label>
                <Input id={subjectId} name="videoSubject" placeholder="Describe the video topic (e.g., travel hacks)" required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <div className="flex items-center gap-1">
                    <Label htmlFor={modelId}>AI Model</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <HelpCircle className="size-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>Choose a capable, cost‑effective model</TooltipContent>
                    </Tooltip>
                  </div>
                  <Select value={aiModel} onValueChange={onChangeAiModel}>
                    <SelectTrigger id={modelId}>
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.length > 0
                        ? models.map((m) => (
                            <SelectItem key={m} value={m}>
                              {m}
                            </SelectItem>
                          ))
                        : [
                            <SelectItem key="gemini-2.0-flash" value="gemini-2.0-flash">
                              gemini-2.0-flash
                            </SelectItem>,
                          ]}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <div className="flex items-center gap-1">
                    <Label htmlFor={parasId}>Paragraphs</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <HelpCircle className="size-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>Number of script segments</TooltipContent>
                    </Tooltip>
                  </div>
                  <Input id={parasId} name="paragraphNumber" type="number" min={1} max={10} defaultValue={1} />
                </div>
                <div className="grid gap-2">
                  <div className="flex items-center gap-1">
                    <Label htmlFor={threadsId}>Threads</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <HelpCircle className="size-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>Parallel workers; higher is faster, heavier</TooltipContent>
                    </Tooltip>
                  </div>
                  <Input id={threadsId} name="threads" type="number" min={1} max={8} defaultValue={2} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={colorId}>Subtitle Color</Label>
                  <input
                    id={colorId}
                    name="color"
                    type="color"
                    value={subtitleColor}
                    onChange={(e) => onChangeSubtitleColor(e.target.value)}
                    aria-label="Subtitle color"
                    className="h-9 w-full rounded-md border bg-background p-1"
                  />
                </div>
              </div>
            </fieldset>

            <fieldset className="grid gap-4">
              <legend className="text-sm font-medium">Audio</legend>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label htmlFor={voiceId}>Voice</Label>
                  <div className="flex items-center gap-2">
                    <Select value={voice} onValueChange={onChangeVoice}>
                      <SelectTrigger id={voiceId} className="flex-1">
                        <SelectValue placeholder="Select voice" />
                      </SelectTrigger>
                      <SelectContent>
                        {voices.length > 0
                          ? voices.map((v) => (
                              <SelectItem key={v} value={v}>
                                {v}
                              </SelectItem>
                            ))
                          : [
                              <SelectItem key="af_bella" value="af_bella">
                                af_bella
                              </SelectItem>,
                            ]}
                      </SelectContent>
                    </Select>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-9 px-3"
                      title={voiceLoading ? "Loading sample…" : "Play sample"}
                      aria-label="Play voice sample"
                      disabled={!voice || voiceLoading}
                      onClick={async () => {
                        if (!voice) return
                        try {
                          setVoiceLoading(true)
                          // Stop any existing playback
                          try { audioRef.current?.pause() } catch {}
                          const base = apiBase || ''
                          const sampleUrl = `${base}/api/voice-sample?voice=${encodeURIComponent(voice)}&t=${Date.now()}`
                          const audio = new Audio(sampleUrl)
                          audioRef.current = audio
                          audio.onended = () => { setVoiceLoading(false) }
                          audio.onerror = () => { setVoiceLoading(false) }
                          await audio.play()
                          // Reset loading state shortly after playback starts
                          setTimeout(() => setVoiceLoading(false), 300)
                        } catch {
                          setVoiceLoading(false)
                        }
                      }}
                    >
                      {voiceLoading ? '…' : '▶'}
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="use-music">Use Music</Label>
                    <Switch
                      id="use-music"
                      checked={useMusic}
                      onCheckedChange={setUseMusic}
                      aria-describedby={useMusic ? musicZipId : undefined}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor={musicZipId} className="sr-only">
                      ZIP URL of MP3s
                    </Label>
                    <Input
                      id={musicZipId}
                      name="zipUrl"
                      type="url"
                      placeholder="ZIP URL of MP3s (optional)"
                      disabled={!useMusic}
                    />
                  </div>
                </div>
              </div>
            </fieldset>

            <fieldset className="grid gap-3">
              <legend className="text-sm font-medium">Custom Prompt (optional)</legend>
              <div className="grid gap-2">
                <Label htmlFor={promptId} className="sr-only">
                  Custom prompt
                </Label>
                <Textarea id={promptId} name="customPrompt" placeholder="Provide additional guidance for the script..." />
              </div>
            </fieldset>
          </CardContent>
          <CardFooter className="gap-2">
            <Button type="submit" disabled={!!busy} className="inline-flex items-center gap-2">
              {busy ? "Running…" : "Create videos purrely with AI"}
            </Button>
            <Button
              type="reset"
              variant="outline"
              className="inline-flex items-center gap-2"
              onClick={(e) => {
                // reset form UI and notify parent
                e.currentTarget.form?.reset()
                setUseMusic(false)
                onChangeAiModel(aiModel)
                onChangeVoice(voice)
                onChangeSubtitleColor("#FFFF00")
                onReset?.()
              }}
            >
              <RefreshCw className="size-4" /> Reset
            </Button>
          </CardFooter>
        </form>
      </Card>
    </TooltipProvider>
  )
}
