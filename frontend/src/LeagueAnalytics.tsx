import React from 'react'
import { BarChart3, CalendarDays, RefreshCw, RotateCcw, Sparkles, Target, Trophy } from 'lucide-react'
import './leagueAnalytics.css'
import ContinentalQualification from './ContinentalQualification'

type Stats = { played:number; wins:number; draws:number; losses:number; points:number; goals_for:number; goals_against:number; ppg:number }
type LeagueRow = Stats & { position:number; team_id:string; team:string; goal_difference:number; first:Stats; return:Stats; home:Stats; away:Stats; recent:Stats }
type Fixture = { id:string; round:number|null; date:string|null; home_id:string; away_id:string; home:string; away:string; played:boolean; home_goals:number|null; away_goals:number|null; status:string }
type League = {
  season:number; source:string; updated_at?:string|null;
  coverage:{fixtures:number;expected:number;finished:number;pending:number;teams:number;complete:boolean};
  simulation_available:boolean; notice:string; provider_warning?:string|null; table:LeagueRow[]; fixtures:Fixture[];
  validation?: {ok:boolean;message:string; checks:{code:string; label:string;ok:boolean;actual:number;expected:number}[]}
}
type Projection = { team_id:string;team:string;current_points:number; expected_points:number;points_p10:number;points_p90:number;expected_position:number;title_pct:number;libertadores_pct:number;sulamericana_pct:number;relegation_pct:number }
type Simulation = {method:string;runs:number;forecast:Projection[];source:string;libertadores_places:number;sula_places:number}
type Props = { token:string; apiUrl:string }
type Period = 'total'|'return'|'first'|'home'|'away'|'recent'
type Outcome = 'H'|'D'|'A'

const fmt = (n:number) => n.toLocaleString('pt-BR', {maximumFractionDigits:1})
const periodLabels:Record<Period,string> = {total:'Geral',first:'1º turno',return:'Returno',home:'Em casa',away:'Fora',recent:'Últimos 5'}
const periods:Period[] = ['total','first','return','home','away','recent']
const nameOf = (row:LeagueRow, period:Period):Stats => period === 'total' ? row : row[period]
function dateOf(value:string|null) { if (!value) return 'Data a definir'; const d = new Date(value); return isNaN(d.getTime()) ? value : d.toLocaleDateString('pt-BR', {day:'2-digit',month:'2-digit',year:'numeric'}) }

