"""Distribuição de vagas continentais segundo REC Brasileirão Série A 2026.

Artigos 6º e 7º (CBF): 4 vagas fase de grupos + 1 preliminar por
Brasileirão; campeão e vice da Copa do Brasil (grupo/pre); campeão
Libertadores/Sul-Americana com classificação independente. Duplicidades
retornam à tabela. Se finalistas ainda não são conhecidos, cenário é
marcado PROVISÓRIO, não como classificação oficial definitiva.
"""
import re
import unicodedata
from collections import defaultdict

REGULATION_URL = 'https://stcbfsiteprdimgbrs.blob.core.windows.net/img-site/cdn/REC_Brasileiro_SA_rie_A_2026_v15_12_2025_final_02692c1077.pdf'


def normalize(value):
    text = unicodedata.normalize('NFKD', str(value or '').lower())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(x for x in text if not unicodedata.combining(x))).split())


def _short(value):
    name = normalize(value)
    aliases = {
        'atletico mineiro': 'atletico mg',
        'clube atletico mineiro': 'atletico mg',
        'atletico mg': 'atletico mg',
        'atletico paranaense': 'athletico pr',
        'athletico paranaense': 'athletico pr',
        'athletico pr': 'athletico pr',
        'red bull bragantino': 'bragantino',
        'rb bragantino': 'bragantino',
        'red bull bragantino sp': 'bragantino',
        'corinthians paulista': 'corinthians',
        'sc corinthians paulista': 'corinthians',
        'sao paulo fc': 'sao paulo',
        'flamengo rj': 'flamengo',
        'fluminense fc': 'fluminense',
        'gremio fbpa': 'gremio',
        'gremio rs': 'gremio',
        'cruzeiro ec': 'cruzeiro',
        'esporte clube bahia': 'bahia',
        'bahia ba': 'bahia',
        'esporte clube vitoria': 'vitoria',
        'vitoria ba': 'vitoria',
        'club de regatas vasco da gama': 'vasco',
        'vasco da gama': 'vasco',
        'botafogo fr': 'botafogo',
        'botafogo rj': 'botafogo',
        'santos fc': 'santos',
        'palmeiras sp': 'palmeiras',
        'sociedade esportiva palmeiras': 'palmeiras',
        'associacao chapecoense de futebol': 'chapecoense',
        'chapecoense sc': 'chapecoense',
    }
    return aliases.get(name, name)


def resolve_club(value, table):
    if value is None or value == '':
        return None
    needle = str(value)
    direct = {str(row['team_id']): str(row['team_id']) for row in table}
    if needle in direct:
        return needle
    comparable = _short(needle)
    found = [str(row['team_id']) for row in table if _short(row['team']) == comparable]
    return found[0] if len(found) == 1 else None


