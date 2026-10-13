import React from 'react'
import { AlertCircle, CheckCircle2, Database, RefreshCw, Users } from 'lucide-react'
import './playerSource.css'

type Status={
  configured:boolean;league_id:number;status:string;message:string;
  next_page:number;total_pages:number|null;imported_players:number;
  skipped_players:number;players_in_database:number;stats_in_database:number;
  source:string;partial:boolean;season_access?:boolean|null;subscription_plan?:string
}
type Props={token:string;apiUrl:string;onUpdated:()=>Promise<void>}

export default function PlayerSourcePanel({token,apiUrl,onUpdated}:Props){
  const [data,setData]=React.useState<Status|null>(null)
  const [busy,setBusy]=React.useState(false)
  const [error,setError]=React.useState('')
  const load=React.useCallback(async()=>{
    const response=await fetch(`${apiUrl}/players-source/status`,{headers:{Authorization:`Bearer ${token}`}})
    const payload=await response.json()
    if(!response.ok) throw new Error(payload.detail||'Falha no status de atletas.')
    setData(payload)
    return payload as Status
  },[token,apiUrl])
  React.useEffect(()=>{
    let live=true
    load().catch(e=>{if(live)setError(e instanceof Error?e.message:'Falha na coleta')})
    return ()=>{live=false}
  },[load])

  const ongoing=data?.status==='running'
  React.useEffect(()=>{
    if(!ongoing)return
    let active=true
    const interval=window.setInterval(async()=>{
      try{
        const result=await load()
        if(!active)return
        if(result.status!=='running')await onUpdated()
      }catch(e){if(active)setError(e instanceof Error?e.message:'Falha ao acompanhar atletas')}
    },10000)
    return ()=>{active=false;window.clearInterval(interval)}
  },[ongoing,load,onUpdated])

  async function synchronize(){
    setBusy(true);setError('')
    try{
      const response=await fetch(`${apiUrl}/players-source/sync?pages=8`,{
        method:'POST',headers:{Authorization:`Bearer ${token}`}
      })
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.detail||'Não foi possível iniciar a coleta')
      setData(payload)
    }catch(e){setError(e instanceof Error?e.message:'Erro ao sincronizar')}
    finally{setBusy(false)}
  }
  return <div className="players-source-panel">
    <div className="players-source-heading">
      <div className="players-source-symbol"><Database size={21}/></div>
      <div><strong>Coleta de jogadores · API-Football</strong><p>Estatísticas individuais e elencos da Série A de 2026, sem depender do bloqueio da SofaScore.</p></div>
      <button type="button" className="secondary light" disabled={busy||ongoing} onClick={()=>void load().catch(e=>setError(String(e)))}><RefreshCw size={15}/> Status</button>
    </div>
    {error&&<div className="players-source-warning"><AlertCircle size={16}/>{error}</div>}
    {data&&!data.configured&&<div className="players-source-warning"><AlertCircle size={16}/>Configure <code>API_FOOTBALL_KEY</code> no .env e recrie o container backend. A chave de football-data.org não é a mesma.</div>}
    {data?.configured&&<>
      {data.season_access===false && <div className="players-source-warning"><AlertCircle size={16}/><span><strong>Plano Free sem acesso à Série A 2026.</strong> Você pode continuar usando os jogos e a classificação pela football-data.org. Para importar jogadores atuais por esta API, é necessário acesso contratado à temporada 2026.</span></div>}
      <div className="players-source-kpis">
        <div><span>Atletas no banco</span><strong>{data.players_in_database}</strong></div>
        <div><span>Registros estatísticos</span><strong>{data.stats_in_database}</strong></div>
        <div><span>Página seguinte</span><strong>{data.next_page}{data.total_pages?` / ${data.total_pages}`:''}</strong></div>
      </div>
      <div className="players-source-notice">
        {data.status==='completed'?<CheckCircle2 size={16}/>:<Users size={16}/>}
        <span>{data.message||'Aguardando sincronização.'}</span>
      </div>
      <div className="players-source-actions">
        <button type="button" className="secondary" disabled={busy||ongoing||data.season_access===false} onClick={()=>void synchronize()}>
          <RefreshCw size={16}/>{ongoing?'Importação em andamento':busy?'Iniciando...':data.status==='partial'?'Continuar próximas 8 páginas':'Sincronizar jogadores'}
        </button>
        <small>Com cobertura autorizada, cada execução consulta até 8 páginas. A disponibilidade dos dados individuais depende do plano contratado e da competição.</small>
      </div>
      <p className="players-source-small">Enquanto a importação estiver parcial, rankings podem estar incompletos. O sistema não interpreta ausência de estatística como zero.</p>
    </>}
  </div>
}
