import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'
import { Badge } from '@/components/components/ui/badge'
import { Input } from '@/components/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/components/ui/select'
import { useToast } from '@/components/hooks/use-toast'
import { 
  FaPlay, 
  FaDownload, 
  FaSearch, 
  FaFilter, 
  FaVideo, 
  FaClock, 
  FaHdd,
  FaSyncAlt,
  FaFilm,
  FaBrain,
  FaEye,
  FaShare,
  FaTrash,
  FaUpload,
  FaCheck
} from 'react-icons/fa'
import { cn } from '@/components/lib/utils'

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

interface Video {
  id: string
  job_id: string
  workflow: 'moneyprinter' | 'brainrot'
  filename: string
  path: string
  size_bytes: number
  size_mb: number
  created_at: string
  duration_seconds?: number
  download_url: string
  thumbnail_url?: string
  subtitles_path?: string
  video_type: 'ai_generated' | 'compilation'
  compilation_type?: string
  compilation_num?: number
  posted?: boolean
}

interface VideoStats {
  total_videos: number
  total_size_mb: number
  workflows: {
    moneyprinter: { count: number; size_mb: number }
    brainrot: { count: number; size_mb: number }
  }
  video_types: {
    ai_generated: { count: number; size_mb: number }
    compilation: { count: number; size_mb: number }
  }
}

