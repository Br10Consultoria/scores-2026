import React from 'react'
import { AlertTriangle, CheckCircle2, RefreshCw, Trophy } from 'lucide-react'
import './continental.css'

type CupGame = { id:number;date:string|null;round:string|null;status:string;home:string;away:string;home_goals:number|null;away_goals:number|null }
type Cup = { key:string;name:string;source:string;status:string;matches:number;completed_matches:number;champion:string|null;runner_up:string|null;finals:CupGame[];recent_matches:CupGame[];message:string }
type SelectionKey = 'copa_winner'|'copa_runner'|'libertadores_winner'|'sulamericana_winner'
type Selection = Record<SelectionKey,string>
type AllocationRow = { team_id:string;team:string;points:number;position:number;competition:string;phase:string|null;reasons:string[] }
type Allocation = {ready:boolean;status:string;message:string;issues?:string[];regulation:string;ranking_mode?:string;slots:AllocationRow[];counts?:{libertadores:number;sulamericana:number;groups:number;pre:number}}
type CupPayload = {cups:Record<string,Cup>;allocation:Allocation;auto_selections:Record<string,string|null>;provider_warning:string|null;league_coverage:{teams:number;fixtures:number}}
type Props = {token:string;apiUrl:string;projectionRanking?:string[];onSelectionChange?:(value:Selection)=>void}
const EMPTY:Selection={copa_winner:'',copa_runner:'',libertadores_winner:'',sulamericana_winner:''}
const OPTIONS:{key:SelectionKey;label:string}[]=[
  {key:'copa_winner',label:'Campeão Copa do Brasil'},
  {key:'copa_runner',label:'Vice da Copa do Brasil'},
  {key:'libertadores_winner',label:'Campeão Libertadores'},
  {key:'sulamericana_winner',label:'Campeão Sul-Americana'}
]
const statusName:Record<string,string>={confirmed:'Campeão confirmado',in_progress:'Em andamento',no_data:'Sem jogos',not_configured:'API não configurada',unavailable:'Dados indisponíveis',season_restricted:'Plano Free não cobre 2026'}
const destinations:Record<string,string>={libertadores:'Libertadores',sulamericana:'Sul-Americana',serie_b:'Rebaixamento',none:'Sem vaga no cenário'}

