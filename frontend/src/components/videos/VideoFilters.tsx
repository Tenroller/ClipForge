'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, Filter } from "lucide-react";

interface VideoFiltersProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  workflowFilter: string;
  onWorkflowFilterChange: (value: string) => void;
  postedFilter: string;
  onPostedFilterChange: (value: string) => void;
  sortBy: string;
  onSortByChange: (value: string) => void;
  sortOrder: string;
  onSortOrderChange: (value: string) => void;
}

export default function VideoFilters({
  searchTerm,
  onSearchChange,
  workflowFilter,
  onWorkflowFilterChange,
  postedFilter,
  onPostedFilterChange,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
}: VideoFiltersProps) {
  return (
    <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
      <CardContent className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {/* Search */}
          <div className="md:col-span-2">
            <Label htmlFor="search" className="flex items-center gap-2 mb-2">
              <Search className="size-3" />
              Search
            </Label>
            <Input
              id="search"
              placeholder="Search by filename or job ID..."
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </div>

          {/* Workflow Filter */}
          <div>
            <Label className="flex items-center gap-2 mb-2">
              <Filter className="size-3" />
              Workflow
            </Label>
            <Select value={workflowFilter} onValueChange={onWorkflowFilterChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Workflows</SelectItem>
                <SelectItem value="moneyprinter">MoneyPrinter</SelectItem>
                <SelectItem value="brainrot">Brainrot</SelectItem>
                <SelectItem value="podcastclips">Podcast Clips</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Posted Filter */}
          <div>
            <Label className="mb-2 block">Posted Status</Label>
            <Select value={postedFilter} onValueChange={onPostedFilterChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Videos</SelectItem>
                <SelectItem value="posted">Posted</SelectItem>
                <SelectItem value="not_posted">Not Posted</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Sort */}
          <div>
            <Label className="mb-2 block">Sort By</Label>
            <div className="flex gap-2">
              <Select value={sortBy} onValueChange={onSortByChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="created_at">Date</SelectItem>
                  <SelectItem value="size_bytes">Size</SelectItem>
                  <SelectItem value="filename">Name</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortOrder} onValueChange={onSortOrderChange}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="desc">↓</SelectItem>
                  <SelectItem value="asc">↑</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