interface VideosResponse {
  videos: Video[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export default function VideosPage() {
  const [videos, setVideos] = useState<Video[]>([])
  const [stats, setStats] = useState<VideoStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [workflowFilter, setWorkflowFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState('desc')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)
  const [postingVideos, setPostingVideos] = useState<Set<string>>(new Set())
  
  const { toast } = useToast()
  const limit = 20

  // Load videos
  const loadVideos = async (resetOffset = false) => {
    try {
      if (resetOffset) {
        setLoading(true)
        setOffset(0)
      } else {
        setLoadingMore(true)
      }

      const currentOffset = resetOffset ? 0 : offset
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: currentOffset.toString(),
        sort_by: sortBy,
        sort_order: sortOrder
      })

      if (workflowFilter !== 'all') {
        params.append('workflow', workflowFilter)
      }

      const response = await fetch(`${API}/api/videos/all?${params}`)
      if (!response.ok) {
        throw new Error(`Failed to load videos: ${response.statusText}`)
      }

      const data: VideosResponse = await response.json()
      
      if (resetOffset) {
        setVideos(data.videos)
        setOffset(data.limit)
      } else {
        setVideos(prev => [...prev, ...data.videos])
        setOffset(prev => prev + data.limit)
      }
      
      setHasMore(data.has_more)
    } catch (error) {
      console.error('Failed to load videos:', error)
      toast({
        title: 'Error',
        description: 'Failed to load videos. Please try again.',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  // Load stats
  const loadStats = async () => {
    try {
      const response = await fetch(`${API}/api/videos/stats`)
      if (!response.ok) {
        throw new Error(`Failed to load stats: ${response.statusText}`)
      }
      const data: VideoStats = await response.json()
      setStats(data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  // Initial load
  useEffect(() => {
    loadVideos(true)
    loadStats()
  }, [workflowFilter, sortBy, sortOrder])

  // Filter videos by search term
  const filteredVideos = videos.filter(video =>
    video.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    video.job_id.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Get workflow icon
  const getWorkflowIcon = (workflow: string) => {
    switch (workflow) {
      case 'moneyprinter':
        return <FaFilm className="size-4" />
      case 'brainrot':
        return <FaBrain className="size-4" />
      default:
        return <FaVideo className="size-4" />
    }
  }

  // Handle video download
  const handleDownload = (video: Video) => {
    const link = document.createElement('a')
    link.href = `${API}${video.download_url}`
    link.download = video.filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    toast({
      title: 'Download Started',
      description: `Downloading ${video.filename}...`
    })
  }

  // Generate thumbnail for a specific job
  const generateThumbnailForJob = async (jobId: string) => {
    try {
      const response = await fetch(`${API}/api/thumbnails/generate/${jobId}`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`Failed to generate thumbnail: ${response.statusText}`)
      }
      
      const result = await response.json()
      
      toast({
        title: 'Thumbnail Generated',
        description: `Generated ${result.generated_thumbnails} thumbnails for job ${jobId}`
      })
      
      // Refresh the videos list
      loadVideos(true)
      
    } catch (error) {
      console.error('Failed to generate thumbnail:', error)
      toast({
        title: 'Error',
        description: 'Failed to generate thumbnail. Please try again.',
        variant: 'destructive'
      })
    }
  }

  // Post video to webhook
  const handlePostVideo = async (video: Video) => {
    try {
      setPostingVideos(prev => new Set(prev).add(video.id))
      
      const response = await fetch(`${API}/api/videos/post`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          video_id: video.id,
          job_id: video.job_id
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `Failed to post video: ${response.statusText}`)
      }
      
      const result = await response.json()
      
      // Update the video in the local state
      setVideos(prevVideos => 
        prevVideos.map(v => 
          v.id === video.id ? { ...v, posted: true } : v
        )
      )
      
      toast({
        title: 'Video Posted',
        description: `Successfully posted ${video.filename} to webhook`
      })
      
    } catch (error) {
      console.error('Failed to post video:', error)
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to post video. Please try again.',
        variant: 'destructive'
      })
    } finally {
      setPostingVideos(prev => {
        const newSet = new Set(prev)
        newSet.delete(video.id)
        return newSet
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Video Gallery</h1>
          <p className="text-muted-foreground">
            View and manage all your generated videos
          </p>
        </div>
        <Button
          onClick={() => {
            loadVideos(true)
            loadStats()
          }}
          className="w-fit"
        >
          <FaSyncAlt className="size-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Videos</p>
                  <p className="text-2xl font-bold">{stats.total_videos}</p>
                </div>
                <FaVideo className="size-8 text-primary" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Size</p>
                  <p className="text-2xl font-bold">{stats.total_size_mb.toFixed(1)} MB</p>
                </div>
                <FaHdd className="size-8 text-primary" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">AI Generated</p>
                  <p className="text-2xl font-bold">{stats.video_types.ai_generated.count}</p>
                </div>
                <FaFilm className="size-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Compilations</p>
                  <p className="text-2xl font-bold">{stats.video_types.compilation.count}</p>
                </div>
                <FaBrain className="size-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters and Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <FaSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground size-4" />
                <Input
                  placeholder="Search videos by filename or job ID..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Workflow Filter */}
            <Select value={workflowFilter} onValueChange={setWorkflowFilter}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Workflow" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Workflows</SelectItem>
                <SelectItem value="moneyprinter">AI Generated</SelectItem>
                <SelectItem value="brainrot">Compilations</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort By */}
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="created_at">Date Created</SelectItem>
                <SelectItem value="size_mb">File Size</SelectItem>
                <SelectItem value="filename">Filename</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort Order */}
            <Select value={sortOrder} onValueChange={setSortOrder}>
              <SelectTrigger className="w-full sm:w-32">
                <SelectValue placeholder="Order" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="desc">Newest First</SelectItem>
                <SelectItem value="asc">Oldest First</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Videos Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="h-40 w-full mb-4 bg-muted rounded animate-pulse" />
                <div className="h-4 w-3/4 mb-2 bg-muted rounded animate-pulse" />
                <div className="h-3 w-1/2 bg-muted rounded animate-pulse" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredVideos.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <FaVideo className="size-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Videos Found</h3>
            <p className="text-muted-foreground">
              {searchTerm ? 'No videos match your search criteria.' : 'No videos have been generated yet.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredVideos.map((video) => (
              <Card key={video.id} className="group hover:shadow-lg transition-all duration-200">
                <CardContent className="p-0">
                  {/* Video Preview */}
                  <div className="relative aspect-video bg-muted rounded-t-lg overflow-hidden">
                    {video.thumbnail_url ? (
                      <img
                        src={`${API}${video.thumbnail_url}`}
                        alt={`Thumbnail for ${video.filename}`}
                        className="w-full h-full object-cover cursor-pointer transition-transform group-hover:scale-105"
                        onClick={() => setSelectedVideo(video)}
                        onError={(e) => {
                          // Fallback to video element if thumbnail fails to load
                          const target = e.target as HTMLImageElement;
                          const parent = target.parentElement;
                          if (parent) {
                            target.style.display = 'none';
                            const videoElement = parent.querySelector('video');
                            if (videoElement) {
                              videoElement.style.display = 'block';
                            }
                          }
                        }}
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-gray-100 to-gray-300 flex items-center justify-center">
                        <FaVideo className="size-12 text-gray-400" />
                      </div>
                    )}
                    
                    <video
                      className={`w-full h-full object-cover cursor-pointer transition-transform group-hover:scale-105 ${video.thumbnail_url ? 'hidden' : ''}`}
                      poster={video.thumbnail_url ? `${API}${video.thumbnail_url}` : undefined}
                      preload="metadata"
                      onClick={() => setSelectedVideo(video)}
                    >
                      <source src={`${API}${video.download_url}`} type="video/mp4" />
                    </video>
                    
                    {/* Play Overlay */}
                    <div 
                      className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                      onClick={() => setSelectedVideo(video)}
                    >
                      <FaPlay className="size-12 text-white" />
                    </div>

                    {/* Workflow Badge */}
                    <div className="absolute top-2 left-2">
                      <Badge variant="secondary" className="flex items-center gap-1">
                        {getWorkflowIcon(video.workflow)}
                        {video.workflow === 'moneyprinter' ? 'AI' : 'Compilation'}
                      </Badge>
                    </div>

                    {/* Posted Badge */}
                    {video.posted && (
                      <div className="absolute top-2 left-2 mt-8">
                        <Badge variant="default" className="bg-green-600 hover:bg-green-700 flex items-center gap-1">
                          <FaCheck className="size-3" />
                          Posted
                        </Badge>
                      </div>
                    )}

                    {/* Size Badge */}
                    <div className="absolute top-2 right-2">
                      <Badge variant="outline" className="bg-black/50 text-white border-white/20">
                        {formatFileSize(video.size_bytes)}
                      </Badge>
                    </div>

                    {/* Duration Badge */}
                    {video.duration_seconds && (
                      <div className="absolute bottom-2 right-2">
                        <Badge variant="outline" className="bg-black/50 text-white border-white/20 flex items-center gap-1">
                          <FaClock className="size-3" />
                          {Math.floor(video.duration_seconds / 60)}:{(video.duration_seconds % 60).toString().padStart(2, '0')}
                        </Badge>
                      </div>
                    )}
                  </div>

                  {/* Video Info */}
                  <div className="p-4">
                    <h3 className="font-semibold text-sm mb-2 line-clamp-2" title={video.filename}>
                      {video.filename}
                    </h3>
                    
                    <div className="space-y-2 mb-4">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Job ID</span>
                        <span className="font-mono">{video.job_id.slice(0, 8)}...</span>
                      </div>
                      
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Created</span>
                        <span>{formatDate(video.created_at)}</span>
                      </div>

                      {video.compilation_type && (
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>Type</span>
                          <Badge variant="outline" className="text-xs">
                            {video.compilation_type}
                          </Badge>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1"
                        onClick={() => setSelectedVideo(video)}
                      >
                        <FaEye className="size-3 mr-1" />
                        Preview
                      </Button>
                      
                      {!video.thumbnail_url && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => generateThumbnailForJob(video.job_id)}
                          title="Generate thumbnail"
                        >
                          <FaVideo className="size-3" />
                        </Button>
                      )}
                      
                      <Button
                        size="sm"
                        className="flex-1"
                        onClick={() => handleDownload(video)}
                      >
                        <FaDownload className="size-3 mr-1" />
                        Download
                      </Button>
                    </div>

                    {/* Post Button */}
                    <div className="mt-2">
                      {video.posted ? (
                        <div className="flex items-center justify-center gap-2 text-green-600 text-sm">
                          <FaCheck className="size-3" />
                          <span>Posted to Webhook</span>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="default"
                          className="w-full"
                          onClick={() => handlePostVideo(video)}
                          disabled={postingVideos.has(video.id)}
                        >
                          {postingVideos.has(video.id) ? (
                            <>
                              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white mr-1"></div>
                              Posting...
                            </>
                          ) : (
                            <>
                              <FaUpload className="size-3 mr-1" />
                              Post to Webhook
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Load More Button */}
          {hasMore && (
            <div className="text-center">
              <Button
                onClick={() => loadVideos(false)}
                disabled={loadingMore}
                variant="outline"
                className="w-40"
              >
                {loadingMore ? 'Loading...' : 'Load More'}
              </Button>
            </div>
          )}
        </>
      )}

      {/* Video Preview Modal */}
      {selectedVideo && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">{selectedVideo.filename}</h2>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedVideo(null)}
              >
                ✕
              </Button>
            </div>
            
            <div className="space-y-4">
              {/* Video Player */}
              <div className="aspect-video bg-black rounded-lg overflow-hidden">
                <video
                  className="w-full h-full"
                  controls
                  autoPlay
                  src={`${API}${selectedVideo.download_url}`}
                />
              </div>
              
              {/* Video Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <h3 className="font-semibold">Details</h3>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Workflow:</span>
                      <Badge variant="secondary" className="flex items-center gap-1">
                        {getWorkflowIcon(selectedVideo.workflow)}
                        {selectedVideo.workflow === 'moneyprinter' ? 'AI Generated' : 'Compilation'}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">File Size:</span>
                      <span>{formatFileSize(selectedVideo.size_bytes)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Created:</span>
                      <span>{formatDate(selectedVideo.created_at)}</span>
                    </div>
                    {selectedVideo.duration_seconds && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Duration:</span>
                        <span>{Math.floor(selectedVideo.duration_seconds / 60)}:{(selectedVideo.duration_seconds % 60).toString().padStart(2, '0')}</span>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="space-y-2">
                  <h3 className="font-semibold">Actions</h3>
                  <div className="space-y-2">
                    <Button
                      className="w-full"
                      onClick={() => handleDownload(selectedVideo)}
                    >
                      <FaDownload className="size-4 mr-2" />
                      Download Video
                    </Button>
                    
                    {selectedVideo.subtitles_path && (
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={() => {
                          const link = document.createElement('a')
                          link.href = `${API}/api/download?path=${selectedVideo.subtitles_path}`
                          link.download = 'subtitles.json'
                          document.body.appendChild(link)
                          link.click()
                          document.body.removeChild(link)
                        }}
                      >
                        Download Subtitles
                      </Button>
                    )}
                    
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() => {
                        const url = `${window.location.origin}${selectedVideo.download_url}`
                        navigator.clipboard.writeText(url)
                        toast({
                          title: 'Link Copied',
                          description: 'Video link copied to clipboard'
                        })
                      }}
                    >
                      <FaShare className="size-4 mr-2" />
                      Copy Link
                    </Button>

                    {/* Post to Webhook */}
                    {selectedVideo.posted ? (
                      <div className="w-full p-3 bg-green-50 border border-green-200 rounded-lg flex items-center justify-center gap-2 text-green-700">
                        <FaCheck className="size-4" />
                        <span className="font-medium">Posted to Webhook</span>
                      </div>
                    ) : (
                      <Button
                        variant="default"
                        className="w-full"
                        onClick={() => handlePostVideo(selectedVideo)}
                        disabled={postingVideos.has(selectedVideo.id)}
                      >
                        {postingVideos.has(selectedVideo.id) ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                            Posting to Webhook...
                          </>
                        ) : (
                          <>
                            <FaUpload className="size-4 mr-2" />
                            Post to Webhook
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