export default function ContinentalQualification({token,apiUrl,projectionRanking,onSelectionChange}:Props){
  const [payload,setPayload]=React.useState<CupPayload|null>(null)
  const [selected,setSelected]=React.useState<Selection>({...EMPTY})
  const [allocation,setAllocation]=React.useState<Allocation|null>(null)
  const [loading,setLoading]=React.useState(false)
  const [simulating,setSimulating]=React.useState(false)
  const [error,setError]=React.useState('')
  const [useProjection,setUseProjection]=React.useState(false)

  const load=React.useCallback(async()=>{
    setLoading(true);setError('')
    try{
      const response=await fetch(`${apiUrl}/analytics/continental?season=2026`,{headers:{Authorization:`Bearer ${token}`}})
      const result=await response.json()
      if(!response.ok) throw new Error(result.detail||'Falha ao consultar copas.')
      setPayload(result);setAllocation(result.allocation)
      const auto=result.auto_selections||{}
      const initial:Selection = {
        copa_winner:auto.copa_winner||'',
        copa_runner:auto.copa_runner||'',
        libertadores_winner:auto.libertadores_winner||'',
        sulamericana_winner:auto.sulamericana_winner||''
      }
      setSelected(initial)
      onSelectionChange?.(initial)
    }catch(e){setError(e instanceof Error?e.message:'Erro na consulta das copas')}
    finally{setLoading(false)}
  },[apiUrl,token,onSelectionChange])
  React.useEffect(()=>{void load()},[load])

  const teams=(payload?.allocation?.slots||[]).map(s=>({id:s.team_id,name:s.team})).sort((a,b)=>a.name.localeCompare(b.name,'pt-BR'))

  async function simulate(){
    setSimulating(true);setError('')
    try{
      const response=await fetch(`${apiUrl}/analytics/continental/scenario`,{
        method:'POST',
        headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
        body:JSON.stringify({
          season:2026,use_confirmed_results:false,
          ...Object.fromEntries(OPTIONS.map(o=>[o.key,selected[o.key]||null])),
          ranking:useProjection&&projectionRanking?.length===20?projectionRanking:null
        })
      })
      const result=await response.json()
      if(!response.ok) throw new Error(result.detail||'Não foi possível montar o cenário.')
      setAllocation(result.allocation)
    }catch(e){setError(e instanceof Error?e.message:'Falha na simulação')}
    finally{setSimulating(false)}
  }
  const keys=['copa_brasil','libertadores','sulamericana']
  return <section className="league-panel continental-panel">
    <div className="league-panel-head">
      <div><h3><Trophy size={20}/> Copa do Brasil, Libertadores e Sul-Americana</h3><p>Distribuição de vagas para 2027 conforme o regulamento da Série A de 2026 e os resultados disponíveis das copas.</p></div>
      <button type="button" className="league-btn secondary" disabled={loading} onClick={()=>void load()}><RefreshCw size={16}/>{loading?'Consultando...':'Atualizar copas'}</button>
    </div>
    {error&&<div className="league-warning">{error}</div>}
    <div className="continental-cups">
      {keys.map(key=>{
        const cup=payload?.cups?.[key]
        return <div className="continental-cup" key={key}>
          <strong>{cup?.name||({copa_brasil:'Copa do Brasil',libertadores:'Libertadores',sulamericana:'Sul-Americana'} as Record<string,string>)[key]}</strong>
          <span className={'continental-status '+(cup?.status==='confirmed'?'confirmed':'')}>{cup?(statusName[cup.status]||cup.status):'Aguardando API'}</span>
          <p>{cup?.champion ? `Campeão: ${cup.champion}` : cup?.message||'Carregando dados...'}</p>
          {cup?.runner_up&&<p>Vice: {cup.runner_up}</p>}
          <small>{cup?.matches||0} jogos disponíveis · {cup?.completed_matches||0} encerrados</small>
          {(cup?.finals||[]).slice(-1).map(g=><small key={g.id}>Final: {g.home} {g.home_goals??'–'} × {g.away_goals??'–'} {g.away}</small>)}
        </div>
      })}
    </div>
    <p className="league-disclaimer">Sem uma chave API_FOOTBALL_KEY válida, não há atualização automática das três copas. Jogos não coletados não são considerados concluídos.</p>
    <div className="continental-divider"/>
    <div className="league-panel-head"><div><h3>Simular títulos e repasses de vagas</h3><p>Enquanto as finais não ocorrerem, escolha os possíveis campeões e vice. O sistema não os apresenta como resultados oficiais.</p></div></div>
    <div className="continental-options">
      {OPTIONS.map(opt=><label key={opt.key}>{opt.label}<select value={selected[opt.key]} onChange={e=>{const next={...selected,[opt.key]:e.target.value};setSelected(next);onSelectionChange?.(next);setAllocation(null)}}>
        <option value="">Ainda indefinido / fora da Série A</option>
        {teams.map(t=><option value={t.id} key={t.id}>{t.name}</option>)}
      </select></label>)}
    </div>
    <div className="continental-controls">
      <label className="continental-check"><input type="checkbox" disabled={!projectionRanking?.length} checked={Boolean(useProjection&&projectionRanking?.length)} onChange={e=>{setUseProjection(e.target.checked);setAllocation(null)}}/> Aplicar ordem projetada pela simulação do Brasileirão</label>
      <button type="button" className="league-btn" disabled={!payload||simulating} onClick={()=>void simulate()}>{simulating?'Calculando...':'Calcular vagas desse cenário'}</button>
    </div>
    {allocation?.slots?.length ? <>
      <div className="continental-summary">
        <span><strong>{allocation.counts?.libertadores||0}</strong> clubes da Série A na Libertadores</span>
        <span><strong>{allocation.counts?.sulamericana||0}</strong> clubes na Sul-Americana</span>
        <span><strong>{allocation.counts?.groups||0}</strong> vagas de grupos</span>
        <span><strong>{allocation.counts?.pre||0}</strong> vagas preliminares</span>
      </div>
      <div className={allocation.ready?'continental-ok':'league-note'}>
        {allocation.ready?<CheckCircle2 size={16}/>:<AlertTriangle size={16}/>}
        <span>{allocation.message} {allocation.ranking_mode==='simulacao'?'Classificação estimada aplicada.':'Classificação atual utilizada.'}</span>
      </div>
      {Boolean(allocation.issues?.length)&&<div className="continental-notes">{allocation.issues?.map((issue,i)=><p key={i}>{issue}</p>)}</div>}
      <div className="league-scroll"><table className="league-table continental-table"><thead><tr><th>Pos.</th><th>Clube</th><th>Competição 2027</th><th>Fase</th><th>Critério</th></tr></thead><tbody>
        {allocation.slots.map(s=><tr key={s.team_id}>
          <td>{s.position}º</td><td><strong>{s.team}</strong></td>
          <td><span className={'continental-destination '+s.competition}>{destinations[s.competition]||s.competition}</span></td>
          <td>{s.phase==='groups'?'Grupos':s.phase==='pre'?'Preliminar':'–'}</td>
          <td>{s.reasons.join(' / ')||'–'}</td>
        </tr>)}
      </tbody></table></div>
      <p className="league-disclaimer">O resultado acima é uma <strong>projeção condicional</strong> enquanto os campeões não forem confirmados e o Brasileirão não terminar. <a href={allocation.regulation} target="_blank" rel="noopener noreferrer">Regulamento CBF 2026 (artigos 6º e 7º)</a>.</p>
    </> : <div className="league-note">Para calcular as vagas é preciso carregar os 20 clubes do Brasileirão. Confira a integração football-data.org.</div>}
  </section>
}
