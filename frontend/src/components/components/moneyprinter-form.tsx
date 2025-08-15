"use client"

import { useId, useRef, useState } from "react"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/components/ui/card"
import { Label } from "@/components/components/ui/label"
import { Input } from "@/components/components/ui/input"
import { Textarea } from "@/components/components/ui/textarea"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/components/ui/select"
import { Switch } from "@/components/components/ui/switch"
import { HelpCircle, RefreshCw, Sparkles, Cpu, Cloud, Loader2, Type } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/components/ui/tooltip"
import { Button } from "@/components/components/ui/button"
import { toast } from "sonner"

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
  formId?: string
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
  formId,
}: MoneyPrinterFormProps) {
  const [useMusic, setUseMusic] = useState(false)
  const [useLocalGpu, setUseLocalGpu] = useState(true)
  const [useCloudGpu, setUseCloudGpu] = useState(false)
  const [gpuInfoText, setGpuInfoText] = useState<string>("")
  const [voiceLoading, setVoiceLoading] = useState(false)
  
  // TikTok-style subtitle controls
  const [useTikTokSubtitles, setUseTikTokSubtitles] = useState(false)
  const [subtitleFont, setSubtitleFont] = useState("Arial")
  const [subtitleFontSize, setSubtitleFontSize] = useState(48)
  const [subtitleDefaultColor, setSubtitleDefaultColor] = useState("#FFFFFF")
  const [subtitleHighlightColor, setSubtitleHighlightColor] = useState("#FFFF00")
  const [subtitleStrokeColor, setSubtitleStrokeColor] = useState("#000000")
  const [subtitleBackgroundColor, setSubtitleBackgroundColor] = useState("#000000")
  const [subtitleStrokeWidth, setSubtitleStrokeWidth] = useState(2)
  const [subtitleBackgroundOpacity, setSubtitleBackgroundOpacity] = useState(0.6)
  const [subtitlePaddingX, setSubtitlePaddingX] = useState(16)
  const [subtitlePaddingY, setSubtitlePaddingY] = useState(12)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const subjectId = useId()
  const [subject, setSubject] = useState("")
  const [suggesting, setSuggesting] = useState(false)
  const modelId = useId()
  const parasId = useId()
  const threadsId = useId()
  const colorId = useId()
  const voiceId = useId()
  const promptId = useId()
  const musicZipId = useId()

  return (
    <TooltipProvider>
      <Card className="lg:sticky lg:top-6 enhanced-card">
        <form onSubmit={onSubmit} id={formId}>
          <CardHeader className="py-3">
            <CardTitle className="text-base flex items-center gap-3">
              <div className="size-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Sparkles className="size-4 text-white" />
              </div>
              AI Video Generator
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {/* Hidden fields to ensure form has values expected by backend */}
            <input type="hidden" name="aiModel" value={aiModel} />
            <input type="hidden" name="voice" value={voice} />
            <input type="hidden" name="subtitlesPosition" value={subtitlesPosition} />
            
            {/* TikTok-style subtitle hidden fields */}
            <input type="hidden" name="useTikTokSubtitles" value={useTikTokSubtitles.toString()} />
            <input type="hidden" name="subtitleFont" value={subtitleFont} />
            <input type="hidden" name="subtitleFontSize" value={subtitleFontSize.toString()} />
            <input type="hidden" name="subtitleDefaultColor" value={subtitleDefaultColor} />
            <input type="hidden" name="subtitleHighlightColor" value={subtitleHighlightColor} />
            <input type="hidden" name="subtitleStrokeColor" value={subtitleStrokeColor} />
            <input type="hidden" name="subtitleBackgroundColor" value={subtitleBackgroundColor} />
            <input type="hidden" name="subtitleStrokeWidth" value={subtitleStrokeWidth.toString()} />
            <input type="hidden" name="subtitleBackgroundOpacity" value={subtitleBackgroundOpacity.toString()} />
            <input type="hidden" name="subtitlePaddingX" value={subtitlePaddingX.toString()} />
            <input type="hidden" name="subtitlePaddingY" value={subtitlePaddingY.toString()} />
            <input type="hidden" name="useMusic" value={useMusic ? "1" : ""} />
            <input type="hidden" name="useGPU" value={useLocalGpu ? "1" : ""} />
            <input type="hidden" name="useCloudGPU" value={useCloudGpu ? "1" : ""} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Left Column */}
              <div className="space-y-4">
                <div className="form-section compact-section">
                  <div className="form-section-title">
                    <Sparkles className="size-4 text-blue-500" />
                    Content
                  </div>
                  <div className="grid gap-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={subjectId}>Subject</Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 px-2 gap-1"
                        disabled={suggesting}
                        onClick={async () => {
                          try {
                            setSuggesting(true)
                            const base = apiBase || ''
                            const res = await fetch(`${base}/api/moneyprinter/suggest-subject`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ aiModel })
                            })
                            const data = await res.json()
                            if (!res.ok) throw new Error(data?.detail || 'Failed to generate subject')
                            const s = String(data?.subject || '').trim()
                            if (s) setSubject(s)
                          } catch (e) {
                            // Best-effort; keep errors silent in UI to avoid noise
                          } finally {
                            setSuggesting(false)
                          }
                        }}
                        title="Generate with AI"
                        aria-label="Generate subject with AI"
                      >
                        <Sparkles className="size-3.5" />
                        {suggesting ? 'Generating…' : 'Generate with AI'}
                      </Button>
                    </div>
                    <Input
                      id={subjectId}
                      name="videoSubject"
                      placeholder="Describe the video topic (e.g., travel hacks)"
                      required
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-3">
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
                    <div className="grid grid-cols-2 gap-3">
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
                </div>

                <div className="form-section compact-section">
                  <div className="form-section-title">
                    <div className="size-4 rounded bg-gradient-to-r from-pink-400 to-red-400 flex items-center justify-center">
                      <span className="text-[10px] text-white font-bold">♪</span>
                    </div>
                    Audio
                  </div>
                  <div className="grid gap-3">
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
                    <div className="flex items-center justify-between">
                      <Label htmlFor="use-music">Use Music</Label>
                      <Switch
                        id="use-music"
                        checked={useMusic}
                        onCheckedChange={setUseMusic}
                        aria-describedby={useMusic ? musicZipId : undefined}
                      />
                    </div>
                    {useMusic && (
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
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column */}
              <div className="space-y-4">
                <div className="form-section compact-section">
                  <div className="form-section-title">
                    <Type className="size-4 text-green-500" />
                    TikTok-Style Subtitles
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                  <Switch
                    id="useTikTokSubtitles"
                    checked={useTikTokSubtitles}
                    onCheckedChange={setUseTikTokSubtitles}
                  />
                  <Label htmlFor="useTikTokSubtitles" className="flex-1">
                    Enable word-by-word highlighting
                  </Label>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="size-3.5 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent>Highlight each word as it's spoken, TikTok style</TooltipContent>
                  </Tooltip>
                </div>

                {useTikTokSubtitles && (
                  <div className="grid gap-4 pl-4 border-l-2 border-green-200 dark:border-green-800">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="grid gap-2">
                        <Label htmlFor="subtitleFont">Font</Label>
                        <Select value={subtitleFont} onValueChange={setSubtitleFont}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Arial-Bold">Arial Bold</SelectItem>
                            <SelectItem value="Arial">Arial</SelectItem>
                            <SelectItem value="Helvetica-Bold">Helvetica Bold</SelectItem>
                            <SelectItem value="Impact">Impact</SelectItem>
                            <SelectItem value="Times-Bold">Times Bold</SelectItem>
                            <SelectItem value="Comic-Sans-MS">Comic Sans</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="subtitleFontSize">Font Size</Label>
                        <Input
                          type="number"
                          min={20}
                          max={100}
                          value={subtitleFontSize}
                          onChange={(e) => setSubtitleFontSize(Number(e.target.value))}
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="grid gap-2">
                        <Label>Default Text Color</Label>
                        <input
                          type="color"
                          value={subtitleDefaultColor}
                          onChange={(e) => setSubtitleDefaultColor(e.target.value)}
                          className="h-9 w-full rounded-md border bg-background p-1"
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>Highlight Color</Label>
                        <input
                          type="color"
                          value={subtitleHighlightColor}
                          onChange={(e) => setSubtitleHighlightColor(e.target.value)}
                          className="h-9 w-full rounded-md border bg-background p-1"
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="grid gap-2">
                        <Label>Stroke Color</Label>
                        <input
                          type="color"
                          value={subtitleStrokeColor}
                          onChange={(e) => setSubtitleStrokeColor(e.target.value)}
                          className="h-9 w-full rounded-md border bg-background p-1"
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>Background Color</Label>
                        <input
                          type="color"
                          value={subtitleBackgroundColor}
                          onChange={(e) => setSubtitleBackgroundColor(e.target.value)}
                          className="h-9 w-full rounded-md border bg-background p-1"
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-3">
                      <div className="grid gap-2">
                        <Label>Stroke Width</Label>
                        <Input
                          type="number"
                          min={0}
                          max={10}
                          value={subtitleStrokeWidth}
                          onChange={(e) => setSubtitleStrokeWidth(Number(e.target.value))}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>Background Opacity</Label>
                        <Input
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          value={subtitleBackgroundOpacity}
                          onChange={(e) => setSubtitleBackgroundOpacity(Number(e.target.value))}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>Padding</Label>
                        <div className="flex gap-1">
                          <Input
                            type="number"
                            min={0}
                            max={50}
                            value={subtitlePaddingX}
                            onChange={(e) => setSubtitlePaddingX(Number(e.target.value))}
                            placeholder="X"
                            className="text-xs"
                          />
                          <Input
                            type="number"
                            min={0}
                            max={50}
                            value={subtitlePaddingY}
                            onChange={(e) => setSubtitlePaddingY(Number(e.target.value))}
                            placeholder="Y"
                            className="text-xs"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                  </div>
                </div>

                <div className="form-section compact-section">
                  <div className="form-section-title">
                    <Cpu className="size-4 text-purple-500" />
                    Acceleration
                  </div>
                  <div className="space-y-4">
                    <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Cpu className="size-4 text-muted-foreground flex-shrink-0" />
                      <Label htmlFor="use-local-gpu" className="text-sm font-medium">Use local GPU</Label>
                    </div>
                    <Switch
                      id="use-local-gpu"
                      checked={useLocalGpu}
                      onCheckedChange={(v) => {
                        setUseLocalGpu(!!v)
                        if (v) setUseCloudGpu(false)
                      }}
                    />
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 px-3 text-xs flex-shrink-0"
                      onClick={async () => {
                        try {
                          const base = apiBase || ''
                          const res = await fetch(`${base}/api/gpu-info`)
                          const data = await res.json()
                          const local = data?.local || {}
                          const cuda = !!local?.cudaAvailable
                          const name = local?.gpuName || 'Unknown GPU'
                          const mem = typeof local?.memoryGb === 'number' && local.memoryGb > 0 ? `${local.memoryGb.toFixed(1)}GB` : 'n/a'
                          const codec = local?.preferredCodec || 'n/a'
                          const summary = `CUDA: ${cuda ? 'yes' : 'no'} · GPU: ${name} · VRAM: ${mem} · Codec: ${codec}`
                          setGpuInfoText(summary)
                          toast.info(summary)
                        } catch (e) {
                          const msg = 'Could not detect GPU capabilities'
                          setGpuInfoText(msg)
                          toast.error(msg)
                        }
                      }}
                    >
                      Show detected GPU
                    </Button>
                  </div>
                  {gpuInfoText ? (
                    <div className="text-xs text-muted-foreground bg-muted/30 p-2 rounded border-l-2 border-purple-400">
                      {gpuInfoText}
                    </div>
                  ) : null}
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Cloud className="size-4 text-muted-foreground flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <Label htmlFor="use-cloud-gpu" className="text-sm font-medium block">Use Cloud GPU</Label>
                        <div className="text-xs text-muted-foreground mt-0.5">Model service</div>
                      </div>
                    </div>
                    <Switch
                      id="use-cloud-gpu"
                      checked={useCloudGpu}
                      onCheckedChange={(v) => {
                        setUseCloudGpu(!!v)
                        if (v) setUseLocalGpu(false)
                      }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground bg-muted/30 p-2 rounded border-l-2 border-blue-400">
                    Offloads heavy processing to a cloud GPU provider. (Coming soon)
                  </div>
                    </div>
                  </div>
                </div>

                <div className="form-section compact-section">
                  <div className="form-section-title">
                    <HelpCircle className="size-4 text-emerald-500" />
                    Custom Prompt (optional)
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor={promptId} className="sr-only">
                      Custom prompt
                    </Label>
                    <Textarea id={promptId} name="customPrompt" placeholder="Provide additional guidance for the script..." />
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter className="gap-3 pt-4 pb-4">
            <Button
              type="submit"
              disabled={!!busy}
              className="btn-primary inline-flex items-center gap-2 w-full text-sm"
            >
              {busy ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Sparkles className="size-4" />
                  Create Video
                </>
              )}
            </Button>
            <Button
              type="reset"
              variant="outline"
              className="inline-flex items-center gap-2 hover:bg-muted/80 w-full text-sm"
              onClick={(e) => {
                // reset form UI and notify parent
                e.currentTarget.form?.reset()
                setUseMusic(false)
                setSubject("")
                
                // Reset TikTok subtitle options
                setUseTikTokSubtitles(false)
                setSubtitleFont("Arial-Bold")
                setSubtitleFontSize(48)
                setSubtitleDefaultColor("#FFFFFF")
                setSubtitleHighlightColor("#FFFF00")
                setSubtitleStrokeColor("#000000")
                setSubtitleBackgroundColor("#000000")
                setSubtitleStrokeWidth(2)
                setSubtitleBackgroundOpacity(0.6)
                setSubtitlePaddingX(16)
                setSubtitlePaddingY(12)
                
                onChangeAiModel(aiModel)
                onChangeVoice(voice)
                onChangeSubtitleColor("#FFFF00")
                onReset?.()
              }}
            >
              <RefreshCw className="size-4" /> Reset Form
            </Button>
          </CardFooter>
        </form>
      </Card>
    </TooltipProvider>
  )
}
