import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export const keys = {
  overview: ['overview'], repositories: ['repositories'], runs: ['runs'], settings: ['settings'],
  experiments: ['experiments'], datasets: ['datasets'],
  run: (id: string) => ['run', id], repo: (id: string) => ['repository', id],
  tree: (id: string, path: string) => ['tree', id, path], graph: (id: string) => ['graph', id],
  experiment: (id: string) => ['experiment', id],
}

export function useOverview() { return useQuery({ queryKey: keys.overview, queryFn: api.overview, refetchInterval: 5000 }) }
export function useRepositories() { return useQuery({ queryKey: keys.repositories, queryFn: api.repositories }) }
export function useSettings() { return useQuery({ queryKey: keys.settings, queryFn: api.settings, refetchInterval: 8000 }) }
export function useCreateRun() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: api.createRun, onSuccess: async value => {
    await Promise.all([qc.invalidateQueries({ queryKey: keys.runs }), qc.invalidateQueries({ queryKey: keys.overview })])
    return value
  } })
}
export function useImportRepository() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ name, file }: { name: string; file: File }) => api.importRepository(name, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.repositories }) })
}
