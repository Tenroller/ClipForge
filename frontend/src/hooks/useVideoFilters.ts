import { useState, useCallback, useEffect } from 'react';

export interface VideoFiltersState {
  searchTerm: string;
  debouncedSearchTerm: string;
  workflowFilter: string;
  postedFilter: string;
  sortBy: string;
  sortOrder: string;
}

export interface VideoFiltersActions {
  setSearchTerm: (value: string) => void;
  setWorkflowFilter: (value: string) => void;
  setPostedFilter: (value: string) => void;
  setSortBy: (value: string) => void;
  setSortOrder: (value: string) => void;
  buildSearchParams: (overrideOffset?: number) => URLSearchParams;
}

export type UseVideoFiltersReturn = VideoFiltersState & VideoFiltersActions;

const DEFAULT_LIMIT = 20;
const SEARCH_DEBOUNCE_MS = 400;

export function useVideoFilters(): UseVideoFiltersReturn {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [workflowFilter, setWorkflowFilter] = useState('all');
  const [postedFilter, setPostedFilter] = useState('all');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');

  // Debounce the search term so we don't fire API calls on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const buildSearchParams = useCallback(
    (overrideOffset?: number): URLSearchParams => {
      const params = new URLSearchParams({
        limit: DEFAULT_LIMIT.toString(),
        offset: (overrideOffset ?? 0).toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (workflowFilter !== 'all') {
        params.append('workflow', workflowFilter);
      }

      if (postedFilter !== 'all') {
        params.append('posted', postedFilter === 'posted' ? 'true' : 'false');
      }

      if (debouncedSearchTerm.trim()) {
        params.append('search', debouncedSearchTerm.trim());
      }

      return params;
    },
    [sortBy, sortOrder, workflowFilter, postedFilter, debouncedSearchTerm]
  );

  return {
    searchTerm,
    debouncedSearchTerm,
    workflowFilter,
    postedFilter,
    sortBy,
    sortOrder,
    setSearchTerm,
    setWorkflowFilter,
    setPostedFilter,
    setSortBy,
    setSortOrder,
    buildSearchParams,
  };
}
