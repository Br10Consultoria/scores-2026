import React from 'react'
import ReactDOM from 'react-dom/client'
import { Activity, ArrowLeft, BarChart3, CalendarDays, Home, LineChart, Lock, RefreshCw, Search, ShieldCheck, Smartphone, Sparkles, Table2, Trophy, Users, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart as RLineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'
import LeagueAnalytics from './LeagueAnalytics'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

type Competition = { id: number; name: string; season_id?: number; updated_at?: string; teams_count?: number }
type Dashboard = {
  meta?: { latest_data_update?: string; last_collection_finished_at?: string; last_collection_message?: string; legend?: string; sources?: string[]; source_warning?: boolean; player_stats_available?: boolean; finished_matches?: number; scheduled_matches?: number }
  competitions: Competition[]
  teams: number
  players: number
  stats_rows: number
  matches: number
  finished_matches: number
  scheduled_matches: number
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

type Tab = 'visao' | 'tabelas' | 'jogadores' | 'times' | 'jogos' | 'comparar' | 'analises'

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
  const [position, setPosition] = React.useState('')
  const [month, setMonth] = React.useState('')
  const [sort, setSort] = React.useState('rating')
  const [message, setMessage] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [syncStart, setSyncStart] = React.useState<number|null>(null)
  const [aiLoading, setAiLoading] = React.useState(false)
  const [aiResult, setAiResult] = React.useState<AIResult | null>(null)
  const [selectedTeam, setSelectedTeam] = React.useState<any | null>(null)
  const [selectedPlayer, setSelectedPlayer] = React.useState<any | null>(null)
  const [compareIds, setCompareIds] = React.useState<number[]>([])
  const [comparison, setComparison] = React.useState<Player[]>([])
  const [compareTeamIds, setCompareTeamIds] = React.useState<number[]>([])
  const [teamComparison, setTeamComparison] = React.useState<any[]>([])

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
      request(`/sofascore/players?limit=300&sort=${sort}${query ? `&q=${encodeURIComponent(query)}` : ''}${competitionId ? `&competition_id=${competitionId}` : ''}${teamId ? `&team_id=${teamId}` : ''}${position ? `&position=${encodeURIComponent(position)}` : ''}`),
      request(`/sofascore/standings${competitionId ? `?competition_id=${competitionId}` : ''}`),
      request(`/sofascore/matches?limit=200${competitionId ? `&competition_id=${competitionId}` : ''}${teamId ? `&team_id=${teamId}` : ''}${month ? `&month=${encodeURIComponent(month)}` : ''}`),
    ])
    setDashboard(dash); setCompetitions(comps); setTeams(teamRows); setPlayers(playerRows); setStandings(standingRows); setMatches(matchRows)
  }, [token, competitionId, teamId, position, month, sort, query])

  async function sync() {
    setLoading(true); setMessage('Coletando dados das fontes configuradas. O processamento continua em segundo plano...')
    try {
      const data = await request('/sofascore/sync', { method: 'POST' })
      setMessage(data.message || data.detail || 'Sincronização iniciada')
      if (data.status === 'accepted' || data.status === 'running') {
        setSyncStart(Date.now())
      } else {
        await loadData()
      }
    } catch (e: any) { setMessage(e.message || 'Falha na sincronização') }
    setLoading(false)
  }

  function changeTab(next: Tab) {
    setTab(next)
    setSelectedTeam(null)
    setSelectedPlayer(null)
  }

  function goHome() {
    setSelectedTeam(null)
    setSelectedPlayer(null)
    setTab('visao')
  }

  async function openTeam(id: number) { setSelectedPlayer(null); setSelectedTeam(await request(`/sofascore/teams/${id}`)) }
  async function openPlayer(id: number) { setSelectedTeam(null); setSelectedPlayer(await request(`/sofascore/players/${id}${competitionId ? `?competition_id=${competitionId}` : ''}`)) }

  async function compare() {
    if (compareIds.length < 2) return
    setComparison(await request(`/sofascore/compare/players?ids=${compareIds.join(',')}${competitionId ? `&competition_id=${competitionId}` : ''}`))
    changeTab('comparar')
  }

  async function compareSelectedTeams(ids = compareTeamIds) {
    if (ids.length < 2) return
    setTeamComparison(await request(`/sofascore/compare/teams?ids=${ids.join(',')}${competitionId ? `&competition_id=${competitionId}` : ''}`))
    changeTab('comparar')
  }

  async function runAI(path: string, options: RequestInit = {}) {
    setAiLoading(true)
    setMessage('Gerando análise com IA. Aguarde alguns segundos...')
    try {
      const data = await request(path, { method: 'POST', ...options })
      setAiResult(data)
      setMessage('Análise com IA gerada com sucesso.')
    } catch (e: any) {
      const text = e.message || 'Falha ao gerar análise com IA'
      setMessage(text.includes('OPENAI_API_KEY') ? `${text} No servidor, rode: docker compose up -d --build backend` : text)
    } finally {
      setAiLoading(false)
    }
  }

  const analyzeTeam = (id: number) => runAI(`/ai/team/${id}`)
  const analyzePlayer = (id: number) => runAI(`/ai/player/${id}`)
  const analyzeMatch = (id: number) => runAI(`/ai/match/${id}`)
  const analyzeCompare = () => runAI('/ai/compare', { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_ids: compareIds }) })

  React.useEffect(() => { loadData().catch(err => setMessage(err.message)) }, [token])

  // A sincronização é assíncrona. Evita anunciar "concluído" enquanto o
  // coletor ainda está gravando dados no PostgreSQL.
  React.useEffect(() => {
    if (!token || syncStart === null) return
    let active = true
    let attempts = 0
    const timer = window.setInterval(async () => {
      attempts += 1
      try {
        const dash = await request('/reports/dashboard')
        if (!active) return
        const meta = dash?.meta
        const started = meta?.last_collection_started_at ? new Date(meta.last_collection_started_at).getTime() : 0
        if (meta?.last_collection_status === 'running') {
          setMessage('Coleta em andamento. ' + collectionSummary(meta?.last_collection_message, dash))
        } else if (started + 5000 >= syncStart && meta?.last_collection_status) {
          setSyncStart(null)
          setMessage(collectionSummary(meta?.last_collection_message, dash))
          await loadData()
        }
        if (attempts >= 180) {
          setSyncStart(null)
          setMessage('A coleta continua no servidor ou excedeu o tempo de acompanhamento. Verifique o status nos logs.')
        }
      } catch (error) {
        if (active) setMessage(error instanceof Error ? error.message : 'Falha ao consultar status de coleta.')
      }
    }, 10000)
    return () => { active = false; window.clearInterval(timer) }
  }, [token, syncStart])

  if (!token) {
    return <main className="login-screen">
      <section className="login-card">
        <div className="login-brand"><div className="login-icon"><ShieldCheck size={18}/></div><div><h1>Scores 2026</h1><p>Acesso seguro ao painel SofaScore</p></div></div>
        {!tempToken ? <form onSubmit={login} className="compact-form">
          <label className="block"><span>Usuário ou e-mail</span><input className="input" value={username} onChange={e => setUsername(e.target.value)} /></label>
          <label className="block"><span>Senha</span><input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>
          <button className="btn" type="submit"><Lock size={16}/> Entrar</button>
        </form> : <form onSubmit={verify2FA} className="compact-form">
          <label className="block"><span>Código 2FA</span><input className="input tracking-widest" value={code} onChange={e => setCode(e.target.value)} /></label>
          <button className="btn" type="submit"><Smartphone size={16}/> Validar 2FA</button>
        </form>}
        {message && <p className="mt-4 text-sm text-amber-200">{message}</p>}
      </section>
    </main>
  }

  const latest = dashboard?.meta?.latest_data_update || dashboard?.meta?.last_collection_finished_at

  return <main className="min-h-screen bg-slate-100 text-slate-900">
    <header className="app-header">
      <div className="header-inner">
        <div className="header-title"><h1>Scores 2026 Intelligence</h1><p>Séries A/B, Copa do Brasil, Copa do Mundo e SofaScore</p><p>Última atualização: {formatDate(latest) || 'aguardando coleta'}</p></div>
        <div className="header-actions"><button type="button" onClick={goHome} className="secondary muted"><Home size={16}/> Home</button><button type="button" onClick={sync} className="secondary" disabled={loading}><RefreshCw size={16}/> {loading ? 'Sincronizando...' : 'Sincronizar'}</button><button type="button" onClick={() => {localStorage.removeItem('token'); setToken('')}} className="danger">Sair</button></div>
      </div>
    </header>
    <section className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
      {message && <div className="collection-flash"><span>{collectionSummary(message,dashboard)}</span><button type="button" onClick={() => setMessage('')} aria-label="Dispensar aviso"><X size={16}/></button></div>}
      <Filters competitions={competitions} teams={teams} positions={dashboard?.positions || []} competitionId={competitionId} setCompetitionId={setCompetitionId} teamId={teamId} setTeamId={setTeamId} position={position} setPosition={setPosition} month={month} setMonth={setMonth} sort={sort} setSort={setSort} query={query} setQuery={setQuery} onApply={loadData}/>
      <AIInsight result={aiResult} loading={aiLoading} onClear={() => setAiResult(null)} />
      <nav className="tabs"><TabButton active={tab==='visao'} onClick={() => changeTab('visao')} icon={<BarChart3 size={18}/>} label="Visão geral"/><TabButton active={tab==='tabelas'} onClick={() => changeTab('tabelas')} icon={<Table2 size={18}/>} label="Tabelas"/><TabButton active={tab==='jogadores'} onClick={() => changeTab('jogadores')} icon={<Users size={18}/>} label="Jogadores"/><TabButton active={tab==='times'} onClick={() => changeTab('times')} icon={<Trophy size={18}/>} label="Times"/><TabButton active={tab==='jogos'} onClick={() => changeTab('jogos')} icon={<CalendarDays size={18}/>} label="Jogos"/><TabButton active={tab==='comparar'} onClick={() => changeTab('comparar')} icon={<LineChart size={18}/>} label="Comparar"/><TabButton active={tab==='analises'} onClick={() => changeTab('analises')} icon={<Trophy size={18}/>} label="Projeções Brasileirão"/></nav>
      {tab === 'visao' && <Overview dashboard={dashboard} openPlayer={openPlayer} openProjections={() => changeTab('analises')}/>} 
      {tab === 'tabelas' && <Standings rows={standings} openTeam={openTeam}/>} 
      {tab === 'jogadores' && <Players players={players} openPlayer={openPlayer} compareIds={compareIds} setCompareIds={setCompareIds} compare={compare} analyzePlayer={analyzePlayer}/>} 
      {tab === 'times' && <Teams teams={teams} openTeam={openTeam} analyzeTeam={analyzeTeam}/>} 
      {tab === 'jogos' && <Matches matches={matches} openTeam={openTeam} analyzeMatch={analyzeMatch}/>} 
      {tab === 'analises' && <LeagueAnalytics token={token} apiUrl={API_URL}/>}
      {tab === 'comparar' && <Comparison players={comparison} availablePlayers={players} teams={teams} teamComparison={teamComparison} compareIds={compareIds} setCompareIds={setCompareIds} compare={compare} compareTeamIds={compareTeamIds} setCompareTeamIds={setCompareTeamIds} compareTeams={compareSelectedTeams} analyzeCompare={analyzeCompare} disabled={compareIds.length < 2 || aiLoading}/>} 
      <p className="legend">Legenda geral: as métricas exibidas dependem do nível de detalhe público retornado pela SofaScore para cada competição, time e atleta. Todas as datas são exibidas no fuso local do navegador a partir de timestamps UTC do backend.</p>
    </section>
    {selectedTeam && <Modal title={`Time: ${selectedTeam.team?.name || ''}`} onClose={() => setSelectedTeam(null)}><TeamDetail data={selectedTeam} openTeam={openTeam} openPlayer={openPlayer} analyzeTeam={analyzeTeam} analyzePlayer={analyzePlayer} analyzeMatch={analyzeMatch}/></Modal>}
    {selectedPlayer && <Modal title={`Jogador: ${selectedPlayer.player?.name || ''}`} onClose={() => setSelectedPlayer(null)}><PlayerDetail data={selectedPlayer} analyzePlayer={analyzePlayer}/></Modal>}
  </main>
}

