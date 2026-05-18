import React from 'react'
import ReactDOM from 'react-dom/client'
import { Activity, BarChart3, CalendarDays, Download, LineChart, Lock, RefreshCw, Search, ShieldCheck, Smartphone, Sparkles, Table2, Trophy, Users, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart as RLineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

type Competition = { id: number; name: string; season_id?: number; updated_at?: string }
type Dashboard = {
  meta?: { latest_data_update?: string; last_collection_finished_at?: string; last_collection_message?: string; legend?: string }
  competitions: Competition[]
  teams: number
  players: number
  stats_rows: number
  matches: number
  avg_rating: number | null
  top_goals: any[]
  top_assists: any[]
  top_rating: any[]
  positions: { position: string; total: number }[]
  standings_preview: any[]
  monthly_matches: { month: string; total: number }[]
}
type Team = { team_id: number; name: string; logo_url?: string; country?: string; updated_at?: string }
type Player = { player_id: number; name: string; team_id?: number; team_name?: string; position?: string; nationality?: string; age?: number; updated_at?: string; stats?: any }
type Match = { match_id: number; competition_name?: string; home_team?: Team; away_team?: Team; home_score?: number; away_score?: number; status?: string; start_time?: string; round_info?: string; venue?: string; updated_at?: string }
type AIResult = { scope: string; entity_id?: number | null; title: string; analysis: string; context?: Record<string, any> }

type Tab = 'visao' | 'tabelas' | 'jogadores' | 'times' | 'jogos' | 'comparar'

function App() {
  const [token, setToken] = React.useState(localStorage.getItem('token') || '')
  const [tempToken, setTempToken] = React.useState('')
  const [username, setUsername] = React.useState('admin')
  const [password, setPassword] = React.useState('')
  const [code, setCode] = React.useState('')
  const [tab, setTab] = React.useState<Tab>('visao')
  const [dashboard, setDashboard] = React.useState<Dashboard | null>(null)
  const [competitions, setCompetitions] = React.useState<Competition[]>([])
  const [teams, setTeams] = React.useState<Team[]>([])
  const [players, setPlayers] = React.useState<Player[]>([])
  const [standings, setStandings] = React.useState<any[]>([])
  const [matches, setMatches] = React.useState<Match[]>([])
  const [query, setQuery] = React.useState('')
  const [competitionId, setCompetitionId] = React.useState('')
  const [teamId, setTeamId] = React.useState('')
  const [month, setMonth] = React.useState('')
  const [sort, setSort] = React.useState('rating')
  const [message, setMessage] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [aiLoading, setAiLoading] = React.useState(false)
  const [aiResult, setAiResult] = React.useState<AIResult | null>(null)
  const [selectedTeam, setSelectedTeam] = React.useState<any | null>(null)
  const [selectedPlayer, setSelectedPlayer] = React.useState<any | null>(null)
  const [compareIds, setCompareIds] = React.useState<number[]>([])
  const [comparison, setComparison] = React.useState<Player[]>([])

  const authHeaders = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token])

  async function request(path: string, options: RequestInit = {}) {
    const res = await fetch(`${API_URL}${path}`, { ...options, headers: { ...(options.headers || {}), ...(token ? authHeaders : {}) } })
    if (res.status === 401) { localStorage.removeItem('token'); setToken(''); throw new Error('Sessão expirada') }
    const ct = res.headers.get('content-type') || ''
    const data = ct.includes('application/json') ? await res.json() : await res.text()
    if (!res.ok) throw new Error(typeof data === 'string' ? data : (data.detail || 'Falha na requisição'))
    return data
  }

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

  const loadData = React.useCallback(async () => {
    if (!token) return
    const [dash, comps, teamRows, playerRows, standingRows, matchRows] = await Promise.all([
      request(`/reports/dashboard${competitionId ? `?competition_id=${competitionId}` : ''}`),
      request('/sofascore/competitions'),
      request(`/sofascore/teams${competitionId ? `?competition_id=${competitionId}` : ''}`),
      request(`/sofascore/players?limit=300&sort=${sort}${query ? `&q=${encodeURIComponent(query)}` : ''}${competitionId ? `&competition_id=${competitionId}` : ''}${teamId ? `&team_id=${teamId}` : ''}`),
      request(`/sofascore/standings${competitionId ? `?competition_id=${competitionId}` : ''}`),
      request(`/sofascore/matches?limit=200${competitionId ? `&competition_id=${competitionId}` : ''}${teamId ? `&team_id=${teamId}` : ''}${month ? `&month=${month}` : ''}`),
    ])
    setDashboard(dash); setCompetitions(comps); setTeams(teamRows); setPlayers(playerRows); setStandings(standingRows); setMatches(matchRows)
  }, [token, competitionId, teamId, month, sort, query])

  async function sync() {
    setLoading(true); setMessage('Sincronizando SofaScore: competições, times, escudos, elencos, tabela, jogos e estatísticas disponíveis...')
    try {
      const data = await request('/sofascore/sync', { method: 'POST' })
      setMessage(data.message || data.detail || 'Sincronização finalizada')
      await loadData()
    } catch (e: any) { setMessage(e.message || 'Falha na sincronização') }
    setLoading(false)
  }

  async function openTeam(id: number) { setSelectedTeam(await request(`/sofascore/teams/${id}`)) }
  async function openPlayer(id: number) { setSelectedPlayer(await request(`/sofascore/players/${id}`)) }

  async function compare() {
    if (!compareIds.length) return
    setComparison(await request(`/sofascore/compare/players?ids=${compareIds.join(',')}`))
    setTab('comparar')
  }

  async function runAI(path: string, options: RequestInit = {}) {
    setAiLoading(true)
    setMessage('Gerando análise com IA. Aguarde alguns segundos...')
    try {
      const data = await request(path, { method: 'POST', ...options })
      setAiResult(data)
      setMessage('Análise com IA gerada com sucesso.')
    } catch (e: any) {
      setMessage(e.message || 'Falha ao gerar análise com IA')
    } finally {
      setAiLoading(false)
    }
  }

  const analyzeDashboard = () => runAI(`/ai/dashboard-insight${competitionId ? `?competition_id=${competitionId}` : ''}`)
  const analyzeTeam = (id: number) => runAI(`/ai/team/${id}`)
  const analyzePlayer = (id: number) => runAI(`/ai/player/${id}`)
  const analyzeMatch = (id: number) => runAI(`/ai/match/${id}`)
  const analyzeCompare = () => runAI('/ai/compare', { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_ids: compareIds }) })

  React.useEffect(() => { loadData().catch(err => setMessage(err.message)) }, [token])

  if (!token) {
    return <main className="min-h-screen bg-slate-950 text-white grid place-items-center p-6">
      <section className="w-full max-w-md rounded-3xl bg-white/10 border border-white/10 shadow-2xl p-8 backdrop-blur">
        <div className="flex items-center gap-3 mb-8"><div className="p-3 bg-sky-500 rounded-2xl"><ShieldCheck /></div><div><h1 className="text-2xl font-bold">Scores 2026</h1><p className="text-slate-300">Acesso seguro ao painel SofaScore</p></div></div>
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

  const latest = dashboard?.meta?.latest_data_update || dashboard?.meta?.last_collection_finished_at

  return <main className="min-h-screen bg-slate-100 text-slate-900">
    <header className="bg-slate-950 text-white px-6 py-5 sticky top-0 z-20 shadow-lg">
      <div className="max-w-7xl mx-auto flex flex-col xl:flex-row justify-between gap-4">
        <div><h1 className="text-2xl font-bold">Scores 2026 Intelligence</h1><p className="text-slate-300">Série A/B, SofaScore, ratings, tabelas, jogos, estatísticas, Telegram e IA</p><p className="text-xs text-sky-200 mt-1">Última atualização: {formatDate(latest) || 'aguardando coleta'}</p></div>
        <div className="flex flex-wrap gap-3"><button onClick={sync} className="secondary" disabled={loading}><RefreshCw size={18}/> {loading ? 'Sincronizando...' : 'Sincronizar'}</button><button onClick={analyzeDashboard} className="secondary" disabled={aiLoading}><Sparkles size={18}/> {aiLoading ? 'Analisando...' : 'Insight IA'}</button><a className="secondary muted" href={`${API_URL}/reports/players.csv`} target="_blank"><Download size={18}/> CSV</a><button onClick={() => {localStorage.removeItem('token'); setToken('')}} className="danger">Sair</button></div>
      </div>
    </header>
    <section className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
      {message && <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-900">{message}</div>}
      <Filters competitions={competitions} teams={teams} competitionId={competitionId} setCompetitionId={setCompetitionId} teamId={teamId} setTeamId={setTeamId} month={month} setMonth={setMonth} sort={sort} setSort={setSort} query={query} setQuery={setQuery} onApply={loadData}/>
      <AIInsight result={aiResult} loading={aiLoading} onClear={() => setAiResult(null)} />
      <nav className="tabs"><TabButton active={tab==='visao'} onClick={() => setTab('visao')} icon={<BarChart3 size={18}/>} label="Visão geral"/><TabButton active={tab==='tabelas'} onClick={() => setTab('tabelas')} icon={<Table2 size={18}/>} label="Séries A/B"/><TabButton active={tab==='jogadores'} onClick={() => setTab('jogadores')} icon={<Users size={18}/>} label="Jogadores"/><TabButton active={tab==='times'} onClick={() => setTab('times')} icon={<Trophy size={18}/>} label="Times"/><TabButton active={tab==='jogos'} onClick={() => setTab('jogos')} icon={<CalendarDays size={18}/>} label="Jogos"/><TabButton active={tab==='comparar'} onClick={() => setTab('comparar')} icon={<LineChart size={18}/>} label="Comparar"/></nav>
      {tab === 'visao' && <Overview dashboard={dashboard} openPlayer={openPlayer} analyzeDashboard={analyzeDashboard} aiLoading={aiLoading}/>} 
      {tab === 'tabelas' && <Standings rows={standings} openTeam={openTeam}/>} 
      {tab === 'jogadores' && <Players players={players} openPlayer={openPlayer} compareIds={compareIds} setCompareIds={setCompareIds} compare={compare} analyzePlayer={analyzePlayer}/>} 
      {tab === 'times' && <Teams teams={teams} openTeam={openTeam} analyzeTeam={analyzeTeam}/>} 
      {tab === 'jogos' && <Matches matches={matches} openTeam={openTeam} analyzeMatch={analyzeMatch}/>} 
      {tab === 'comparar' && <Comparison players={comparison} analyzeCompare={analyzeCompare} disabled={compareIds.length < 2 || aiLoading}/>} 
      <p className="legend">Legenda geral: as métricas exibidas dependem do nível de detalhe público retornado pela SofaScore para cada competição, time e atleta. Todas as datas representam a última coleta armazenada no sistema.</p>
    </section>
    {selectedTeam && <Modal title={`Time: ${selectedTeam.team?.name || ''}`} onClose={() => setSelectedTeam(null)}><TeamDetail data={selectedTeam} openPlayer={openPlayer} analyzeTeam={analyzeTeam} analyzePlayer={analyzePlayer}/></Modal>}
    {selectedPlayer && <Modal title={`Jogador: ${selectedPlayer.player?.name || ''}`} onClose={() => setSelectedPlayer(null)}><PlayerDetail data={selectedPlayer} analyzePlayer={analyzePlayer}/></Modal>}
  </main>
}

function Filters(props: any) { return <Panel title="Filtros inteligentes"><div className="filters"><label>Competição<select value={props.competitionId} onChange={(e) => props.setCompetitionId(e.target.value)}><option value="">Todas</option>{props.competitions.map((c: Competition) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label><label>Time<select value={props.teamId} onChange={(e) => props.setTeamId(e.target.value)}><option value="">Todos</option>{props.teams.map((t: Team) => <option key={t.team_id} value={t.team_id}>{t.name}</option>)}</select></label><label>Mês<input type="month" value={props.month} onChange={(e) => props.setMonth(e.target.value)} /></label><label>Ordenar jogadores<select value={props.sort} onChange={(e) => props.setSort(e.target.value)}><option value="rating">Rating médio</option><option value="goals">Gols</option><option value="assists">Assistências</option><option value="matches">Jogos</option><option value="age">Idade</option><option value="name">Nome</option></select></label><label className="grow">Busca<input placeholder="Jogador ou time" value={props.query} onChange={(e) => props.setQuery(e.target.value)} /></label><button className="secondary light" onClick={props.onApply}><Search size={18}/> Aplicar</button></div></Panel> }

function AIInsight({ result, loading, onClear }: { result: AIResult | null; loading: boolean; onClear: () => void }) {
  if (!result && !loading) return null
  return <Panel title="Análise com IA">
    {loading && <p className="chart-legend">A IA está cruzando ratings, gols, assistências, tabela classificatória e últimos resultados...</p>}
    {result && <div className="ai-box"><div className="toolbar"><strong><Sparkles size={18}/> {result.title}</strong><button className="secondary light" onClick={onClear}>Limpar análise</button></div><pre>{result.analysis}</pre></div>}
  </Panel>
}

function Overview({ dashboard, openPlayer, analyzeDashboard, aiLoading }: any) { return <div className="space-y-6"><div className="toolbar"><span className="small">Visão consolidada do banco SofaScore.</span><button className="secondary light" onClick={analyzeDashboard} disabled={aiLoading}><Sparkles size={18}/> Analisar dashboard com IA</button></div><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"><Card icon={<Trophy/>} label="Times" value={dashboard?.teams ?? 0}/><Card icon={<Users/>} label="Jogadores" value={dashboard?.players ?? 0}/><Card icon={<Activity/>} label="Jogos" value={dashboard?.matches ?? 0}/><Card icon={<BarChart3/>} label="Registros" value={dashboard?.stats_rows ?? 0}/><Card icon={<ShieldCheck/>} label="Rating médio" value={dashboard?.avg_rating ?? '-'}/></div><div className="grid grid-cols-1 xl:grid-cols-2 gap-6"><Panel title="Distribuição por posição"><ChartLegend text="Mostra a quantidade de atletas por posição cadastrada."/><ResponsiveContainer width="100%" height={300}><BarChart data={dashboard?.positions || []}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="position"/><YAxis/><Tooltip/><Legend/><Bar name="Total de jogadores" dataKey="total" fill="#0284c7" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></Panel><Panel title="Jogos por mês"><ChartLegend text="Quantidade de partidas coletadas por mês."/><ResponsiveContainer width="100%" height={300}><RLineChart data={dashboard?.monthly_matches || []}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="month"/><YAxis/><Tooltip/><Legend/><Line name="Jogos" type="monotone" dataKey="total" stroke="#0f172a" strokeWidth={3}/></RLineChart></ResponsiveContainer></Panel></div><div className="grid grid-cols-1 lg:grid-cols-3 gap-6"><Ranking title="Top rating" rows={dashboard?.top_rating || []} field="rating" openPlayer={openPlayer}/><Ranking title="Top gols" rows={dashboard?.top_goals || []} field="goals" openPlayer={openPlayer}/><Ranking title="Top assistências" rows={dashboard?.top_assists || []} field="assists" openPlayer={openPlayer}/></div><Panel title="Metadados da coleta"><p>{dashboard?.meta?.legend}</p><p className="small">Última mensagem: {dashboard?.meta?.last_collection_message || '-'}</p></Panel></div> }
function Standings({ rows, openTeam }: any) { return <Panel title="Tabela atualizada: Série A e Série B"><ChartLegend text="Clique no time para abrir elenco, jogos, posição, forma e rating médio."/><div className="overflow-x-auto"><table className="table"><thead><tr><th>Pos.</th><th>Time</th><th>Competição</th><th>J</th><th>V</th><th>E</th><th>D</th><th>GP</th><th>GC</th><th>SG</th><th>Pts</th><th>Forma</th><th>Atualizado</th></tr></thead><tbody>{rows.map((r: any, i: number) => <tr key={i}><td>{r.position}</td><td><button className="link team-cell" onClick={() => openTeam(r.team.team_id)}><Logo src={r.team.logo_url}/>{r.team.name}</button></td><td>{r.competition_name}</td><td>{r.matches ?? '-'}</td><td>{r.wins ?? '-'}</td><td>{r.draws ?? '-'}</td><td>{r.losses ?? '-'}</td><td>{r.scores_for ?? '-'}</td><td>{r.scores_against ?? '-'}</td><td>{r.score_diff ?? '-'}</td><td><strong>{r.points ?? '-'}</strong></td><td>{r.form || '-'}</td><td>{formatDate(r.updated_at)}</td></tr>)}</tbody></table></div></Panel> }
function Players({ players, openPlayer, compareIds, setCompareIds, compare, analyzePlayer }: any) { const toggle=(id:number)=>setCompareIds((ids:number[])=>ids.includes(id)?ids.filter(x=>x!==id):[...ids,id].slice(-4)); return <Panel title="Jogadores e registros específicos"><div className="toolbar"><span className="small">Selecione até 4 jogadores e clique em comparar.</span><button className="secondary light" onClick={compare}>Comparar selecionados</button></div><div className="overflow-x-auto"><table className="table"><thead><tr><th>Comparar</th><th>Nome</th><th>Time</th><th>Posição</th><th>Rating</th><th>Jogos</th><th>Gols</th><th>Assist.</th><th>Nac.</th><th>Idade</th><th>IA</th><th>Atualizado</th></tr></thead><tbody>{players.map((p: Player) => <tr key={p.player_id}><td><input type="checkbox" checked={compareIds.includes(p.player_id)} onChange={() => toggle(p.player_id)}/></td><td><button className="link" onClick={() => openPlayer(p.player_id)}>{p.name}</button></td><td>{p.team_name || '-'}</td><td>{p.position || '-'}</td><td>{p.stats?.rating ?? '-'}</td><td>{p.stats?.matches ?? '-'}</td><td>{p.stats?.goals ?? '-'}</td><td>{p.stats?.assists ?? '-'}</td><td>{p.nationality || '-'}</td><td>{p.age || '-'}</td><td><button className="link" onClick={() => analyzePlayer(p.player_id)}>Analisar</button></td><td>{formatDate(p.updated_at)}</td></tr>)}</tbody></table></div></Panel> }
function Teams({ teams, openTeam, analyzeTeam }: any) { return <Panel title="Times clicáveis"><div className="team-grid">{teams.map((t: Team) => <div className="team-card" key={t.team_id}><button className="team-card-main" onClick={() => openTeam(t.team_id)}><Logo src={t.logo_url}/><strong>{t.name}</strong><span>{t.country || 'Brasil'}</span><small>Atualizado: {formatDate(t.updated_at)}</small></button><button className="secondary light" onClick={() => analyzeTeam(t.team_id)}><Sparkles size={16}/> Analisar com IA</button></div>)}</div></Panel> }
function Matches({ matches, openTeam, analyzeMatch }: any) { return <Panel title="Jogos, últimos resultados e calendário"><ChartLegend text="Use os filtros de competição, time e mês para analisar recortes específicos."/><div className="match-list">{matches.map((m: Match) => <div className="match" key={m.match_id}><span>{formatDate(m.start_time)}</span><strong>{m.competition_name || '-'}</strong><div><button className="link team-cell" onClick={() => m.home_team && openTeam(m.home_team.team_id)}><Logo src={m.home_team?.logo_url}/>{m.home_team?.name}</button><b>{m.home_score ?? '-'}</b><span>x</span><b>{m.away_score ?? '-'}</b><button className="link team-cell" onClick={() => m.away_team && openTeam(m.away_team.team_id)}><Logo src={m.away_team?.logo_url}/>{m.away_team?.name}</button></div><small>{m.status || '-'} · {m.round_info || ''} · {m.venue || ''}</small><button className="secondary light" onClick={() => analyzeMatch(m.match_id)}><Sparkles size={16}/> Analisar jogo com IA</button></div>)}</div></Panel> }
function Comparison({ players, analyzeCompare, disabled }: any) { const data = players.map((p: Player) => ({ name: p.name, rating: p.stats?.rating || 0, gols: p.stats?.goals || 0, assistencias: p.stats?.assists || 0, jogos: p.stats?.matches || 0 })); return <Panel title="Comparação de jogadores"><div className="toolbar"><ChartLegend text="Compare rating médio, gols, assistências e jogos dos atletas selecionados."/><button className="secondary light" onClick={analyzeCompare} disabled={disabled}><Sparkles size={18}/> Comparar com IA</button></div><ResponsiveContainer width="100%" height={320}><BarChart data={data}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis/><Tooltip/><Legend/><Bar dataKey="rating" name="Rating" fill="#0284c7"/><Bar dataKey="gols" name="Gols" fill="#16a34a"/><Bar dataKey="assistencias" name="Assistências" fill="#f59e0b"/><Bar dataKey="jogos" name="Jogos" fill="#64748b"/></BarChart></ResponsiveContainer></Panel> }
function TeamDetail({ data, openPlayer, analyzeTeam, analyzePlayer }: any) { return <div className="space-y-4"><div className="flex items-center gap-3"><Logo src={data.team?.logo_url}/><div><h3>{data.team?.name}</h3><p>Rating médio do elenco: <strong>{data.avg_rating ?? '-'}</strong></p></div></div><button className="secondary light" onClick={() => data.team?.team_id && analyzeTeam(data.team.team_id)}><Sparkles size={18}/> Analisar time com IA</button><Standings rows={(data.standings || []).map((s:any)=>({...s, team:data.team, competition_name:s.competition_name}))} openTeam={()=>{}}/><Players players={data.players || []} openPlayer={openPlayer} compareIds={[]} setCompareIds={()=>{}} compare={()=>{}} analyzePlayer={analyzePlayer}/><Matches matches={data.matches || []} openTeam={()=>{}} analyzeMatch={()=>{}}/></div> }
function PlayerDetail({ data, analyzePlayer }: any) { const p=data.player; const s=p?.stats; return <div className="space-y-4"><button className="secondary light" onClick={() => p?.player_id && analyzePlayer(p.player_id)}><Sparkles size={18}/> Analisar jogador com IA</button><div className="detail-grid"><Info label="Time" value={p?.team_name}/><Info label="Posição" value={p?.position}/><Info label="Nacionalidade" value={p?.nationality}/><Info label="Idade" value={p?.age}/><Info label="Pé preferido" value={p?.preferred_foot}/><Info label="Altura" value={p?.height}/><Info label="Rating médio" value={s?.rating}/><Info label="Jogos" value={s?.matches}/><Info label="Titular" value={s?.starts}/><Info label="Minutos" value={s?.minutes}/><Info label="Gols" value={s?.goals}/><Info label="Assistências" value={s?.assists}/><Info label="Finalizações" value={s?.shots}/><Info label="Passes-chave" value={s?.key_passes}/><Info label="Desarmes" value={s?.tackles}/><Info label="Defesas" value={s?.saves}/><Info label="Atualizado" value={formatDate(p?.updated_at)}/></div></div> }
function Ranking({ title, rows, field, openPlayer }: any) { return <Panel title={title}><div className="space-y-3">{rows.map((p:any, i:number) => <button className="rank" key={p.player_id || i} onClick={() => p.player_id && openPlayer(p.player_id)}><span>{i+1}</span><strong>{p.name}<small>{p.team}</small></strong><em>{p[field] ?? '-'}</em></button>)}</div></Panel> }
function Card({ icon, label, value }: { icon: React.ReactNode, label: string, value: any }) { return <div className="card"><div className="text-sky-600">{icon}</div><div><p className="text-sm text-slate-500">{label}</p><strong className="text-3xl">{value}</strong></div></div> }
function Panel({ title, children }: { title: string, children: React.ReactNode }) { return <section className="panel"><h2>{title}</h2>{children}</section> }
function TabButton({active,onClick,icon,label}: any){return <button className={active?'tab active':'tab'} onClick={onClick}>{icon}{label}</button>}
function ChartLegend({text}:{text:string}){return <p className="chart-legend">Legenda: {text}</p>}
function Logo({src}:{src?:string}){return src?<img className="logo" src={src} loading="lazy"/>:<span className="logo placeholder">?</span>}
function Info({label,value}:any){return <div className="info"><span>{label}</span><strong>{value ?? '-'}</strong></div>}
function Modal({title,children,onClose}: any){return <div className="modal-bg"><div className="modal"><header><h2>{title}</h2><button onClick={onClose}><X/></button></header>{children}</div></div>}
function formatDate(value?: string){ if(!value) return ''; try { return new Intl.DateTimeFormat('pt-BR',{dateStyle:'short', timeStyle:'short'}).format(new Date(value)) } catch { return value } }

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
