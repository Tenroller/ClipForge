'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, Filter } from "lucide-react";
import { useTranslations } from 'next-intl';

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
  const t = useTranslations('videos');
  return (
    <Card className="border-2 rounded-2xl bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md shadow-lg hover:shadow-xl transition-all duration-300">
      <CardContent className="p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4 sm:gap-5">
          {/* Search */}
          <div className="md:col-span-2">
            <Label htmlFor="search" className="flex items-center gap-2 mb-2.5 font-semibold text-sm">
              <Search className="size-4 text-primary" />
              {t('filters.search')}
            </Label>
            <Input
              id="search"
              placeholder={t('filters.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
              className="h-11 shadow-sm border-2 focus:border-primary/50 transition-all"
            />
          </div>

          {/* Workflow Filter */}
          <div>
            <Label className="flex items-center gap-2 mb-2.5 font-semibold text-sm">
              <Filter className="size-4 text-primary" />
              {t('filters.workflow')}
            </Label>
            <Select value={workflowFilter} onValueChange={onWorkflowFilterChange}>
              <SelectTrigger className="h-11 shadow-sm border-2 hover:border-primary/50 transition-all">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allWorkflows')}</SelectItem>
                <SelectItem value="moneyprinter">MoneyPrinter</SelectItem>
                <SelectItem value="brainrot">Brainrot</SelectItem>
                <SelectItem value="podcastclips">Podcast Clips</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Posted Filter */}
          <div>
            <Label className="mb-2.5 block font-semibold text-sm">{t('filters.posted')}</Label>
            <Select value={postedFilter} onValueChange={onPostedFilterChange}>
              <SelectTrigger className="h-11 shadow-sm border-2 hover:border-primary/50 transition-all">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allPosted')}</SelectItem>
                <SelectItem value="posted">{t('filters.postedOnly')}</SelectItem>
                <SelectItem value="not_posted">{t('filters.unpostedOnly')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Sort */}
          <div>
            <Label className="mb-2.5 block font-semibold text-sm">{t('sort.sortBy')}</Label>
            <div className="flex gap-2">
              <Select value={sortBy} onValueChange={onSortByChange}>
                <SelectTrigger className="h-11 shadow-sm border-2 hover:border-primary/50 transition-all">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="created_at">{t('sort.createdAt')}</SelectItem>
                  <SelectItem value="size_bytes">{t('sort.size')}</SelectItem>
                  <SelectItem value="filename">{t('sort.filename')}</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortOrder} onValueChange={onSortOrderChange}>
                <SelectTrigger className="w-24 h-11 shadow-sm border-2 hover:border-primary/50 transition-all">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="desc">{t('sort.descending')} ↓</SelectItem>
                  <SelectItem value="asc">{t('sort.ascending')} ↑</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
