import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/components/ui/card"
import { Button } from "@/components/components/ui/button"
import { Badge } from "@/components/components/ui/badge"
import {
  Download,
  Play,
  Pause,
  Eye,
  FileVideo,
  Clock,
  HardDrive,
  X
} from "lucide-react"
import { VideoSkeleton, VideoSkeletons } from "./VideoSkeleton"

interface GeneratedVideo {
  filename: string
  path: string
  size_mb: number
  size_bytes: number
  mtime: number
  compilation_type: string
  download_url: string
  compilation_num?: number
  variation?: string
}

interface GeneratedVideosPanelProps {
  videos: GeneratedVideo[]
  totalSizeMb: number
  compilationTypes: {
    normal: number
    tts: number
    total: number
  }
  onClose?: () => void
  numCompilations?: number
  expectedVideos?: number
  isGenerating?: boolean
}

export function GeneratedVideosPanel({
  videos,
  totalSizeMb,
  compilationTypes,
  onClose,
  numCompilations = 0,
  expectedVideos = 0,
  isGenerating = false
}: GeneratedVideosPanelProps) {
  const [playingVideo, setPlayingVideo] = useState<string | null>(null)
  const [expandedVideo, setExpandedVideo] = useState<string | null>(null)
  const [loadingVideos, setLoadingVideos] = useState<{ [key: string]: boolean }>({})
  const videoRefs = useRef<{ [key: string]: HTMLVideoElement | null }>({})

  // Cleanup video refs when component unmounts
  useEffect(() => {
    return () => {
      // Pause any playing videos before unmounting
      if (playingVideo && videoRefs.current[playingVideo]) {
        videoRefs.current[playingVideo]?.pause()
      }
    }
  }, [playingVideo])

  const formatFileSize = (sizeMb: number) => {
    if (sizeMb >= 1024) {
      return `${(sizeMb / 1024).toFixed(1)} GB`
    }
    return `${sizeMb.toFixed(1)} MB`
  }

  const formatDate = (mtime: number) => {
    return new Date(mtime * 1000).toLocaleString()
  }

  const toggleVideoPlayback = (videoPath: string) => {
    const videoElement = videoRefs.current[videoPath]
    if (!videoElement) return

    if (playingVideo === videoPath) {
      videoElement.pause()
      setPlayingVideo(null)
    } else {
      // Pause any other playing video
      if (playingVideo && videoRefs.current[playingVideo]) {
        videoRefs.current[playingVideo]?.pause()
      }
      
      setLoadingVideos(prev => ({ ...prev, [videoPath]: true }))
      videoElement.play().then(() => {
        setLoadingVideos(prev => ({ ...prev, [videoPath]: false }))
        setPlayingVideo(videoPath)
      }).catch((error) => {
        console.error('Failed to play video:', error)
        setLoadingVideos(prev => ({ ...prev, [videoPath]: false }))
        setPlayingVideo(null)
      })
    }
  }

  const toggleVideoExpansion = (videoPath: string) => {
    if (expandedVideo === videoPath) {
      setExpandedVideo(null)
    } else {
      setExpandedVideo(videoPath)
    }
  }

  const getCompilationTypeColor = (type: string) => {
    switch (type) {
      case "Normal":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
      case "TTS":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300"
    }
  }

  // Show skeleton placeholders when videos are still generating (only for limited mode)
  if (isGenerating && videos.length === 0 && numCompilations > 0 && expectedVideos !== null) {
    return (
      <Card className="enhanced-card border-l-4 border-l-blue-500">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
              <div className="size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            </div>
            <div>
              <div>Generating Videos</div>
              <p className="text-sm font-normal text-muted-foreground">
                {expectedVideos !== null
                  ? `Creating ${expectedVideos} video compilations...`
                  : 'Creating unlimited video compilations...'
                }
              </p>
            </div>
          </CardTitle>
          {onClose && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="p-1 h-8 w-8"
            >
              <X className="size-4" />
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <VideoSkeletons
            numCompilations={numCompilations}
            expectedVideos={expectedVideos}
            completedVideos={0}
          />
        </CardContent>
      </Card>
    )
  }

  if (!videos || videos.length === 0) {
    return (
      <Card className="enhanced-card border-l-4 border-l-yellow-500">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-r from-yellow-500 to-orange-600 flex items-center justify-center">
              <FileVideo className="size-4 text-white" />
            </div>
            Generated Videos
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <FileVideo className="size-12 mx-auto mb-4 opacity-50" />
            <p>No videos were generated</p>
            <p className="text-sm">Check the job logs for more information</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="enhanced-card border-l-4 border-l-green-500">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 flex items-center justify-center">
              <FileVideo className="size-4 text-white" />
            </div>
            <div>
              <div>Generated Videos</div>
              <p className="text-sm font-normal text-muted-foreground">
                {videos.length} videos created successfully
              </p>
            </div>
          </CardTitle>
          {onClose && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="p-1 h-8 w-8"
            >
              <X className="size-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Summary Statistics */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-2">
              <FileVideo className="size-4 text-blue-600" />
              <span className="text-sm font-medium text-blue-900 dark:text-blue-100">Total Videos</span>
            </div>
            <div className="text-2xl font-bold text-blue-900 dark:text-blue-100 mt-1">
              {compilationTypes.total}
            </div>
          </div>
          
          <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-2">
              <Play className="size-4 text-green-600" />
              <span className="text-sm font-medium text-green-900 dark:text-green-100">Normal</span>
            </div>
            <div className="text-2xl font-bold text-green-900 dark:text-green-100 mt-1">
              {compilationTypes.normal}
            </div>
          </div>
          
          <div className="p-4 rounded-lg bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-800">
            <div className="flex items-center gap-2">
              <HardDrive className="size-4 text-orange-600" />
              <span className="text-sm font-medium text-orange-900 dark:text-orange-100">TTS</span>
            </div>
            <div className="text-2xl font-bold text-orange-900 dark:text-orange-100 mt-1">
              {compilationTypes.tts}
            </div>
          </div>
          
          <div className="p-4 rounded-lg bg-purple-50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800">
            <div className="flex items-center gap-2">
              <HardDrive className="size-4 text-purple-600" />
              <span className="text-sm font-medium text-purple-900 dark:text-purple-100">Total Size</span>
            </div>
            <div className="text-2xl font-bold text-purple-900 dark:text-purple-100 mt-1">
              {formatFileSize(totalSizeMb)}
            </div>
          </div>
        </div>

        {/* Video List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              {isGenerating ? 'Videos in Progress' : 'Generated Videos'}
            </h3>
            {isGenerating && expectedVideos !== null && expectedVideos > 0 && (
              <Badge variant="outline" className="text-xs">
                {videos.length}/{expectedVideos} completed
              </Badge>
            )}
            {isGenerating && expectedVideos === null && (
              <Badge variant="outline" className="text-xs">
                {videos.length} generated (unlimited mode)
              </Badge>
            )}
          </div>

          {/* Mix of completed videos and skeleton placeholders */}
          {(() => {
            const completedVideos = videos
            const skeletonVideos: Array<{compilationNum: number, variation: 'normal' | 'tts', isCompleted: boolean}> = []

            // Generate skeleton list for expected videos (only for limited mode)
            if (isGenerating && numCompilations > 0 && expectedVideos !== null) {
              for (let i = 1; i <= numCompilations; i++) {
                // Check if normal variation is completed
                const normalCompleted = completedVideos.some(v =>
                  v.compilation_num === i && v.variation === 'normal'
                )
                // Check if TTS variation is completed
                const ttsCompleted = completedVideos.some(v =>
                  v.compilation_num === i && v.variation === 'tts'
                )

                if (!normalCompleted) {
                  skeletonVideos.push({ compilationNum: i, variation: 'normal', isCompleted: false })
                }
                if (!ttsCompleted) {
                  skeletonVideos.push({ compilationNum: i, variation: 'tts', isCompleted: false })
                }
              }
            }

            return (
              <>
                {/* Render completed videos */}
                {videos.map((video, index) => (
                  <div key={video.path} className="border rounded-lg overflow-hidden">
                    {/* Video Header */}
                    <div className="p-4 bg-muted/30 border-b">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Badge
                            variant="outline"
                            className={getCompilationTypeColor(video.compilation_type)}
                          >
                            {video.compilation_type}
                          </Badge>
                          <span className="font-medium text-sm">{video.filename}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleVideoExpansion(video.path)}
                            className="p-1 h-8 w-8"
                          >
                            <Eye className="size-4" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleVideoPlayback(video.path)}
                            className="p-1 h-8 w-8"
                            disabled={loadingVideos[video.path]}
                          >
                            {loadingVideos[video.path] ? (
                              <div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                            ) : playingVideo === video.path ? (
                              <Pause className="size-4" />
                            ) : (
                              <Play className="size-4" />
                            )}
                          </Button>

                          <Button
                            asChild
                            variant="outline"
                            size="sm"
                            className="h-8"
                          >
                            <a
                              href={video.download_url}
                              download
                              target="_blank"
                              rel="noreferrer"
                            >
                              <Download className="size-3 mr-1" />
                              Download
                            </a>
                          </Button>
                        </div>
                      </div>

                      {/* Video Metadata */}
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <HardDrive className="size-3" />
                          {formatFileSize(video.size_mb)}
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className="size-3" />
                          {formatDate(video.mtime)}
                        </div>
                      </div>
                    </div>

                    {/* Video Preview (when expanded) */}
                    {expandedVideo === video.path && (
                      <div className="p-4 bg-black">
                        <video
                          ref={(el) => {
                            videoRefs.current[video.path] = el
                          }}
                          src={video.download_url}
                          controls
                          className="w-full max-h-[400px] rounded-lg"
                          poster="/api/placeholder/640/360"
                          preload="metadata"
                          onPlay={() => setPlayingVideo(video.path)}
                          onPause={() => setPlayingVideo(null)}
                          onEnded={() => setPlayingVideo(null)}
                          onError={(e) => {
                            console.error('Video error:', e)
                            setPlayingVideo(null)
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}

                {/* Render skeleton placeholders for videos still being generated */}
                {skeletonVideos.map((skeleton, index) => (
                  <VideoSkeleton
                    key={`skeleton-${skeleton.compilationNum}-${skeleton.variation}`}
                    compilationNum={skeleton.compilationNum}
                    variation={skeleton.variation}
                    expectedVideos={expectedVideos}
                    completedVideos={videos.length}
                  />
                ))}
              </>
            )
          })()}
        </div>

        {/* Download All Button */}
        <div className="flex justify-center">
          <Button
            asChild
            variant="default"
            size="lg"
            className="px-8"
            disabled={videos.length === 0}
          >
            <a 
              href={`${window.location.origin}/api/download?path=${encodeURIComponent(videos[0]?.path.split('/').slice(0, -1).join('/'))}`}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => {
                if (videos.length === 0) {
                  e.preventDefault()
                }
              }}
            >
              <Download className="size-4 mr-2" />
              Download All Videos ({videos.length})
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