function Filters(props: any) { return <Panel title="Filtros inteligentes"><div className="filters"><label>Competição<select value={props.competitionId} onChange={(e) => props.setCompetitionId(e.target.value)}><option value="">Todas</option>{props.competitions.map((c: Competition) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label><label>Time<select value={props.teamId} onChange={(e) => props.setTeamId(e.target.value)}><option value="">Todos</option>{props.teams.map((t: Team) => <option key={t.team_id} value={t.team_id}>{t.name}</option>)}</select></label><label>Posição<select value={props.position} onChange={(e) => props.setPosition(e.target.value)}><option value="">Todas</option>{props.positions.map((p: any) => <option key={p.position || 'sem-posicao'} value={p.position}>{p.position || 'Sem posição'}</option>)}</select></label><label>Mês<input type="month" value={props.month} onChange={(e) => props.setMonth(e.target.value)} /></label><label>Ordenar jogadores<select value={props.sort} onChange={(e) => props.setSort(e.target.value)}><option value="rating">Maior score/rating</option><option value="name">Nome</option><option value="goals">Mais gols</option><option value="assists">Mais assistências</option><option value="matches">Mais jogos</option><option value="shots">Mais finalizações</option><option value="shots_on_target">Finalizações no alvo</option><option value="key_passes">Passes-chave</option><option value="big_chances_created">Grandes chances criadas</option><option value="penalty_goals">Gols de pênalti</option><option value="headed_goals">Gols de cabeça</option><option value="free_kick_goals">Gols de falta</option><option value="age">Idade</option></select></label><label className="grow">Busca<input placeholder="Jogador ou time" value={props.query} onChange={(e) => props.setQuery(e.target.value)} /></label><button className="secondary light" onClick={props.onApply}><Search size={18}/> Aplicar</button></div></Panel> }

function AIInsight({ result, loading, onClear }: { result: AIResult | null; loading: boolean; onClear: () => void }) {
  if (!result && !loading) return null
  return <Panel title="Análise com IA">
    {loading && <p className="chart-legend">A IA está cruzando ratings, gols, assistências, tabela classificatória e últimos resultados...</p>}
    {result && <div className="ai-box"><div className="toolbar"><strong><Sparkles size={18}/> {result.title}</strong><button className="secondary light" onClick={onClear}>Limpar análise</button></div><pre>{result.analysis}</pre></div>}
  </Panel>
}

function collectionSummary(raw?: string, dashboard?: Dashboard | null) {
  if (!raw) return 'Aguardando primeira sincronização.'
  const unavailable = /403 Forbidden|retornou 403|SofaScore.*403/i.test(raw)
  const hasSerieA = (dashboard?.meta?.sources||[]).includes('football-data.org')
  if (unavailable) {
    return hasSerieA
      ? 'Sincronização parcial: Série A importada pela football-data.org. Dados de jogadores e outras competições ainda indisponíveis porque a SofaScore recusou o acesso (HTTP 403).'
      : 'Sincronização parcial: a SofaScore recusou o acesso (HTTP 403). Verifique as fontes de dados; não há estatísticas individuais disponíveis nesta coleta.'
  }
  // A mensagem completa permanece auditável nos logs da aplicação.
  return raw.split(' Avisos:')[0].slice(0, 350)
}

function EmptyData({ label }: {label:string}) {
  return <div className="empty-data">
    <Activity size={22}/>
    <strong>{label}</strong>
    <p>Este gráfico será preenchido quando houver estatísticas de jogadores disponíveis na fonte configurada.</p>
  </div>
}

function Overview({ dashboard, openPlayer, openProjections }: { dashboard:Dashboard|null; openPlayer:(id:number)=>void;openProjections:()=>void }) {
  const comps=(dashboard?.competitions||[]).filter(c=>(c.teams_count||0)>0)
  const coverage=comps.map(c=>`${c.name}: ${c.teams_count} clubes`).join(' · ')
  const sources=dashboard?.meta?.sources||[]
  const hasPlayers=(dashboard?.players||0)>0
  const hasStats=(dashboard?.stats_rows||0)>0
  const hasForbidden=/403 Forbidden|retornou 403/i.test(dashboard?.meta?.last_collection_message||'')
  return <div className="space-y-6">
    <div className="overview-intro">
      <div><strong>Visão geral das competições</strong><p>{coverage||'Aguardando competições e partidas da primeira coleta.'}</p></div>
      <button type="button" className="secondary light" onClick={openProjections}><Trophy size={16}/> Ver projeções e vagas</button>
    </div>
    <div className="source-status">
      <div><span className="source-status-icon"><Activity size={18}/></span><div>
        <strong>{dashboard?.matches ? 'Calendário importado' : 'Aguardando calendário'}</strong>
        <p>Origem: {sources.length ? sources.join(' + ') : 'sem dados'}. Os jogos disponíveis incluem partidas futuras.</p>
      </div></div>
      <div><span className="source-status-icon muted"><Users size={18}/></span><div>
        <strong>{hasStats?'Estatísticas individuais disponíveis':'Estatísticas individuais indisponíveis'}</strong>
        <p>{hasStats ? 'Ratings, gols e assistências carregados conforme cobertura da fonte.' : hasForbidden ? 'A SofaScore retornou HTTP 403; a football-data.org não fornece esses dados no coletor atual.' : 'Ainda não há estatísticas individuais coletadas para este filtro.'}</p>
      </div></div>
    </div>
    <div className="dashboard-cards">
      <Card icon={<Trophy/>} label="Times coletados" value={dashboard?.teams ?? 0}/>
      <Card icon={<Activity/>} label="Jogos realizados" value={dashboard?.finished_matches ?? 0}/>
      <Card icon={<CalendarDays/>} label="Jogos não finalizados" value={dashboard?.scheduled_matches ?? 0}/>
      <Card icon={<Users/>} label="Jogadores" value={dashboard?.players ?? 0}/>
      <Card icon={<BarChart3/>} label="Estatísticas de atletas" value={dashboard?.stats_rows ?? 0}/>
    </div>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <Panel title="Distribuição por posição">
        {hasPlayers && dashboard?.positions?.length
          ? <><ChartLegend text="Quantidade de atletas por posição cadastrada."/><ResponsiveContainer width="100%" height={280}><BarChart data={dashboard.positions}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="position"/><YAxis/><Tooltip/><Legend/><Bar name="Total de jogadores" dataKey="total" fill="#0284c7" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></>
          : <EmptyData label="Nenhum elenco coletado"/>}
      </Panel>
      <Panel title="Partidas por mês">
        {dashboard?.monthly_matches?.length
          ? <><ChartLegend text="Quantidade de jogos cadastrados por mês, incluindo jogos futuros."/><ResponsiveContainer width="100%" height={280}><RLineChart data={dashboard.monthly_matches}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="month"/><YAxis/><Tooltip/><Legend/><Line name="Partidas no calendário" type="monotone" dataKey="total" stroke="#0f172a" strokeWidth={3}/></RLineChart></ResponsiveContainer></>
          : <EmptyData label="Calendário ainda indisponível"/>}
      </Panel>
    </div>
    {hasStats ? <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Ranking title="Top rating" rows={dashboard?.top_rating||[]} field="rating" openPlayer={openPlayer}/>
      <Ranking title="Top gols" rows={dashboard?.top_goals||[]} field="goals" openPlayer={openPlayer}/>
      <Ranking title="Top assistências" rows={dashboard?.top_assists||[]} field="assists" openPlayer={openPlayer}/>
    </div> : <div className="overview-unavailable">
      <Users size={20}/><div><strong>Rankings de artilharia, assistências e rating aguardando fonte de atletas</strong>
      <p>Os rankings não devem exibir zeros como se fossem dados reais. Classificação, gols dos clubes e projeções do Brasileirão continuam disponíveis.</p></div>
    </div>}
    <Panel title="Estado da última coleta">
      <p>{dashboard?.meta?.legend}</p>
      <p className="small">{collectionSummary(dashboard?.meta?.last_collection_message,dashboard)}</p>
    </Panel>
  </div>
}

function Standings({ rows, openTeam }: any) { return <Panel title="Tabelas disponíveis: Séries A/B e Copa do Mundo"><ChartLegend text="Competições sem standings, como a Copa do Brasil, aparecem principalmente em Jogos e Times. Clique no time para abrir elenco, jogos, posição, forma e rating médio."/><div className="overflow-x-auto"><table className="table"><thead><tr><th>Pos.</th><th>Time</th><th>Competição</th><th>J</th><th>V</th><th>E</th><th>D</th><th>GP</th><th>GC</th><th>SG</th><th>Pts</th><th>Forma</th><th>Atualizado</th></tr></thead><tbody>{rows.map((r: any, i: number) => <tr key={i}><td>{r.position}</td><td><button className="link team-cell" onClick={() => openTeam(r.team.team_id)}><Logo src={r.team.logo_url}/>{r.team.name}</button></td><td>{r.competition_name}</td><td>{r.matches ?? '-'}</td><td>{r.wins ?? '-'}</td><td>{r.draws ?? '-'}</td><td>{r.losses ?? '-'}</td><td>{r.scores_for ?? '-'}</td><td>{r.scores_against ?? '-'}</td><td>{r.score_diff ?? '-'}</td><td><strong>{r.points ?? '-'}</strong></td><td>{r.form || '-'}</td><td>{formatDate(r.updated_at)}</td></tr>)}</tbody></table></div></Panel> }
function Players({ players, openPlayer, compareIds, setCompareIds, compare, analyzePlayer }: any) {
  const toggle = (id: number) => setCompareIds((ids: number[]) => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id].slice(-4))
  const selectedCount = compareIds.length
  return <Panel title="Jogadores e registros específicos"><div className="toolbar"><span className="small">Selecione até 4 jogadores clicando na linha, no checkbox ou no nome do atleta.</span><button className="secondary light" onClick={(e) => { e.stopPropagation(); compare() }} disabled={selectedCount < 2}>Comparar selecionados{selectedCount ? ` (${selectedCount})` : ''}</button></div><div className="overflow-x-auto"><table className="table"><thead><tr><th>Comparar</th><th>Nome</th><th>Time</th><th>Posição</th><th>Rating</th><th>Jogos</th><th>Gols</th><th>Assist.</th><th>Nac.</th><th>Idade</th><th>IA</th><th>Atualizado</th></tr></thead><tbody>{players.map((p: Player) => { const checked = compareIds.includes(p.player_id); return <tr key={p.player_id} className={checked ? 'selectable-row selected' : 'selectable-row'} onClick={() => toggle(p.player_id)}><td><label className="checkbox-hit" onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={checked} onChange={() => toggle(p.player_id)} /><span>{checked ? 'Selecionado' : 'Selecionar'}</span></label></td><td><button className="link" onClick={(e) => { e.stopPropagation(); openPlayer(p.player_id) }}>{p.name}</button></td><td>{p.team_name || '-'}</td><td>{p.position || '-'}</td><td>{p.stats?.rating ?? '-'}</td><td>{p.stats?.matches ?? '-'}</td><td>{p.stats?.goals ?? '-'}</td><td>{p.stats?.assists ?? '-'}</td><td>{p.nationality || '-'}</td><td>{p.age || '-'}</td><td><button className="link" onClick={(e) => { e.stopPropagation(); analyzePlayer(p.player_id) }}>Analisar</button></td><td>{formatDate(p.updated_at)}</td></tr> })}</tbody></table></div></Panel>
}
function Teams({ teams, openTeam, analyzeTeam }: any) { return <Panel title="Times clicáveis"><div className="team-grid">{teams.map((t: Team) => <div className="team-card" key={t.team_id}><button className="team-card-main" onClick={() => openTeam(t.team_id)}><Logo src={t.logo_url}/><strong>{t.name}</strong><span>{t.country || 'Brasil'}</span><small>Atualizado: {formatDate(t.updated_at)}</small></button><button className="secondary light" onClick={() => analyzeTeam(t.team_id)}><Sparkles size={16}/> Analisar com IA</button></div>)}</div></Panel> }
function Matches({ matches, openTeam, analyzeMatch }: any) { return <Panel title="Jogos, últimos resultados e calendário"><ChartLegend text="Use os filtros de competição, time e mês para analisar recortes específicos."/><div className="match-list">{matches.map((m: Match) => <div className="match" key={m.match_id}><span>{formatDate(m.start_time)}</span><strong>{m.competition_name || '-'}</strong><div><button className="link team-cell" onClick={() => m.home_team && openTeam(m.home_team.team_id)}><Logo src={m.home_team?.logo_url}/>{m.home_team?.name}</button><b>{m.home_score ?? '-'}</b><span>x</span><b>{m.away_score ?? '-'}</b><button className="link team-cell" onClick={() => m.away_team && openTeam(m.away_team.team_id)}><Logo src={m.away_team?.logo_url}/>{m.away_team?.name}</button></div><small>{m.status || '-'} · {m.round_info || ''} · {m.venue || ''}</small><button className="secondary light" onClick={() => analyzeMatch(m.match_id)}><Sparkles size={16}/> Analisar jogo com IA</button></div>)}</div></Panel> }
const EXTRA_LABELS: Record<string, string> = { penalty_goals: 'Gols pênalti', headed_goals: 'Gols cabeça', free_kick_goals: 'Gols falta', left_foot_goals: 'Gols pé esq.', right_foot_goals: 'Gols pé dir.', big_chances_missed: 'Grandes chances perdidas', successful_dribbles: 'Dribles certos', duels_won: 'Duelos vencidos', aerial_duels_won: 'Duelos aéreos', penalties_won: 'Pênaltis sofridos', penalties_committed: 'Pênaltis cometidos', errors_leading_to_goal: 'Erros p/ gol' }
function statValue(p: Player, key: string) { return p.stats?.[key] ?? p.stats?.extra?.[key] ?? 0 }
function Comparison({ players, availablePlayers, teams, teamComparison, compareIds, setCompareIds, compare, compareTeamIds, setCompareTeamIds, compareTeams, analyzeCompare, disabled }: any) {
  const togglePlayer = (id: number) => setCompareIds((ids: number[]) => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id].slice(-4))
  const toggleTeam = (id: number) => setCompareTeamIds((ids: number[]) => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id].slice(-8))
  const data = players.map((p: Player) => ({ name: p.name, rating: p.stats?.rating || 0, gols: p.stats?.goals || 0, assistencias: p.stats?.assists || 0, jogos: p.stats?.matches || 0, penalti: p.stats?.extra?.penalty_goals || 0, cabeca: p.stats?.extra?.headed_goals || 0 }))
  const teamData = teamComparison.map((r: any) => ({ name: r.team?.short_name || r.team?.name, rating: r.avg_rating || 0, gols: r.goals || 0, assistencias: r.assists || 0, finalizacoes: r.shots || 0, passes: r.key_passes || 0 }))
  const playerExtraKeys: string[] = Array.from(new Set<string>(players.flatMap((p: Player) => Object.keys(p.stats?.extra || {}))))
  const teamExtraKeys: string[] = Array.from(new Set<string>(teamComparison.flatMap((r: any) => Object.keys(r.extra || {}))))
  return <div className="space-y-6"><Panel title="Comparação de jogadores"><div className="toolbar"><ChartLegend text="Use os filtros acima para posição, time e ordenação. Depois selecione de 2 a 4 atletas para comparar score, gols, assistências e estatísticas extras disponíveis."/><button className="secondary light" onClick={compare} disabled={compareIds.length < 2}>Atualizar comparação ({compareIds.length})</button><button className="secondary light" onClick={analyzeCompare} disabled={disabled}><Sparkles size={18}/> Comparar com IA</button></div><div className="overflow-x-auto"><table className="table compact-table"><thead><tr><th>Usar</th><th>Nome</th><th>Time</th><th>Posição</th><th>Rating</th><th>Gols</th><th>Assist.</th><th>Jogos</th><th>Fin.</th><th>Passes-chave</th></tr></thead><tbody>{availablePlayers.map((p: Player) => { const checked = compareIds.includes(p.player_id); return <tr key={p.player_id} className={checked ? 'selectable-row selected' : 'selectable-row'} onClick={() => togglePlayer(p.player_id)}><td><label className="checkbox-hit" onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={checked} onChange={() => togglePlayer(p.player_id)} /><span>{checked ? 'Selecionado' : 'Selecionar'}</span></label></td><td>{p.name}</td><td>{p.team_name || '-'}</td><td>{p.position || '-'}</td><td>{p.stats?.rating ?? '-'}</td><td>{p.stats?.goals ?? '-'}</td><td>{p.stats?.assists ?? '-'}</td><td>{p.stats?.matches ?? '-'}</td><td>{p.stats?.shots ?? '-'}</td><td>{p.stats?.key_passes ?? '-'}</td></tr> })}</tbody></table></div>{players.length > 0 && <><ResponsiveContainer width="100%" height={320}><BarChart data={data}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis/><Tooltip/><Legend/><Bar dataKey="rating" name="Rating" fill="#0284c7"/><Bar dataKey="gols" name="Gols" fill="#16a34a"/><Bar dataKey="assistencias" name="Assistências" fill="#f59e0b"/><Bar dataKey="jogos" name="Jogos" fill="#64748b"/><Bar dataKey="penalti" name="Gols pênalti" fill="#8b5cf6"/><Bar dataKey="cabeca" name="Gols cabeça" fill="#ef4444"/></BarChart></ResponsiveContainer><div className="overflow-x-auto"><table className="table compact-table"><thead><tr><th>Jogador</th><th>Time</th><th>Rating</th><th>Gols</th><th>Assist.</th><th>Finaliz.</th><th>No alvo</th><th>Chances criadas</th>{playerExtraKeys.map(key => <th key={key}>{EXTRA_LABELS[key] || key}</th>)}</tr></thead><tbody>{players.map((p: Player) => <tr key={p.player_id}><td>{p.name}</td><td>{p.team_name || '-'}</td><td>{p.stats?.rating ?? '-'}</td><td>{p.stats?.goals ?? '-'}</td><td>{p.stats?.assists ?? '-'}</td><td>{p.stats?.shots ?? '-'}</td><td>{p.stats?.shots_on_target ?? '-'}</td><td>{p.stats?.big_chances_created ?? '-'}</td>{playerExtraKeys.map(key => <td key={key}>{statValue(p, key) || '-'}</td>)}</tr>)}</tbody></table></div></>}</Panel><Panel title="Comparação entre times"><div className="toolbar"><ChartLegend text="Selecione de 2 a 8 times para somar as estatísticas dos jogadores do elenco no recorte filtrado por competição."/><button className="secondary light" onClick={() => compareTeams()} disabled={compareTeamIds.length < 2}>Comparar times ({compareTeamIds.length})</button></div><div className="team-picker">{teams.map((t: Team) => <button key={t.team_id} className={compareTeamIds.includes(t.team_id) ? 'team-chip active' : 'team-chip'} onClick={() => toggleTeam(t.team_id)}><Logo src={t.logo_url}/>{t.name}</button>)}</div>{teamComparison.length > 0 && <><ResponsiveContainer width="100%" height={320}><BarChart data={teamData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis/><Tooltip/><Legend/><Bar dataKey="rating" name="Rating médio" fill="#0284c7"/><Bar dataKey="gols" name="Gols" fill="#16a34a"/><Bar dataKey="assistencias" name="Assistências" fill="#f59e0b"/><Bar dataKey="finalizacoes" name="Finalizações" fill="#64748b"/><Bar dataKey="passes" name="Passes-chave" fill="#8b5cf6"/></BarChart></ResponsiveContainer><div className="overflow-x-auto"><table className="table compact-table"><thead><tr><th>Time</th><th>Jogadores</th><th>Rating</th><th>Gols</th><th>Assist.</th><th>Finaliz.</th><th>No alvo</th><th>Passes-chave</th><th>Desarmes</th><th>Defesas</th>{teamExtraKeys.map(key => <th key={key}>{EXTRA_LABELS[key] || key}</th>)}</tr></thead><tbody>{teamComparison.map((r: any) => <tr key={r.team?.team_id}><td><span className="team-cell"><Logo src={r.team?.logo_url}/>{r.team?.name}</span></td><td>{r.players_with_stats}</td><td>{r.avg_rating ?? '-'}</td><td>{r.goals ?? '-'}</td><td>{r.assists ?? '-'}</td><td>{r.shots ?? '-'}</td><td>{r.shots_on_target ?? '-'}</td><td>{r.key_passes ?? '-'}</td><td>{r.tackles ?? '-'}</td><td>{r.saves ?? '-'}</td>{teamExtraKeys.map(key => <td key={key}>{r.extra?.[key] ?? '-'}</td>)}</tr>)}</tbody></table></div></>}</Panel></div>
}
function TeamDetail({ data, openTeam, openPlayer, analyzeTeam, analyzePlayer, analyzeMatch }: any) { return <div className="space-y-4"><div className="flex items-center gap-3"><Logo src={data.team?.logo_url}/><div><h3>{data.team?.name}</h3><p>Rating médio do elenco: <strong>{data.avg_rating ?? '-'}</strong></p></div></div><button className="secondary light" onClick={() => data.team?.team_id && analyzeTeam(data.team.team_id)}><Sparkles size={18}/> Analisar time com IA</button><Standings rows={(data.standings || []).map((s:any)=>({...s, team:data.team, competition_name:s.competition_name}))} openTeam={openTeam}/><Players players={data.players || []} openPlayer={openPlayer} compareIds={[]} setCompareIds={()=>{}} compare={()=>{}} analyzePlayer={analyzePlayer}/><Matches matches={data.matches || []} openTeam={openTeam} analyzeMatch={analyzeMatch}/></div> }
function PlayerDetail({ data, analyzePlayer }: any) { const p=data.player; const s=p?.stats; return <div className="space-y-4"><button className="secondary light" onClick={() => p?.player_id && analyzePlayer(p.player_id)}><Sparkles size={18}/> Analisar jogador com IA</button><div className="detail-grid"><Info label="Time" value={p?.team_name}/><Info label="Posição" value={p?.position}/><Info label="Nacionalidade" value={p?.nationality}/><Info label="Idade" value={p?.age}/><Info label="Pé preferido" value={p?.preferred_foot}/><Info label="Altura" value={p?.height}/><Info label="Rating médio" value={s?.rating}/><Info label="Jogos" value={s?.matches}/><Info label="Titular" value={s?.starts}/><Info label="Minutos" value={s?.minutes}/><Info label="Gols" value={s?.goals}/><Info label="Assistências" value={s?.assists}/><Info label="Finalizações" value={s?.shots}/><Info label="Passes-chave" value={s?.key_passes}/><Info label="Desarmes" value={s?.tackles}/><Info label="Defesas" value={s?.saves}/><Info label="Atualizado" value={formatDate(p?.updated_at)}/></div></div> }
function Ranking({ title, rows, field, openPlayer }: any) { return <Panel title={title}><div className="space-y-3">{rows.map((p:any, i:number) => <button className="rank" key={p.player_id || i} onClick={() => p.player_id && openPlayer(p.player_id)}><span>{i+1}</span><strong>{p.name}<small>{p.team}</small></strong><em>{p[field] ?? '-'}</em></button>)}</div></Panel> }
function Card({ icon, label, value }: { icon: React.ReactNode, label: string, value: any }) { return <div className="card"><div className="text-sky-600">{icon}</div><div><p className="text-sm text-slate-500">{label}</p><strong className="text-3xl">{value}</strong></div></div> }
function Panel({ title, children }: { title: string, children: React.ReactNode }) { return <section className="panel"><h2>{title}</h2>{children}</section> }
function TabButton({active,onClick,icon,label}: any){return <button className={active?'tab active':'tab'} onClick={onClick}>{icon}{label}</button>}
function ChartLegend({text}:{text:string}){return <p className="chart-legend">Legenda: {text}</p>}
function Logo({src}:{src?:string}){return src?<img className="logo" src={src} loading="lazy"/>:<span className="logo placeholder">?</span>}
function Info({label,value}:any){return <div className="info"><span>{label}</span><strong>{value ?? '-'}</strong></div>}
function Modal({title,children,onClose}: any){return <div className="modal-bg"><div className="modal"><header><h2>{title}</h2><button className="secondary light" onClick={onClose}><ArrowLeft size={18}/> Voltar</button><button onClick={onClose} aria-label="Fechar"><X/></button></header>{children}</div></div>}
function formatDate(value?: string){ if(!value) return ''; try { return new Intl.DateTimeFormat('pt-BR',{dateStyle:'short', timeStyle:'short'}).format(new Date(value)) } catch { return value } }

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