export default function LeagueAnalytics({token, apiUrl}:Props) {
  const [data,setData] = React.useState<League|null>(null)
  const [forecast,setForecast] = React.useState<Simulation|null>(null)
  const [loading,setLoading] = React.useState(false)
  const [simLoading,setSimLoading] = React.useState(false)
  const [error,setError] = React.useState('')
  const [period,setPeriod] = React.useState<Period>('return')
  const [team,setTeam] = React.useState('')
  const [libertadores,setLibertadores] = React.useState(5)
  const [overrides,setOverrides] = React.useState<Record<string,Outcome>>({})

  const getData = React.useCallback(async ()=>{
    setLoading(true);setError('')
    try {
      const response = await fetch(`${apiUrl}/analytics/brasileirao?season=2026`,{headers:{Authorization:`Bearer ${token}`}})
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Não foi possível consultar o campeonato.')
      setData(result)
      setForecast(null)
    } catch(e) {setError(e instanceof Error?e.message:'Falha na consulta')}
    finally {setLoading(false)}
  },[apiUrl,token])

  React.useEffect(()=>{void getData()},[getData])
  const teamRows = React.useMemo(()=>[...(data?.table||[])].sort((a,b)=>a.team.localeCompare(b.team,'pt-BR')),[data])
  const effectiveTeam = team || teamRows[0]?.team_id || ''
  const selected = teamRows.find(r=>r.team_id === effectiveTeam)
  const fixtures = (data?.fixtures||[]).filter(f=> f.home_id===effectiveTeam || f.away_id===effectiveTeam)
  const pending = fixtures.filter(f=>!f.played)
  const sorted = [...(data?.table||[])].sort((a,b)=>{
    const left=nameOf(a,period), right=nameOf(b,period)
    return right.points-left.points || right.wins-left.wins ||
      ((right.goals_for-right.goals_against)-(left.goals_for-left.goals_against)) || a.team.localeCompare(b.team,'pt-BR')
  })
  const chosen = pending.filter(f=>overrides[f.id])
  const customPoints = chosen.reduce((n,f)=>n+(overrides[f.id]==='D'?1:(overrides[f.id]==='H' ? f.home_id===effectiveTeam : f.away_id===effectiveTeam)?3:0),0)

  function choose(matchId:string,outcome:Outcome) {
    setOverrides(old=>({...old,[matchId]:outcome}))
    setForecast(null)
  }
  async function runSimulation() {
    setSimLoading(true);setError('')
    try {
      const response=await fetch(`${apiUrl}/analytics/brasileirao/simulate`,{
        method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
        body:JSON.stringify({season:2026,runs:2000,seed:2026,libertadores_places:libertadores,sula_places:6,overrides})
      })
      const result=await response.json()
      if (!response.ok) throw new Error(result.detail || 'Não foi possível simular a competição.')
      setForecast(result)
    } catch(e) { setError(e instanceof Error?e.message:'Erro na simulação') }
    finally {setSimLoading(false)}
  }

  return <div className="league-page">
    <section className="league-head">
      <div><div className="league-eyebrow"><BarChart3 size={16}/> Inteligência esportiva</div><h2>Brasileirão · Projeções 2026</h2><p>Compare turno, returno, mando de campo e reta final. Todos os resultados são obtidos das fontes configuradas.</p></div>
      <button type="button" className="league-btn" disabled={loading} onClick={()=>void getData()}><RefreshCw size={16}/>{loading?'Consultando...':'Atualizar dados'}</button>
    </section>
    {error && <div className="league-warning">{error}</div>}
    {data && <>
      <div className="league-meta"><span>Fonte: <strong>{data.source}</strong></span><span>{data.coverage.finished} resultados de {data.coverage.expected} jogos previstos</span><span>{data.coverage.pending} jogos a disputar/cadastrar</span></div>
      {data.provider_warning && <div className="league-note">{data.provider_warning}</div>}
      {!data.simulation_available && <div className="league-warning"><strong>Validação pendente:</strong> {data.notice} Você ainda pode consultar os jogos e os recortes disponíveis.</div>}
      {data.validation && <section className="league-panel">
        <div className="league-panel-head"><div><h3>Validação automática dos dados</h3><p>Verifica calendário, mandos, rodadas e identificação de partidas antes de liberar projeções.</p></div><span className={data.validation.ok?'league-validation-ready':'league-validation-wait'}>{data.validation.ok?'Pronto para simular':'Verificar dados'}</span></div>
        <div className="league-validation-grid">{data.validation.checks.map(check=><div className="league-validation-item" key={check.code}><span className={check.ok?'league-check-pass':'league-check-fail'}>{check.ok?'✓':'!'}</span><div><strong>{check.label}</strong><small>{check.ok?'Validado':`Encontrado: ${check.actual} · esperado: ${check.expected}`}</small></div></div>)}</div>
      </section>}
      <div className="league-kpis">
        <div><span>Líder atual</span><strong>{data.table[0]?.team || '—'}</strong><small>{data.table[0]?.points ?? 0} pontos</small></div>
        <div><span>Melhor returno</span><strong>{[...data.table].sort((a,b)=>b.return.points-a.return.points)[0]?.team || '—'}</strong><small>pontos desde a 20ª rodada</small></div>
        <div><span>Partidas disponíveis</span><strong>{data.coverage.fixtures}</strong><small>de {data.coverage.expected} previstas</small></div>
        <div><span>Modelo probabilístico</span><strong>{data.simulation_available?'Disponível':'Aguardando dados'}</strong><small>Exige calendário da Série A completo</small></div>
      </div>
      {data.table.length > 0 && <div className="league-kpis">
        <div><span>Melhor ataque</span><strong>{[...data.table].sort((a,b)=>b.goals_for-a.goals_for)[0].team}</strong><small>{[...data.table].sort((a,b)=>b.goals_for-a.goals_for)[0].goals_for} gols marcados</small></div>
        <div><span>Defesa menos vazada</span><strong>{[...data.table].sort((a,b)=>a.goals_against-b.goals_against)[0].team}</strong><small>{[...data.table].sort((a,b)=>a.goals_against-b.goals_against)[0].goals_against} gols sofridos</small></div>
        <div><span>Maior saldo de gols</span><strong>{[...data.table].sort((a,b)=>b.goal_difference-a.goal_difference)[0].team}</strong><small>Saldo de {[...data.table].sort((a,b)=>b.goal_difference-a.goal_difference)[0].goal_difference} gols</small></div>
        <div><span>Melhor mandante</span><strong>{[...data.table].sort((a,b)=>(b.home.played?b.home.points/b.home.played:0)-(a.home.played?a.home.points/a.home.played:0))[0].team}</strong><small>Aproveitamento por jogo em casa</small></div>
      </div>}
      <section className="league-panel">
        <div className="league-panel-head"><div><h3>Classificação por período</h3><p>Use as abas para identificar quem melhorou no returno e a força como mandante/visitante.</p></div></div>
        <div className="league-switch">{periods.map(p=><button key={p} type="button" onClick={()=>setPeriod(p)} className={period===p?'selected':''}>{periodLabels[p]}</button>)}</div>
        <div className="league-scroll"><table className="league-table"><thead><tr><th>Pos.</th><th>Clube</th><th>J</th><th>V</th><th>E</th><th>D</th><th>GP</th><th>GC</th><th>SG</th><th>Pts</th><th>Pts/jogo</th></tr></thead><tbody>{sorted.map((r,i)=>{const s=nameOf(r,period);return <tr key={r.team_id}><td>{i+1}º</td><td><strong>{r.team}</strong></td><td>{s.played}</td><td>{s.wins}</td><td>{s.draws}</td><td>{s.losses}</td><td>{s.goals_for}</td><td>{s.goals_against}</td><td>{s.goals_for-s.goals_against}</td><td><strong>{s.points}</strong></td><td>{fmt(s.played?s.points/s.played:0)}</td></tr>})}</tbody></table></div>
      </section>
      <ContinentalQualification token={token} apiUrl={apiUrl} projectionRanking={forecast?.forecast.map(r=>r.team_id)}/>
      <section className="league-panel">
        <div className="league-panel-head"><div><h3><CalendarDays size={19}/> Simulador de resultados</h3><p>Selecione um clube e marque vitórias, empates ou derrotas nas partidas que faltam.</p></div><div className="league-tools"><label>Clube<select value={effectiveTeam} onChange={e=>setTeam(e.target.value)}>{teamRows.map(r=><option key={r.team_id} value={r.team_id}>{r.team}</option>)}</select></label></div></div>
        {selected && <div className="league-team-summary"><strong>{selected.team}</strong><span>{selected.points} pontos atuais</span><span>{selected.home.points} pontos em casa</span><span>{selected.away.points} pontos fora</span><span>{selected.return.points} pontos no returno</span></div>}
        <div className="league-fixtures">
          {pending.map(f=>{
            const local=f.home_id===effectiveTeam
            return <div className="league-match" key={f.id}>
              <div className="league-match-info"><small>Rodada {f.round||'?'} · {dateOf(f.date)} · {local?'Casa':'Fora'}</small><strong>{f.home} × {f.away}</strong></div>
              <div className="league-result-buttons" aria-label="Palpite para resultado">
                {(['H','D','A'] as Outcome[]).map(o=><button type="button" key={o} className={overrides[f.id]===o?'selected':''} title={o==='H'?f.home+' vence':o==='A'?f.away+' vence':'Empate'} onClick={()=>choose(f.id,o)}>{o==='H'?'1':o==='D'?'X':'2'}</button>)}
                {overrides[f.id] && <button type="button" className="clear" title="Usar cálculo automático" onClick={()=>{setOverrides(old=>{const next={...old};delete next[f.id];return next});setForecast(null)}}>×</button>}
              </div>
            </div>
          })}
          {pending.length===0 && <p className="league-empty">Não há jogos futuros deste clube na fonte atual.</p>}
        </div>
        <div className="league-sim-footer">
          <div><strong>{chosen.length}</strong> resultados definidos. {selected && chosen.length===pending.length && pending.length>0 ? `Com os palpites acima, ${selected.team} termina com ${selected.points+customPoints} pontos.`:'As demais partidas serão simuladas automaticamente.'}</div>
          <div className="league-footer-actions">
            <button type="button" className="league-btn secondary" onClick={()=>{setOverrides({});setForecast(null)}}><RotateCcw size={15}/> Limpar palpites</button>
            <label>Vagas em classificação simplificada<select value={libertadores} onChange={e=>{setLibertadores(Number(e.target.value));setForecast(null)}}>{Array.from({length:9},(_,i)=>i+4).map(n=><option value={n} key={n}>G{n}</option>)}</select></label>
            <button type="button" disabled={!data.simulation_available || simLoading} className="league-btn" onClick={()=>void runSimulation()}><Target size={16}/>{simLoading?'Simulando...':'Simular 2.000 temporadas'}</button>
          </div>
        </div>
        <p className="league-disclaimer">Este simulador rápido estima faixas por posição e não aplica automaticamente os campeões das copas. Use o módulo acima para calcular os repasses de vagas conforme o regulamento CBF 2026.</p>
      </section>
      {forecast && <section className="league-panel">
        <div className="league-panel-head"><div><h3><Trophy size={20}/> Projeção final · {forecast.runs.toLocaleString('pt-BR')} simulações</h3><p>Probabilidades estimadas por modelo simplificado; não são percentuais oficiais.</p></div><span className="league-label"><Sparkles size={15}/> Cenário G{forecast.libertadores_places}</span></div>
        <div className="league-scroll"><table className="league-table"><thead><tr><th>Clube</th><th>Pts atuais</th><th>Pts esperados</th><th>Intervalo 10–90%</th><th>Pos. média</th><th>Título</th><th>Libertadores</th><th>Sul-Americana</th><th>Queda</th></tr></thead><tbody>{forecast.forecast.map(r=><tr key={r.team_id}><td><strong>{r.team}</strong></td><td>{r.current_points}</td><td><strong>{fmt(r.expected_points)}</strong></td><td>{r.points_p10}–{r.points_p90}</td><td>{fmt(r.expected_position)}º</td><td>{fmt(r.title_pct)}%</td><td>{fmt(r.libertadores_pct)}%</td><td>{fmt(r.sulamericana_pct)}%</td><td>{fmt(r.relegation_pct)}%</td></tr>)}</tbody></table></div>
        <p className="league-disclaimer">{forecast.method}</p>
      </section>}
    </>}
    {!data && !loading && !error && <div className="league-empty">Aguardando dados da temporada 2026.</div>}
  </div>
}
