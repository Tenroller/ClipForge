import { Card, CardContent } from "@/components/components/ui/card"
import { Badge } from "@/components/components/ui/badge"
import { FileVideo, Clock, HardDrive } from "lucide-react"

interface VideoSkeletonProps {
  compilationNum: number
  variation: 'normal' | 'tts'
  isGenerating?: boolean
  expectedVideos?: number
  completedVideos?: number
}

export function VideoSkeleton({
  compilationNum,
  variation,
  isGenerating = true,
  expectedVideos = 0,
  completedVideos = 0
}: VideoSkeletonProps) {
  const getVariationColor = (variation: string) => {
    switch (variation) {
      case "normal":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
      case "tts":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300"
    }
  }

  const getVariationLabel = (variation: string) => {
    switch (variation) {
      case "normal":
        return "Normal"
      case "tts":
        return "TTS Intro"
      default:
        return variation
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Video Header */}
      <div className="p-4 bg-muted/30 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className={getVariationColor(variation)}
            >
              {getVariationLabel(variation)}
            </Badge>
            <span className="font-medium text-sm">
              Compilation #{compilationNum} - {getVariationLabel(variation)}
            </span>
          </div>

          <div className="flex items-center gap-2 text-muted-foreground">
            {isGenerating && (
              <>
                <div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                <span className="text-xs">Generating...</span>
              </>
            )}
          </div>
        </div>

        {/* Video Metadata */}
        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <HardDrive className="size-3" />
            <span>Processing...</span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="size-3" />
            <span>Pending</span>
          </div>
        </div>
      </div>

      {/* Video Preview Skeleton */}
      <div className="p-4 bg-black relative">
        <div className="w-full aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
          <div className="text-center text-white/50">
            <FileVideo className="size-12 mx-auto mb-2" />
            <p className="text-sm">
              {isGenerating ? 'Generating video...' : 'Video ready soon'}
            </p>
            {expectedVideos > 0 && (
              <p className="text-xs mt-1">
                {completedVideos}/{expectedVideos} videos completed
              </p>
            )}
          </div>
        </div>

        {/* Progress indicator overlay */}
        {isGenerating && (
          <div className="absolute inset-4 flex items-center justify-center">
            <div className="bg-black/80 rounded-lg px-4 py-2 text-white text-sm flex items-center gap-2">
              <div className="size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Rendering video...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface VideoSkeletonsProps {
  numCompilations: number
  expectedVideos?: number
  completedVideos?: number
}

export function VideoSkeletons({
  numCompilations,
  expectedVideos = 0,
  completedVideos = 0
}: VideoSkeletonsProps) {
  const skeletonItems = []

  for (let i = 1; i <= numCompilations; i++) {
    // Normal variation
    skeletonItems.push(
      <VideoSkeleton
        key={`compilation-${i}-normal`}
        compilationNum={i}
        variation="normal"
        expectedVideos={expectedVideos}
        completedVideos={completedVideos}
      />
    )

    // TTS variation
    skeletonItems.push(
      <VideoSkeleton
        key={`compilation-${i}-tts`}
        compilationNum={i}
        variation="tts"
        expectedVideos={expectedVideos}
        completedVideos={completedVideos}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Generating Videos</h3>
        {expectedVideos > 0 && (
          <Badge variant="outline" className="text-xs">
            {completedVideos}/{expectedVideos} completed
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {skeletonItems}
      </div>
    </div>
  )
}
