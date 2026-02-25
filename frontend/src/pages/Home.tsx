import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type CreateProjectPayload } from '../services/api'
import { PlusCircle, Folder, ChevronRight, Loader2 } from 'lucide-react'

export function Home() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<CreateProjectPayload>({ name: '', language: '' })

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: api.projects.list,
  })

  const createProject = useMutation({
    mutationFn: api.projects.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setShowForm(false)
      setForm({ name: '', language: '' })
    },
  })

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Project Core</h1>
          <p className="text-sm text-gray-400">AI-powered, safe code generation</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <PlusCircle size={16} /> New Project
        </button>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {showForm && (
          <div className="mb-8 bg-gray-900 border border-gray-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Create Project</h2>
            <div className="space-y-3">
              <input
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Project name"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              />
              <input
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Language (e.g. python, typescript)"
                value={form.language ?? ''}
                onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
              />
              <input
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Description (optional)"
                value={form.description ?? ''}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              />
              <div className="flex gap-3">
                <button
                  disabled={!form.name || createProject.isPending}
                  onClick={() => createProject.mutate(form)}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  {createProject.isPending && <Loader2 size={14} className="animate-spin" />}
                  Create
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
              {createProject.isError && (
                <p className="text-red-400 text-sm">{String(createProject.error)}</p>
              )}
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 size={16} className="animate-spin" /> Loading projects…
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20">
            <Folder size={48} className="mx-auto mb-4 text-gray-600" />
            <p className="text-gray-400 mb-4">No projects yet.</p>
            <button
              onClick={() => setShowForm(true)}
              className="text-indigo-400 hover:text-indigo-300 text-sm underline"
            >
              Create your first project
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {projects.map(p => (
              <button
                key={p.id}
                onClick={() => navigate(`/projects/${p.id}`)}
                className="w-full flex items-center justify-between bg-gray-900 hover:bg-gray-800 border border-gray-700 rounded-xl px-5 py-4 transition-colors text-left"
              >
                <div>
                  <span className="font-medium text-white">{p.name}</span>
                  {p.language && (
                    <span className="ml-2 text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                      {p.language}
                    </span>
                  )}
                  {p.description && (
                    <p className="text-sm text-gray-400 mt-1">{p.description}</p>
                  )}
                </div>
                <ChevronRight size={16} className="text-gray-500" />
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
