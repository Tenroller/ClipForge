"use client"

import { useId, useRef, useState } from "react"
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { HelpCircle, RefreshCw, Star, Cpu, Loader2, Type, ChevronDown, ChevronUp } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip"
import { Button } from "@/components/ui/button"
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
  // Optional shadow layer control for real-time preview sync
  shadowLayersCount?: number
  onChangeShadowLayersCount?: (value: number) => void
  shadowLayer1Color?: string
  onChangeShadowLayer1Color?: (value: string) => void
  shadowLayer2Color?: string
  onChangeShadowLayer2Color?: (value: string) => void
  shadowLayer3Color?: string
  onChangeShadowLayer3Color?: (value: string) => void
  shadowLayer4Color?: string
  onChangeShadowLayer4Color?: (value: string) => void
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
  // Shadow layer props (controlled from parent for preview sync)
  shadowLayersCount: externalShadowLayersCount,
  onChangeShadowLayersCount,
  shadowLayer1Color: externalShadowLayer1Color,
  onChangeShadowLayer1Color,
  shadowLayer2Color: externalShadowLayer2Color,
  onChangeShadowLayer2Color,
  shadowLayer3Color: externalShadowLayer3Color,
  onChangeShadowLayer3Color,
  shadowLayer4Color: externalShadowLayer4Color,
  onChangeShadowLayer4Color,
}: MoneyPrinterFormProps) {
  const t = useTranslations('creator.form')
  const [useMusic, setUseMusic] = useState(false)
  const [useLocalGpu, setUseLocalGpu] = useState(true)
  const [gpuInfoText, setGpuInfoText] = useState<string>("")
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showSubtitleSettings, setShowSubtitleSettings] = useState(false)

  // TikTok-style subtitle controls
  const [useTikTokSubtitles, setUseTikTokSubtitles] = useState(false)
  const [subtitleFont, setSubtitleFont] = useState("Arial")
  const [subtitleFontSize, setSubtitleFontSize] = useState(48)
  const [subtitleDefaultColor, setSubtitleDefaultColor] = useState("#FFFFFF")
  const [subtitleHighlightColor, setSubtitleHighlightColor] = useState("#FFFFFF")  // Changed to white
  const [subtitleStrokeColor, setSubtitleStrokeColor] = useState("#000000")
  const [subtitleBackgroundColor, setSubtitleBackgroundColor] = useState("#000000")
  const [subtitleStrokeWidth, setSubtitleStrokeWidth] = useState(0)  // Disabled for new style
  const [subtitleBackgroundOpacity, setSubtitleBackgroundOpacity] = useState(0.0)  // Disabled for new style
  const [subtitlePaddingX, setSubtitlePaddingX] = useState(20)  // Increased padding
  const [subtitlePaddingY, setSubtitlePaddingY] = useState(16)

  // 3D Blue Shadow Colors - use external state if provided (for preview sync), otherwise internal
  const shadowLayersCount = externalShadowLayersCount ?? 4
  const setShadowLayersCount = onChangeShadowLayersCount ?? (() => {})
  const shadowLayer1Color = externalShadowLayer1Color ?? "#4A90E2"
  const setShadowLayer1Color = onChangeShadowLayer1Color ?? (() => {})
  const shadowLayer2Color = externalShadowLayer2Color ?? "#357ABD"
  const setShadowLayer2Color = onChangeShadowLayer2Color ?? (() => {})
  const shadowLayer3Color = externalShadowLayer3Color ?? "#2E5F8A"
  const setShadowLayer3Color = onChangeShadowLayer3Color ?? (() => {})
  const shadowLayer4Color = externalShadowLayer4Color ?? "#1E3F5A"
  const setShadowLayer4Color = onChangeShadowLayer4Color ?? (() => {})
  
  // Whisper-enhanced subtitle options
  const [useWhisperEnhanced, setUseWhisperEnhanced] = useState(false)
  const [whisperModel, setWhisperModel] = useState("base")
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
      <Card>
        <form onSubmit={onSubmit} id={formId}>
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <div className="size-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Star className="size-4 text-white" />
              </div>
              Video Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Hidden fields to ensure form has values expected by backend */}
            <input type="hidden" name="aiModel" value={aiModel} />
            <input type="hidden" name="voice" value={voice} />
            <input type="hidden" name="subtitlesPosition" value={subtitlesPosition} />
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
            <input type="hidden" name="shadowLayersCount" value={shadowLayersCount.toString()} />
            <input type="hidden" name="shadowLayer1Color" value={shadowLayer1Color} />
            <input type="hidden" name="shadowLayer2Color" value={shadowLayer2Color} />
            <input type="hidden" name="shadowLayer3Color" value={shadowLayer3Color} />
            <input type="hidden" name="shadowLayer4Color" value={shadowLayer4Color} />
            <input type="hidden" name="useWhisperEnhanced" value={useWhisperEnhanced.toString()} />
            <input type="hidden" name="whisperModel" value={whisperModel} />
            <input type="hidden" name="useMusic" value={useMusic ? "1" : ""} />
            <input type="hidden" name="useGPU" value={useLocalGpu ? "1" : ""} />

            {/* Basic Settings */}
            <div className="space-y-4">
              <div className="text-sm font-semibold text-foreground/90 flex items-center gap-2">
                <Star className="size-4 text-blue-500" />
                Basic Settings
              </div>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor={subjectId}>{t('videoSubject')}</Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 px-3 text-xs"
                      disabled={suggesting}
                      onClick={async () => {
                        try {
                          setSuggesting(true)
                          const base = apiBase || ''
                          const res = await fetch(`${base}/api/AIvideos/suggest-subject`, {
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
                      title={t('generateWithAI')}
                    >
                      <Star className="size-3" />
                      {suggesting ? t('generating') : t('generate')}
                    </Button>
                  </div>
                  <Input
                    id={subjectId}
                    name="videoSubject"
                    placeholder={t('videoSubjectPlaceholder')}
                    required
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  <div className="flex flex-col">
                    <div className="flex items-center justify-between min-h-[1.5rem] mb-2">
                      <Label htmlFor={modelId} className="flex items-center gap-1">
                        {t('aiModel')}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <HelpCircle className="size-3.5 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent>{t('chooseCapableModel')}</TooltipContent>
                        </Tooltip>
                      </Label>
                    </div>
                    <Select value={aiModel} onValueChange={onChangeAiModel}>
                      <SelectTrigger id={modelId}>
                        <SelectValue placeholder={t('selectModel')} />
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

                  <div className="flex flex-col">
                    <div className="flex items-center justify-between min-h-[1.5rem] mb-2">
                      <Label htmlFor={voiceId}>{t('voice')}</Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-6 w-6 p-0 flex-shrink-0"
                        title={voiceLoading ? t('loadingSample') : t('playSample')}
                        disabled={!voice || voiceLoading}
                        onClick={async () => {
                          if (!voice) return
                          try {
                            setVoiceLoading(true)
                            try { audioRef.current?.pause() } catch {}
                            const base = apiBase || ''
                            const sampleUrl = `${base}/api/voice-sample?voice=${encodeURIComponent(voice)}&t=${Date.now()}`
                            const audio = new Audio(sampleUrl)
                            audioRef.current = audio
                            audio.onended = () => { setVoiceLoading(false) }
                            audio.onerror = () => { setVoiceLoading(false) }
                            await audio.play()
                            setTimeout(() => setVoiceLoading(false), 300)
                          } catch {
                            setVoiceLoading(false)
                          }
                        }}
                      >
                        {voiceLoading ? '…' : '▶'}
                      </Button>
                    </div>
                    <Select value={voice} onValueChange={onChangeVoice}>
                      <SelectTrigger id={voiceId}>
                        <SelectValue placeholder={t('selectVoice')} />
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
                  </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  <div className="flex flex-col">
                    <div className="min-h-[1.5rem] mb-2 flex items-center">
                      <Label htmlFor={colorId}>{t('subtitleColor')}</Label>
                    </div>
                    <div className="flex items-center gap-3">
                      <input
                        id={colorId}
                        name="color"
                        type="color"
                        value={subtitleColor}
                        onChange={(e) => onChangeSubtitleColor(e.target.value)}
                        className="h-10 w-16 rounded-md border bg-background p-1 flex-shrink-0"
                      />
                      <div className="flex-1 px-3 py-2 text-sm bg-muted/30 rounded-md border font-mono">
                        {subtitleColor}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col">
                    <div className="flex items-center justify-between min-h-[1.5rem] mb-2">
                      <Label htmlFor="use-music">{t('backgroundMusic')}</Label>
                      <Switch
                        id="use-music"
                        checked={useMusic}
                        onCheckedChange={setUseMusic}
                      />
                    </div>
                    <div className="min-h-[2.5rem] flex items-start">
                      {useMusic && (
                        <Input
                          id={musicZipId}
                          name="zipUrl"
                          type="url"
                          placeholder={t('zipUrlPlaceholder')}
                          className="w-full"
                        />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Advanced Subtitle Settings - Collapsible */}
            <div className="space-y-3">
              <button
                type="button"
                onClick={() => setShowSubtitleSettings(!showSubtitleSettings)}
                className="flex items-center gap-2 text-sm font-medium text-foreground/90 hover:text-foreground transition-colors"
              >
                <Type className="size-4 text-green-500" />
                {t('advancedSubtitleOptions')}
                                  {showSubtitleSettings ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
              </button>
              
              {showSubtitleSettings && (
                <div className="space-y-4 pl-4 border-l-2 border-green-200 dark:border-green-800">
                  <div className="flex items-center gap-3">
                    <Switch
                      id="useTikTokSubtitles"
                      checked={useTikTokSubtitles}
                      onCheckedChange={setUseTikTokSubtitles}
                    />
                    <Label htmlFor="useTikTokSubtitles" className="flex-1">
                      {t('enableWordByWord')}
                    </Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="size-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>{t('highlightEachWord')}</TooltipContent>
                    </Tooltip>
                  </div>

                  {/* Whisper Enhanced Subtitles Options */}
                  <div className="flex items-center gap-3">
                    <Switch
                      id="useWhisperEnhanced"
                      checked={useWhisperEnhanced}
                      onCheckedChange={setUseWhisperEnhanced}
                    />
                    <Label htmlFor="useWhisperEnhanced" className="flex-1">
                      {t('useWhisperTiming')}
                    </Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="size-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>{t('whisperTooltip')}</TooltipContent>
                    </Tooltip>
                  </div>

                  {useWhisperEnhanced && (
                    <div className="space-y-2 pl-4 border-l border-blue-200 dark:border-blue-800">
                      <Label>{t('whisperModel')}</Label>
                      <Select value={whisperModel} onValueChange={setWhisperModel}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="tiny">Tiny (fastest, less accurate)</SelectItem>
                          <SelectItem value="base">Base (balanced)</SelectItem>
                          <SelectItem value="small">Small (good accuracy)</SelectItem>
                          <SelectItem value="medium">Medium (better accuracy)</SelectItem>
                          <SelectItem value="large">Large (best accuracy, slowest)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {useTikTokSubtitles && (
                    <div className="grid gap-4 pl-4 border-l border-green-200 dark:border-green-800">
                      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <Label>{t('font')}</Label>
                          <Select value={subtitleFont} onValueChange={setSubtitleFont}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Arial-Bold">Arial Bold</SelectItem>
                              <SelectItem value="Arial">Arial</SelectItem>
                              <SelectItem value="Helvetica-Bold">Helvetica Bold</SelectItem>
                              <SelectItem value="Helvetica">Helvetica</SelectItem>
                              <SelectItem value="Impact">Impact</SelectItem>
                              <SelectItem value="Times-Bold">Times Bold</SelectItem>
                              <SelectItem value="Times">Times</SelectItem>
                              <SelectItem value="Comic-Sans-MS">Comic Sans MS</SelectItem>
                              <SelectItem value="Montserrat">Montserrat</SelectItem>
                              <SelectItem value="Roboto">Roboto</SelectItem>
                              <SelectItem value="Open Sans">Open Sans</SelectItem>
                              <SelectItem value="Poppins">Poppins</SelectItem>
                              <SelectItem value="Nunito">Nunito</SelectItem>
                              <SelectItem value="Source Sans Pro">Source Sans Pro</SelectItem>
                              <SelectItem value="System">System Font</SelectItem>
                              <SelectItem value="SF Pro Display">SF Pro Display (Apple)</SelectItem>
                              <SelectItem value="Segoe UI">Segoe UI (Windows)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t('fontSize')}</Label>
                          <Input
                            type="number"
                            min={20}
                            max={100}
                            value={subtitleFontSize}
                            onChange={(e) => setSubtitleFontSize(Number(e.target.value))}
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <Label>{t('shadowLayers')}</Label>
                        <div className="grid grid-cols-3 gap-2">
                          <button
                            type="button"
                            onClick={() => setShadowLayersCount(2)}
                            className={`h-10 rounded-md border text-xs font-medium transition-colors ${
                              shadowLayersCount === 2 
                                ? 'bg-primary text-primary-foreground border-primary' 
                                : 'bg-background border-border hover:bg-muted/60'
                            }`}
                          >
                            {t('soft')} (2)
                          </button>
                          <button
                            type="button"
                            onClick={() => setShadowLayersCount(3)}
                            className={`h-10 rounded-md border text-xs font-medium transition-colors ${
                              shadowLayersCount === 3 
                                ? 'bg-primary text-primary-foreground border-primary' 
                                : 'bg-background border-border hover:bg-muted/60'
                            }`}
                          >
                            {t('standard')} (3)
                          </button>
                          <button
                            type="button"
                            onClick={() => setShadowLayersCount(4)}
                            className={`h-10 rounded-md border text-xs font-medium transition-colors ${
                              shadowLayersCount === 4 
                                ? 'bg-primary text-primary-foreground border-primary' 
                                : 'bg-background border-border hover:bg-muted/60'
                            }`}
                          >
                            {t('professional')} (4)
                          </button>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {t('moreLayers')}
                        </p>
                      </div>
                      
                      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
                        <div className="space-y-2">
                          <Label>{t('textColor')}</Label>
                          <input
                            type="color"
                            value={subtitleDefaultColor}
                            onChange={(e) => setSubtitleDefaultColor(e.target.value)}
                            className="h-10 w-full rounded-md border bg-background p-1"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('shadowLayer1')}</Label>
                          <input
                            type="color"
                            value={shadowLayer1Color}
                            onChange={(e) => setShadowLayer1Color(e.target.value)}
                            className="h-10 w-full rounded-md border bg-background p-1"
                          />
                        </div>
                        {shadowLayersCount >= 3 && (
                          <div className="space-y-2">
                            <Label>{t('shadowLayer2')}</Label>
                            <input
                              type="color"
                              value={shadowLayer2Color}
                              onChange={(e) => setShadowLayer2Color(e.target.value)}
                              className="h-10 w-full rounded-md border bg-background p-1"
                            />
                          </div>
                        )}
                        <div className="space-y-2">
                          <Label>Shadow Layer {shadowLayersCount >= 3 ? '3' : '2'}</Label>
                          <input
                            type="color"
                            value={shadowLayer3Color}
                            onChange={(e) => setShadowLayer3Color(e.target.value)}
                            className="h-10 w-full rounded-md border bg-background p-1"
                          />
                        </div>
                        {shadowLayersCount === 4 && (
                          <div className="space-y-2">
                            <Label>Shadow Layer 4</Label>
                            <input
                              type="color"
                              value={shadowLayer4Color}
                              onChange={(e) => setShadowLayer4Color(e.target.value)}
                              className="h-10 w-full rounded-md border bg-background p-1"
                            />
                          </div>
                        )}
                      </div>
                      
                      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
                        <div className="space-y-2">
                          <Label>Shadow Layer 4</Label>
                          <input
                            type="color"
                            value={shadowLayer4Color}
                            onChange={(e) => setShadowLayer4Color(e.target.value)}
                            className="h-10 w-full rounded-md border bg-background p-1"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('highlightColor')}</Label>
                          <input
                            type="color"
                            value={subtitleHighlightColor}
                            onChange={(e) => setSubtitleHighlightColor(e.target.value)}
                            className="h-10 w-full rounded-md border bg-background p-1"
                          />
                          <p className="text-xs text-muted-foreground">For word highlighting</p>
                        </div>
                        <div className="space-y-2">
                          <Label>{t('background')}</Label>
                          <input
                            type="color"
                            value={subtitleBackgroundColor}
                            onChange={(e) => setSubtitleBackgroundColor(e.target.value)}
                            className="h-10 w-full rounded-md border bg-background p-1"
                          />
                          <p className="text-xs text-muted-foreground">Usually disabled for 3D effect</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Advanced Options - Collapsible */}
            <div className="space-y-3">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-sm font-medium text-foreground/90 hover:text-foreground transition-colors"
              >
                <Cpu className="size-4 text-purple-500" />
                Advanced Options
                                  {showAdvanced ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
              </button>
              
              {showAdvanced && (
                <div className="space-y-4 pl-4 border-l-2 border-purple-200 dark:border-purple-800">
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-1">
                        <Label htmlFor={parasId}>{t('paragraphs')}</Label>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <HelpCircle className="size-3.5 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent>{t('paragraphsTooltip')}</TooltipContent>
                        </Tooltip>
                      </div>
                      <Input id={parasId} name="paragraphNumber" type="number" min={1} max={10} defaultValue={1} />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center gap-1">
                        <Label htmlFor={threadsId}>{t('threads')}</Label>
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

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="use-local-gpu">Use Local GPU</Label>
                        <p className="text-xs text-muted-foreground">Hardware acceleration</p>
                      </div>
                      <Switch
                        id="use-local-gpu"
                        checked={useLocalGpu}
                        onCheckedChange={(v) => {
                          setUseLocalGpu(!!v)
                        }}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor={promptId}>Custom Prompt (optional)</Label>
                    <Textarea 
                      id={promptId} 
                      name="customPrompt" 
                      placeholder="Provide additional guidance for the script..."
                      rows={3}
                    />
                  </div>
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex-col gap-3 pt-6">
            <Button
              type="submit"
              disabled={!!busy}
              className="w-full"
            >
              {busy ? (
                <>
                                      <Loader2 className="size-4 animate-spin mr-2" />
                  {t('generating')}
                </>
              ) : (
                <>
                                      <Star className="size-4 mr-2" />
                  {t('generateVideo')}
                </>
              )}
            </Button>
            <Button
              type="reset"
              variant="outline"
              className="w-full"
              onClick={(e) => {
                e.currentTarget.form?.reset()
                setUseMusic(false)
                setSubject("")
                setUseTikTokSubtitles(false)
                setSubtitleFont("Arial-Bold")
                setSubtitleFontSize(48)
                setSubtitleDefaultColor("#FFFFFF")
                setSubtitleHighlightColor("#FFFFFF")  // Changed to white
                setSubtitleStrokeColor("#000000")
                setSubtitleBackgroundColor("#000000")
                setSubtitleStrokeWidth(0)  // Disabled for new style
                setSubtitleBackgroundOpacity(0.0)  // Disabled for new style
                setSubtitlePaddingX(20)  // Increased padding
                setSubtitlePaddingY(16)
                setShadowLayersCount(4)  // Professional (4 layers)
                setShadowLayer1Color("#4A90E2")  // Light blue
                setShadowLayer2Color("#357ABD")  // Medium blue
                setShadowLayer3Color("#2E5F8A")  // Dark blue
                setShadowLayer4Color("#1E3F5A")  // Darkest blue
                setUseWhisperEnhanced(false)
                setWhisperModel("base")
                onChangeAiModel(aiModel)
                onChangeVoice(voice)
                onChangeSubtitleColor("#FFFF00")
                onReset?.()
              }}
            >
                                <RefreshCw className="size-4 mr-2" /> {t('reset')}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </TooltipProvider>
  )
}
