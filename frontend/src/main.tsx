import React from 'react'
import ReactDOM from 'react-dom/client'
import { BarChart3, Lock, RefreshCw, Search, ShieldCheck, Smartphone, Users } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

type Dashboard = {
  teams: number
  players: number
  stats_rows: number
  avg_rating: number | null
  top_goals: any[]
  top_rating: any[]
  positions: { position: string; total: number }[]
}

type Player = { player_id: number; name: string; team_name?: string; position?: string; nationality?: string; age?: number }

function App() {
  const [token, setToken] = React.useState(localStorage.getItem('token') || '')
  const [tempToken, setTempToken] = React.useState('')
  const [username, setUsername] = React.useState('admin')
  const [password, setPassword] = React.useState('Admin@123456')
  const [code, setCode] = React.useState('')
  const [dashboard, setDashboard] = React.useState<Dashboard | null>(null)
  const [players, setPlayers] = React.useState<Player[]>([])
  const [query, setQuery] = React.useState('')
  const [message, setMessage] = React.useState('')
  const [loading, setLoading] = React.useState(false)

  const authHeaders = { Authorization: `Bearer ${token}` }

  async function login(e: React.FormEvent) {
    e.preventDefault()
    setMessage('')
    const res = await fetch(`${API_URL}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })
    const data = await res.json()
    if (!res.ok) { setMessage(data.detail || 'Falha no login'); return }
    if (data.requires_2fa) setTempToken(data.temp_token)
    else { localStorage.setItem('token', data.access_token); setToken(data.access_token) }
  }

  async function verify2FA(e: React.FormEvent) {
    e.preventDefault()
    const res = await fetch(`${API_URL}/auth/2fa/verify`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ temp_token: tempToken, code }) })
    const data = await res.json()
    if (!res.ok) { setMessage(data.detail || 'Código inválido'); return }
    localStorage.setItem('token', data.access_token); setToken(data.access_token); setTempToken('')
  }

  async function loadData() {
    if (!token) return
    const [dashRes, playersRes] = await Promise.all([
      fetch(`${API_URL}/reports/dashboard`, { headers: authHeaders }),
      fetch(`${API_URL}/sofascore/players?limit=100${query ? `&q=${encodeURIComponent(query)}` : ''}`, { headers: authHeaders })
    ])
    if (dashRes.ok) setDashboard(await dashRes.json())
    if (playersRes.ok) setPlayers(await playersRes.json())
  }

  async function sync() {
    setLoading(true); setMessage('Sincronizando com SofaScore...')
    const res = await fetch(`${API_URL}/sofascore/sync`, { method: 'POST', headers: authHeaders })
    const data = await res.json()
    setMessage(data.message || data.detail || 'Finalizado')
    setLoading(false)
    loadData()
  }

  React.useEffect(() => { loadData() }, [token])

  if (!token) {
    return <main className="min-h-screen bg-slate-950 text-white grid place-items-center p-6">
      <section className="w-full max-w-md rounded-3xl bg-white/10 border border-white/10 shadow-2xl p-8 backdrop-blur">
        <div className="flex items-center gap-3 mb-8"><div className="p-3 bg-sky-500 rounded-2xl"><ShieldCheck /></div><div><h1 className="text-2xl font-bold">Scores 2026</h1><p className="text-slate-300">Acesso seguro ao painel</p></div></div>
        {!tempToken ? <form onSubmit={login} className="space-y-4">
          <label className="block"><span>Usuário ou e-mail</span><input className="input" value={username} onChange={e => setUsername(e.target.value)} /></label>
          <label className="block"><span>Senha</span><input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>
          <button className="btn" type="submit"><Lock size={18}/> Entrar</button>
        </form> : <form onSubmit={verify2FA} className="space-y-4">
          <label className="block"><span>Código 2FA</span><input className="input tracking-widest" value={code} onChange={e => setCode(e.target.value)} /></label>
          <button className="btn" type="submit"><Smartphone size={18}/> Validar 2FA</button>
        </form>}
        {message && <p className="mt-4 text-sm text-amber-200">{message}</p>}
      </section>
    </main>
  }

  return <main className="min-h-screen bg-slate-100 text-slate-900">
    <header className="bg-slate-950 text-white px-6 py-5 sticky top-0 z-10 shadow-lg"><div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between gap-4"><div><h1 className="text-2xl font-bold">Scores 2026 Intelligence</h1><p className="text-slate-300">Dashboard SofaScore, relatórios e integração Telegram</p></div><div className="flex gap-3"><button onClick={sync} className="secondary" disabled={loading}><RefreshCw size={18}/> Sincronizar</button><button onClick={() => {localStorage.removeItem('token'); setToken('')}} className="danger">Sair</button></div></div></header>
    <section className="max-w-7xl mx-auto p-6 space-y-6">
      {message && <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-900">{message}</div>}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card icon={<Users/>} label="Times" value={dashboard?.teams ?? 0}/><Card icon={<Users/>} label="Jogadores" value={dashboard?.players ?? 0}/><Card icon={<BarChart3/>} label="Registros estatísticos" value={dashboard?.stats_rows ?? 0}/><Card icon={<ShieldCheck/>} label="Rating médio" value={dashboard?.avg_rating ?? '-'}/>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Distribuição por posição"><ResponsiveContainer width="100%" height={280}><BarChart data={dashboard?.positions || []}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="position"/><YAxis/><Tooltip/><Bar dataKey="total" fill="#0284c7" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></Panel>
        <Panel title="Top rating"><div className="space-y-3">{(dashboard?.top_rating || []).map((p, i) => <Rank key={i} i={i} name={p.name} value={p.rating}/>)}</div></Panel>
      </div>
      <Panel title="Jogadores"><div className="flex gap-2 mb-4"><div className="relative flex-1"><Search className="absolute left-3 top-3 text-slate-400" size={18}/><input className="search" placeholder="Buscar jogador" value={query} onChange={e => setQuery(e.target.value)} /></div><button className="secondary light" onClick={loadData}>Buscar</button></div><div className="overflow-x-auto"><table className="table"><thead><tr><th>Nome</th><th>Time</th><th>Posição</th><th>Nacionalidade</th><th>Idade</th></tr></thead><tbody>{players.map(p => <tr key={p.player_id}><td>{p.name}</td><td>{p.team_name || '-'}</td><td>{p.position || '-'}</td><td>{p.nationality || '-'}</td><td>{p.age || '-'}</td></tr>)}</tbody></table></div></Panel>
    </section>
  </main>
}

function Card({ icon, label, value }: { icon: React.ReactNode, label: string, value: any }) { return <div className="card"><div className="text-sky-600">{icon}</div><div><p className="text-sm text-slate-500">{label}</p><strong className="text-3xl">{value}</strong></div></div> }
function Panel({ title, children }: { title: string, children: React.ReactNode }) { return <section className="panel"><h2>{title}</h2>{children}</section> }
function Rank({ i, name, value }: { i: number, name: string, value: any }) { return <div className="rank"><span>{i+1}</span><strong>{name}</strong><em>{value}</em></div> }

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
