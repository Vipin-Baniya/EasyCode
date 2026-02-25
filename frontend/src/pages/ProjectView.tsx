import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type Action } from '../services/api'
import { ArrowLeft, Send, CheckCircle, XCircle, Clock, Loader2, AlertTriangle } from 'lucide-react'

const STATUS_META: Record<Action['status'], { label: string; color: string; icon: React.ReactNode }> = {
  pending:    { label: 'Pending',     color: 'text-yellow-400', icon: <Clock size={14} /> },
  planning:   { label: 'Planning',    color: 'text-blue-400',   icon: <Loader2 size={14} className="animate-spin" /> },
  executing:  { label: 'Executing',   color: 'text-blue-400',   icon: <Loader2 size={14} className="animate-spin" /> },
  verifying:  { label: 'Verifying',   color: 'text-blue-400',   icon: <Loader2 size={14} className="animate-spin" /> },
  completed:  { label: 'Completed',   color: 'text-green-400',  icon: <CheckCircle size={14} /> },
  failed:     { label: 'Failed',      color: 'text-red-400',    icon: <XCircle size={14} /> },
  rolled_back:{ label: 'Rolled Back', color: 'text-orange-400', icon: <AlertTriangle size={14} /> },
  cancelled:  { label: 'Cancelled',   color: 'text-gray-400',   icon: <XCircle size={14} /> },
}

function ActionCard({ action }: { action: Action }) {
  const qc = useQueryClient()
  const { id: projectId } = useParams<{ id: string }>()
  const meta = STATUS_META[action.status] ?? STATUS_META.pending

  const approve = useMutation({
    mutationFn: () => api.actions.approve(action.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['actions', projectId] }),
  })
  const reject = useMutation({
    mutationFn: () => api.actions.reject(action.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['actions', projectId] }),
  })

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-white flex-1 pr-4">{action.intent}</p>
        <span className={`flex items-center gap-1 text-xs font-medium ${meta.color}`}>
          {meta.icon} {meta.label}
        </span>
      </div>

      {action.plan && (
        <div className="mb-3 text-xs text-gray-400">
          <span className="font-medium text-gray-300">Plan: </span>
          {(action.plan as { summary?: string }).summary ?? '–'}
        </div>
      )}

      {action.requires_approval && action.status === 'pending' && (
        <div className="flex gap-2 mt-3">
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            className="flex items-center gap-1 bg-green-700 hover:bg-green-600 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors disabled:opacity-50"
          >
            {approve.isPending ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle size={12} />}
            Approve
          </button>
          <button
            onClick={() => reject.mutate()}
            disabled={reject.isPending}
            className="flex items-center gap-1 bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors disabled:opacity-50"
          >
            <XCircle size={12} /> Reject
          </button>
        </div>
      )}

      {action.reflection && (
        <p className="mt-3 text-xs text-gray-400 italic border-t border-gray-700 pt-3">
          💡 {action.reflection}
        </p>
      )}

      {action.error && (
        <p className="mt-3 text-xs text-red-400 border-t border-gray-700 pt-3">
          ⚠️ {action.error}
        </p>
      )}
    </div>
  )
}

export function ProjectView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [intent, setIntent] = useState('')

  const { data: project } = useQuery({
    queryKey: ['project', id],
    queryFn: () => api.projects.get(Number(id)),
    enabled: !!id,
  })

  const { data: actions = [] } = useQuery({
    queryKey: ['actions', id],
    queryFn: async () => {
      // TODO: add GET /projects/{id}/actions endpoint
      return [] as Action[]
    },
    enabled: !!id,
    refetchInterval: 3000, // poll every 3s for status updates
  })

  const createAction = useMutation({
    mutationFn: (i: string) =>
      api.actions.create(Number(id), { intent: i, permission_level: 'review' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['actions', id] })
      setIntent('')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (intent.trim()) createAction.mutate(intent.trim())
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-white transition-colors">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-xl font-bold text-white">{project?.name ?? 'Loading…'}</h1>
          {project?.language && (
            <span className="text-xs text-gray-400">{project.language}</span>
          )}
        </div>
      </header>

      <main className="flex-1 max-w-3xl w-full mx-auto px-6 py-6 flex flex-col gap-4">
        {actions.length > 0 && (
          <div className="space-y-3">
            {[...actions].reverse().map(a => (
              <ActionCard key={a.id} action={a} />
            ))}
          </div>
        )}

        {actions.length === 0 && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-gray-500 text-sm">No actions yet. Tell the AI what to build below.</p>
          </div>
        )}
      </main>

      {/* Intent input */}
      <div className="border-t border-gray-800 px-6 py-4">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-3">
          <textarea
            rows={2}
            value={intent}
            onChange={e => setIntent(e.target.value)}
            placeholder="Describe what you want to build or change…"
            className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit(e as unknown as React.FormEvent)
            }}
          />
          <button
            type="submit"
            disabled={!intent.trim() || createAction.isPending}
            className="self-end flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-3 rounded-xl text-sm font-medium transition-colors"
          >
            {createAction.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </form>
        {createAction.isError && (
          <p className="max-w-3xl mx-auto mt-2 text-red-400 text-xs">{String(createAction.error)}</p>
        )}
      </div>
    </div>
  )
}
