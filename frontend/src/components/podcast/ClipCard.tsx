'use client';

import { useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Clock,
  Edit2,
  Expand,
  Maximize2,
  Pause,
  Play,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Volume2,
  VolumeX,
} from 'lucide-react';
import type { PodcastClip } from '@/lib/api';
import { API_BASE } from '@/lib/api';

interface ClipCardProps {
  clip: PodcastClip;
  projectId: string;
  onRender: () => void;
  onDelete: () => void;
  onLike: () => void;
  onDislike: () => void;
  onEdit?: () => void;
}

export default function ClipCard({
  clip,
  projectId,
  onRender,
  onDelete,
  onLike,
  onDislike,
  onEdit,
}: ClipCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Get the video URL
  const videoUrl = clip.download_url.startsWith('http')
    ? clip.download_url
    : `${API_BASE}${clip.download_url}`;

  // Toggle play/pause
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // Toggle mute
  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  // Cycle playback speed
  const cycleSpeed = () => {
    const speeds = [1, 1.5, 2, 0.5];
    const currentIndex = speeds.indexOf(playbackSpeed);
    const nextSpeed = speeds[(currentIndex + 1) % speeds.length];
    if (videoRef.current) {
      videoRef.current.playbackRate = nextSpeed;
    }
    setPlaybackSpeed(nextSpeed);
  };

  // Toggle fullscreen
  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (!document.fullscreenElement) {
        videoRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        document.exitFullscreen();
        setIsFullscreen(false);
      }
    }
  };

  // Update current time
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  // Set duration when metadata loads
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  // Format time MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get score color based on value
  const getScoreColor = (score: number) => {
    if (score >= 9) return 'bg-green-500';
    if (score >= 8) return 'bg-lime-500';
    if (score >= 7) return 'bg-yellow-500';
    if (score >= 6) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <Card className="group overflow-hidden rounded-xl bg-card border border-border">
      {/* Video Player Container */}
      <div className="relative aspect-[9/16] bg-black">
        {/* Score Badge */}
        <div className="absolute top-3 left-3 z-10">
          <Badge className={`${getScoreColor(clip.viral_score)} text-white border-0 text-xs font-bold px-2.5 py-1`}>
            <span className="opacity-70 mr-1">Score:</span>
            {clip.viral_score.toFixed(1)}
          </Badge>
        </div>

        {/* Time Badge (for sorting indicator) */}
        <div className="absolute top-3 right-3 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
          <Badge variant="secondary" className="bg-black/60 text-white border-0 text-xs">
            <Clock className="h-3 w-3 mr-1" />
            {clip.duration_formatted}
          </Badge>
        </div>

        {/* Action Buttons Overlay */}
        <div className="absolute top-12 right-3 z-10 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-red-500/80 hover:bg-red-600 border-0 rounded-full"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 className="h-4 w-4 text-white" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className={`h-8 w-8 border-0 rounded-full ${
              clip.likes > 0 ? 'bg-green-500 hover:bg-green-600' : 'bg-black/60 hover:bg-green-500/80'
            }`}
            onClick={(e) => {
              e.stopPropagation();
              onLike();
            }}
          >
            <ThumbsUp className="h-4 w-4 text-white" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className={`h-8 w-8 border-0 rounded-full ${
              clip.dislikes > 0 ? 'bg-red-500 hover:bg-red-600' : 'bg-black/60 hover:bg-red-500/80'
            }`}
            onClick={(e) => {
              e.stopPropagation();
              onDislike();
            }}
          >
            <ThumbsDown className="h-4 w-4 text-white" />
          </Button>
        </div>

        {/* Video Element */}
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full h-full object-contain"
          muted={isMuted}
          loop
          playsInline
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={() => setIsPlaying(false)}
          onClick={togglePlay}
        />

        {/* Play/Pause Overlay */}
        {!isPlaying && (
          <div
            className="absolute inset-0 flex items-center justify-center bg-black/20 cursor-pointer"
            onClick={togglePlay}
          >
            <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
              <Play className="h-8 w-8 text-black ml-1" fill="currentColor" />
            </div>
          </div>
        )}

        {/* Video Controls */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3 pt-8">
          {/* Progress Bar */}
          <div className="w-full h-1 bg-white/30 rounded-full mb-2 cursor-pointer">
            <div
              className="h-full bg-white rounded-full transition-all"
              style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
            />
          </div>

          {/* Controls Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-white hover:bg-white/20"
                onClick={togglePlay}
              >
                {isPlaying ? (
                  <Pause className="h-4 w-4" fill="currentColor" />
                ) : (
                  <Play className="h-4 w-4" fill="currentColor" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-white hover:bg-white/20"
                onClick={toggleMute}
              >
                {isMuted ? (
                  <VolumeX className="h-4 w-4" />
                ) : (
                  <Volume2 className="h-4 w-4" />
                )}
              </Button>
              <span className="text-xs text-white/80">
                {formatTime(currentTime)} / {formatTime(duration || clip.duration_seconds || 0)}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-white hover:bg-white/20 font-mono"
                onClick={cycleSpeed}
              >
                {playbackSpeed}x
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-white hover:bg-white/20"
                onClick={toggleFullscreen}
              >
                <Maximize2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Clip Info */}
      <div className="p-3 space-y-2">
        {/* Time Interval */}
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs font-normal border-purple-500/50 text-purple-400">
            <Clock className="h-3 w-3 mr-1" />
            INTERVALO
          </Badge>
          <span className="text-sm font-medium text-foreground">
            {clip.time_interval.start_formatted} - {clip.time_interval.end_formatted}
          </span>
        </div>

        {/* Title/Hook */}
        <p className="text-sm line-clamp-2 text-foreground/90">
          {clip.title || clip.hook || 'Clip sem titulo'}
        </p>

        {/* ID */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>ID: {clip.id.substring(0, 20)}...</span>
          {onEdit && (
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              onClick={onEdit}
            >
              <Edit2 className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