def allocate_2026(table, copa_winner=None, copa_runner=None,
                  libertadores_winner=None, sulamericana_winner=None,
                  ranking=None, selection_sources=None):
    """Retorna vagas por clube, sem alterar o banco e sem criar resultados.

    ranking permite usar ordem final de Monte Carlo ou da tabela em vez da
    ordem momentânea. Nomes de campeões estrangeiros não são classificados
    como clubes brasileiros por suposição.
    """
    ids = [str(row['team_id']) for row in table]
    if len(ids) != 20 or len(set(ids)) != 20:
        return {
            'ready': False, 'status': 'waiting_league', 'slots': [],
            'message': 'É preciso receber a classificação completa dos 20 clubes da Série A.',
            'regulation': REGULATION_URL,
        }
    by_id = {str(row['team_id']): row for row in table}
    if ranking is not None:
        if set(str(x) for x in ranking) != set(ids) or len(ranking) != len(ids):
            raise ValueError('Ranking simulado inválido: informe os mesmos 20 times uma única vez.')
        order = [str(x) for x in ranking]
        ranking_mode = 'simulacao'
    else:
        order = [str(row['team_id']) for row in sorted(table, key=lambda r: (
            -int(r.get('points') or 0), -int(r.get('wins') or 0),
            -int(r.get('goal_difference') or 0), -int(r.get('goals_for') or 0), int(r.get('position') or 99)
        ))]
        ranking_mode = 'classificacao_atual'

    champ = resolve_club(copa_winner, table)
    vice = resolve_club(copa_runner, table)
    lib = resolve_club(libertadores_winner, table)
    sula = resolve_club(sulamericana_winner, table)
    if (copa_winner and copa_runner and champ is not None and champ == vice):
        raise ValueError('Campeão e vice da Copa do Brasil não podem ser o mesmo clube.')
    if (libertadores_winner and sulamericana_winner and lib is not None and lib == sula):
        raise ValueError('O mesmo clube não pode ser campeão das duas competições continentais nesta simulação.')

    issues = []
    selections = {
        'copa_winner': copa_winner, 'copa_runner': copa_runner,
        'libertadores_winner': libertadores_winner, 'sulamericana_winner': sulamericana_winner,
    }
    complete_copa = bool(copa_winner and copa_runner and champ and vice)
    if not complete_copa:
        issues.append('A final da Copa do Brasil está indefinida ou contém clube não identificado na Série A; vagas adicionais não foram aplicadas.')
    if not libertadores_winner or not sulamericana_winner:
        issues.append('Os campeões continentais não foram todos definidos; as vagas podem ser redistribuídas quando forem conhecidos.')
    for name, supplied in [('copa_winner', copa_winner), ('copa_runner', copa_runner),
                           ('libertadores_winner', libertadores_winner), ('sulamericana_winner', sulamericana_winner)]:
        if supplied and resolve_club(supplied, table) is None:
            issues.append(f'{name}: clube fora da Série A atual ou nome não reconhecido; confirmar nacionalidade e elegibilidade.')

    # No cenário com Copa do Brasil indefinida, a tabela mostra as cinco
    # vagas nacionais e seis de Sula como BASE PROVISÓRIA, sem cup slots.
    total = {tid: {'team_id': tid, 'team': by_id[tid]['team'], 'points': by_id[tid]['points'],
                   'position': pos, 'competition': 'none', 'phase': None,
                   'reasons': []} for pos, tid in enumerate(order, 1)}

    def grant(tid, phase, reason):
        if not tid:
            return False
        slot = total[tid]
        if slot['competition'] == 'libertadores':
            if phase == 'groups' and slot['phase'] == 'pre':
                slot['phase'] = 'groups'
                slot['reasons'].append(reason)
                return True
            return False
        slot['competition'] = 'libertadores'
        slot['phase'] = phase
        slot['reasons'].append(reason)
        return True

    def next_open(phase, reason):
        for tid in order:
            if total[tid]['competition'] == 'none':
                grant(tid, phase, reason)
                return tid
        return None

    # Continental campeões: ocupam a vaga internacional; domestic slots
    # podem ser transferidos ao próximo clube elegível.
    for tid, reason in ((lib, 'Campeão Libertadores 2026'), (sula, 'Campeão Sul-Americana 2026')):
        grant(tid, 'groups', reason)
    spare_group = 0
    spare_pre = 0

    if complete_copa:
        # §5º: quando o campeão da Copa já tem classificação DIRETA
        # por Série A (entre os quatro primeiros grupos elegíveis) ou
        # por título continental, o vice herda a vaga de GRUPOS da
        # Copa e a sua vaga de pré retorna ao Brasileirão.
        league_direct_candidates = [tid for tid in order if tid not in (lib, sula)][:4]
        if champ in (lib, sula) or champ in league_direct_candidates:
            if not grant(vice, 'groups', 'Vice da Copa do Brasil (vaga direta transferida)'):
                spare_group += 1
            spare_pre += 1
        else:
            if not grant(champ, 'groups', 'Campeão da Copa do Brasil'):
                spare_group += 1
            if not grant(vice, 'pre', 'Vice da Copa do Brasil'):
                spare_pre += 1

    # 4 grupos nacionais: se vice da Copa já tem pré, ele ganha grupos,
    # devolvendo a pré por §3º (classificação mais benéfica).
    awarded_groups = 0
    for tid in order:
        if awarded_groups == 4:
            break
        existing = total[tid]
        if existing['competition'] == 'libertadores' and existing['phase'] == 'groups':
            continue
        if existing['competition'] == 'libertadores' and existing['phase'] == 'pre':
            spare_pre += 1
        grant(tid, 'groups', 'Brasileirão Série A (grupo)')
        awarded_groups += 1

    # 1 pré por classificação no Brasileirão.
    next_open('pre', 'Brasileirão Série A (pré)')
    for _ in range(spare_group):
        next_open('groups', 'Vaga transferida da Copa do Brasil (grupo)')
    for _ in range(spare_pre):
        next_open('pre', 'Vaga transferida da Copa do Brasil (pré)')

    sula_assigned = 0
    for tid in order:
        if sula_assigned >= 6:
            break
        if total[tid]['competition'] == 'none':
            total[tid]['competition'] = 'sulamericana'
            total[tid]['phase'] = 'groups'
            total[tid]['reasons'].append('Série A: seis melhores excluídos da Libertadores')
            sula_assigned += 1

    for tid in order[-4:]:
        if total[tid]['competition'] == 'none':
            total[tid]['competition'] = 'serie_b'
            total[tid]['reasons'].append('Últimos quatro no cenário de classificação')

    slots = [total[tid] for tid in order]
    ready = complete_copa and bool(libertadores_winner) and bool(sulamericana_winner) and not issues
    return {
        'ready': ready, 'status': 'scenario' if not ready else 'complete_scenario',
        'ranking_mode': ranking_mode, 'slots': slots, 'selections': selections,
        'counts': {
            'libertadores': sum(s['competition'] == 'libertadores' for s in slots),
            'sulamericana': sum(s['competition'] == 'sulamericana' for s in slots),
            'groups': sum(s['competition'] == 'libertadores' and s['phase'] == 'groups' for s in slots),
            'pre': sum(s['competition'] == 'libertadores' and s['phase'] == 'pre' for s in slots),
        },
        'issues': issues, 'regulation': REGULATION_URL,
        'message': ('Simulação completa com escolhas informadas; não é classificação oficial definitiva.'
                    if ready else 'Distribuição provisória; complete os campeões e confira as ressalvas.'),
    }
