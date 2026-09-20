"""Servidor local da live — o meio de campo entre o TikTok e o Roblox.

POR QUE ELE EXISTE
------------------
O Roblox nao fala WebSocket, e o HttpService so faz requisicao de SAIDA. O
jogo nao tem como ser AVISADO de que alguem comentou: ele precisa PERGUNTAR.
Este servidor e' quem guarda a resposta dessa pergunta.

    ponte.py  --POST /eventos-->  [ fila ]  <--GET /eventos--  Roblox Studio

A fila e' um anel com cursor: cada resposta diz ate' onde o jogo ja' leu, e a
pergunta seguinte continua dali. Um servidor de jogo que sobe no meio da live
se ancora no fim da fila em vez de receber o historico inteiro de uma vez --
senao a primeira coisa que ele faria era spawnar uma multidao de fantasmas.

Alem da fila, ele serve o PAINEL (onde voce mexe na live sem reiniciar nada) e
os OVERLAYS do OBS.

Python puro, so' biblioteca padrao. Nao precisa de Deno, nao precisa compilar
nada, e nao existe .exe sem assinatura para o antivirus comer.

Roda sozinho:
    python servidor/servidor.py
"""

import json
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
WEB = os.path.join(AQUI, "web")
CONFIG_DIR = os.path.join(RAIZ, "config")
ARQ_AJUSTES = os.path.join(CONFIG_DIR, "ajustes.json")

#[[ OS TETOS DE EFEITO VEM DO ponte/regras.py, E NAO DE UMA COPIA AQUI.
#
#   POR QUE ISSO IMPORTA: o `limitar()` do regras.py corta cada valor antes de
#   ele virar um spawn. Se o servidor guardasse um teto DIFERENTE (ou nenhum),
#   acontecia o que ja' aconteceu neste kit: o oculos ficou gravado com escala
#   10, o painel mostrava 10, e o jogo desenhava 4 -- porque o teto real era 4.
#   O painel virava um mentiroso, e a queixa que chega e' "mexo no painel e o
#   jogo faz outra coisa".
#
#   Importar de la' e' o unico jeito de os dois nunca discordarem. Se por
#   algum motivo o import falhar (alguem rodou o servidor de outra pasta), o
#   servidor continua funcionando SEM normalizar -- perder o ajuste fino e'
#   melhor do que a live nao subir. ]]
sys.path.insert(0, os.path.join(RAIZ, "ponte"))
try:
    import regras as _regras
except ImportError:
    _regras = None

PORTA = int(os.environ.get("PORTA", "8000"))

# Duas chaves, e nao uma. A de LEITURA vai dentro do jogo Roblox, que qualquer
# pessoa com o arquivo do lugar consegue abrir; a de ESCRITA fica so' na ponte.
# Se a de leitura vazar, o pior que fazem e' ler a fila. Com a de escrita,
# injetariam avatares falsos na sua live.
CHAVE_ESCRITA = os.environ.get("CHAVE_ESCRITA", "escrita-local")
CHAVE_LEITURA = os.environ.get("CHAVE_LEITURA", "leitura-local")

# Quantos eventos a fila guarda. 2000 e' bem mais do que o jogo consome (ele
# le' a cada 1s), e serve de folga para um travamento momentaneo do Studio nao
# fazer ninguem sumir. Acima disso os mais velhos caem -- eles ja' nao teriam
# valor nenhum na tela.
FILA_MAX = 2000


# ══════════════════════════════════════════════════════════════════════
#  A FILA
# ══════════════════════════════════════════════════════════════════════

class Fila:
    """Eventos numerados, com corte por cursor.

    `seq` e' um contador que so' cresce, e NAO e' o indice da lista: a lista
    perde os mais velhos e os indices andariam, mas o cursor que o jogo guarda
    precisa continuar valendo. Guardar o numero junto de cada evento resolve
    isso sem o jogo precisar saber de nada.
    """

    def __init__(self, maximo=FILA_MAX):
        self._itens = []          # [(seq, evento), ...]
        self._seq = 0
        self._maximo = maximo
        self._trava = threading.Lock()

    def juntar(self, eventos):
        with self._trava:
            for ev in eventos:
                self._seq += 1
                self._itens.append((self._seq, ev))
            sobra = len(self._itens) - self._maximo
            if sobra > 0:
                del self._itens[:sobra]
            return self._seq

    def desde(self, cursor):
        """(seq_atual, eventos_novos).

        `cursor` negativo (ou ausente) = "so' me diga onde a fila esta'" — e'
        como um servidor que acabou de subir se ancora sem receber historico.
        """
        with self._trava:
            if cursor is None or cursor < 0:
                return self._seq, []
            return self._seq, [ev for n, ev in self._itens if n > cursor]

    def topo(self):
        with self._trava:
            return self._seq


# ══════════════════════════════════════════════════════════════════════
#  OS AJUSTES (o que o painel salva)
# ══════════════════════════════════════════════════════════════════════
#
# A ponte tem a tabela de fabrica dela em regras.py e funciona sozinha desde o
# primeiro minuto, antes de existir painel nenhum. Isto aqui e' o que o painel
# escreve por cima. Nunca e' o painel que decide se a live funciona -- so' o
# quanto ela e' sua.

def _catalogo(grupos):
    """{grupo: (apelidos, rotulo, emoji, moedas, efeito)} -> {apelido: efeito}.

    Escrever os apelidos na mao, um bloco identico por linha, era o formato
    antigo -- e ele tinha um defeito de manutencao caro: onze blocos pra quatro
    presentes, e mexer no tamanho da galaxia significava lembrar de mexer em
    tres lugares. Quando alguem esquecia um, o presente passava a se comportar
    de um jeito na sua regiao e de outro na regiao de quem estava assistindo,
    que e' um bug praticamente impossivel de reproduzir.
    """
    fora = {}
    for grupo, (apelidos, rotulo, emoji, moedas, efeito) in grupos.items():
        for apelido in apelidos:
            fora[apelido] = dict(efeito, grupo=grupo, rotulo=rotulo,
                                 emoji=emoji, moedas=moedas, id="",
                                 apelidos=list(apelidos))
    return fora


AJUSTES_PADRAO = {
    # Efeito por FAIXA DE PRECO, da mais cara pra mais barata. E' a rede de
    # seguranca que faz presente novo (ou de outra regiao) ja' nascer
    # funcionando, sem voce ter que cadastrar nada.
    #
    # A `danca` vem junto pelo mesmo motivo: um presente de 1000 moedas que o
    # TikTok lancou ontem ja' chega dancando a danca da galaxia, sem cadastro.
    "faixas": [
        {"min": 1000, "efeito": {"prio": 6, "escala": 3.2, "crescimento": 1.6,
                                 "vida": 300, "segura": 9.0,
                                 "cena": 9.0, "chuva": 30, "cor": "B14BFF", "brilho": 5,
                                 "danca": "galaxia"}},
        {"min": 200, "efeito": {"prio": 5, "escala": 4.0, "crescimento": 1.0,
                                "vida": 300, "segura": 14.0,
                                "cena": 4.0, "furacao": 12.0, "cor": "27E1FF", "brilho": 4,
                                "danca": "oculos"}},
        {"min": 30, "efeito": {"prio": 4, "escala": 2.8, "crescimento": 0.6,
                               "vida": 240, "segura": 5.5,
                               "cena": 5.5, "cor": "FFA321", "brilho": 3,
                               "danca": "rosquinha"}},
        {"min": 10, "efeito": {"prio": 3, "escala": 1.8, "crescimento": 0.3,
                               "vida": 150, "segura": 4.0,
                               "cena": 4.0, "cor": "FF2D6F", "brilho": 2, "danca": ""}},
        {"min": 1, "efeito": {"prio": 2, "escala": 1.0, "crescimento": 0.15,
                              "vida": 90, "segura": 1.0,
                              "cena": 0, "cor": "FF9EC4", "brilho": 1, "danca": ""}},
    ],
    # O CATALOGO DE PRESENTES. Vence a faixa de preco.
    #
    # POR QUE ELE EXISTE, ALEM DAS FAIXAS
    #
    # A faixa de preco sozinha erra em casos que importam. O caso concreto: o
    # OCULOS custa 199 moedas e a faixa dos "enormes" comeca em 200 -- por uma
    # moeda ele caia na faixa de baixo e entrava do tamanho de uma rosquinha.
    # Um presente de 199 moedas parecendo um de 30 e' dinheiro do espectador
    # entregue errado, e o tipo de coisa que ninguem percebe olhando o painel.
    #
    # ─── O FORMATO, E POR QUE ELE E' ASSIM ───
    #
    # A chave e' um APELIDO em minusculas, e o MESMO presente aparece sob todos
    # os apelidos dele. Isso nao e' repeticao: a API do TikTok manda o nome em
    # ingles e ele MUDA de regiao pra regiao -- "rose" e "rosa" sao o mesmo
    # presente, e so' um dos dois chega, dependendo de quem esta' assistindo.
    # Guardar sob os dois e' o que faz o gatilho pegar nos dois casos.
    #
    # Dentro de cada efeito vao tambem os campos de IDENTIDADE, e sao eles que
    # tornam o catalogo EDITAVEL pelo painel em vez de fixo no codigo:
    #
    #   grupo     a que presente estas linhas pertencem. E' por ele que o painel
    #             junta "rose" e "rosa" numa ficha so' em vez de duas.
    #   rotulo    o nome que aparece no painel.
    #   emoji     enfeite da ficha.
    #   id        o ID NUMERICO do presente no TikTok. VENCE O APELIDO, porque
    #             ele nao muda de regiao nem quando traduzem o nome. Vem vazio
    #             de fabrica de proposito: um ID chutado errado nunca casa, e o
    #             painel mostra o ID de verdade de cada presente que chegar na
    #             sua live pra voce cadastrar sem adivinhar.
    #   moedas    quanto ele custa. So' informativo (o valor real vem do evento).
    #
    # O campo `danca` e' o passo que o avatar daquele presente vai dançar. Os
    # nomes validos estao em ponte/regras.py (DANCAS_VALIDAS), e cada um deles
    # tem o ID da animacao em roblox/src/ReplicatedStorage/Config.luau (DANCAS).
    # "" = a danca padrao, a mesma de quem so' comentou.
    #
    # O campo `crescimento` e' quanto o presente SOMA de tamanho no avatar que a
    # pessoa ja' tem na tela -- e' a promessa do telao ("mande presentes e seu
    # personagem cresce"). O `escala` e' outra coisa: o tamanho com que o boneco
    # NASCE, quando a pessoa ainda nao tem nenhum.
    "presentes": _catalogo({
        # Rosa -- barata, prioridade, sem cinematica, danca padrao. E' de
        # proposito: a rosa e' o presente comum da live, e se ela ja' tivesse
        # passo proprio o passo deixaria de significar "alguem pagou caro".
        "rosa": (["rose", "rosa"], "Rosa", "\U0001F339", 1,
                 {"prio": 2, "escala": 1.0, "crescimento": 0.15, "segura": 1.0,
                  "cena": 0, "chuva": 0, "furacao": 0, "colosso": 0,
                  "danca_geral": 0, "danca": "", "cor": "FF9EC4", "brilho": 1}),

        # Rosquinha -- grande, com cinematica e danca propria.
        "rosquinha": (["doughnut", "donut", "rosquinha"], "Rosquinha",
                      "\U0001F369", 30,
                      {"prio": 4, "escala": 2.8, "crescimento": 0.6, "segura": 5.5,
                       "cena": 5.5, "chuva": 0, "furacao": 0, "colosso": 0,
                       "danca_geral": 0, "danca": "rosquinha", "cor": "FFA321",
                       "brilho": 3}),

        # Oculos -- o que nasce maior de todos, varre a formacao, danca propria.
        "oculos": (["sunglasses", "oculos", "óculos"], "Óculos", "\U0001F576", 199,
                   {"prio": 5, "escala": 4.0, "crescimento": 1.0, "segura": 14.0,
                    "cena": 4.0, "chuva": 0, "furacao": 12.0, "colosso": 0,
                    "danca_geral": 0, "danca": "oculos", "cor": "27E1FF",
                    "brilho": 4}),

        # Galaxia -- a cinematica mais longa, 30s de chuva, danca propria e o
        # maior crescimento. Os avatares da chuva herdam a danca: sao 20 bonecos
        # entrando no MESMO passo no meio da formacao.
        "galaxia": (["galaxy", "galaxia", "galáxia"], "Galáxia", "\U0001F30C", 1000,
                    {"prio": 6, "escala": 3.2, "crescimento": 1.6, "segura": 9.0,
                     "cena": 9.0, "chuva": 30, "furacao": 0, "colosso": 0,
                     "danca_geral": 0, "danca": "galaxia", "cor": "B14BFF",
                     "brilho": 5}),
    }),
    # O que cada ACAO do espectador faz. `ativo` desligado = nao spawna.
    # O que, ALEM do presente, faz um avatar nascer.
    #
    # SO' O COMENTARIO VEM LIGADO, E ISSO E' A REGRA DO PRODUTO.
    #
    # As tres de baixo vinham ligadas de fabrica, e o resultado ao vivo era o
    # oposto do que o kit promete: bastava UMA pessoa ter comentado o nick dela
    # alguma vez pra que cada 200 curtidas dela, cada seguida e cada
    # compartilhamento virassem um boneco NOVO. Numa live de verdade a curtida e'
    # o evento mais frequente que existe -- gente segura o coracao e manda
    # dezenas por segundo -- entao a formacao enchia sozinha, com o chat parado.
    #
    # Quem estava transmitindo via bonecos aparecendo do nada, sem ninguem
    # digitar, e nao tinha como saber de onde vinham: curtida nao aparece no
    # chat. Pior: isso mata o motivo de comentar. Se o boneco aparece de
    # qualquer jeito, o pedido "comenta o seu nick que voce aparece na tela" --
    # que e' o que faz a live crescer -- deixa de ser verdade.
    #
    # Elas continuam no painel, prontas, com os numeros calibrados. Ligar e' um
    # clique, e ai' e' uma escolha de quem esta' transmitindo, e nao uma
    # surpresa no meio da primeira live.
    "acoes": {
        "comentario": {"ativo": True, "prio": 0, "escala": 1.0, "vida": 45,
                       "segura": 0.4, "cena": 0, "cor": "FFFFFF", "brilho": 0},
        "curtida": {"ativo": False, "a_cada": 200, "prio": 1, "escala": 1.0,
                    "vida": 60, "segura": 0.6, "cena": 0, "cor": "FF6B9D", "brilho": 1},
        "seguiu": {"ativo": False, "prio": 2, "escala": 1.3, "vida": 90,
                   "segura": 2.0, "cena": 0, "cor": "4ADE80", "brilho": 1},
        "compartilhou": {"ativo": False, "prio": 2, "escala": 1.2, "vida": 90,
                         "segura": 1.5, "cena": 0, "cor": "60A5FA", "brilho": 1},
    },
    "geral": {
        # Quantos avatares cabem antes de a formacao fechar o ciclo e recomecar.
        "total_avatares": 100,
        # Quantos por fileira. A camera fica do lado +Z, entao fileira nova
        # nasce mais perto de quem assiste.
        "por_fila": 10,
        # Teto de quantos avatares um combo unico pode render.
        "combo_max": 100,
        # Distancia da camera no plano geral.
        "camera_recuo": 34,

        # ─────────────── O CRESCIMENTO ───────────────
        #
        # Ate' onde um avatar pode crescer somando presente sobre presente.
        #
        # 6.0 nao e' um numero solto: e' o maior tamanho em que um boneco ainda
        # CABE no enquadramento junto com a formacao. Acima disso a camera
        # precisa recuar tanto pra ele caber que todo o resto da live vira um
        # tapete de pontinhos no chao -- ou seja, o presente mais caro passa a
        # ESTRAGAR o quadro em vez de destacar quem pagou.
        "tamanho_max": 6.0,
        # Quanto o crescimento demora, em segundos. Salto seco parece bug; um
        # crescimento longo demais termina depois de a camera ja' ter ido
        # embora e a pessoa nao ve' o que pagou. 0.6s e' o ponto em que da'
        # pra ver acontecendo.
        "crescimento_suave": 0.6,
        #[[ O QUE UM PRESENTE FAZ NA TELA. Tres opcoes:
        #
        #   "novo"    cada presente cria um boneco NOVO. Ninguem cresce.
        #             E' a leitura "a live esta' enchendo": a tela mostra
        #             QUANTA gente participou.
        #
        #   "crescer" o presente faz crescer o boneco que a pessoa ja' tem.
        #             So' cria um novo se ela ainda nao estiver na tela.
        #             E' a leitura "quem gastou aparece": premia quem pagou.
        #
        #   "ambos"   as duas coisas: nasce um boneco novo E o que ela ja'
        #             tinha cresce.
        #
        # O PADRAO E' "novo", e a razao e' de produto e nao de codigo: presente
        # tem que colocar ALGUMA COISA NOVA na tela. Um boneco que so' incha no
        # meio da formacao e' um efeito que quem esta' assistindo pelo celular
        # nao liga ao presente que acabou de passar no chat -- e quem pagou
        # fica sem saber se funcionou. Boneco novo aparecendo e' inequivoco.
        #
        # O crescimento continua aqui pra quem quiser: "crescer" premia quem
        # gastou (o boneco DELA fica maior a cada presente) e "ambos" faz as
        # duas coisas. E' um clique no painel.
        "presente_faz": "novo",

        # ─────────────── O ENQUADRAMENTO ───────────────
        #
        # `vertical` liga a composicao pensada pra 9:16 (TikTok Live, OBS em
        # pe'). Ela nao so' muda o FOV: ela recua a camera, porque num quadro
        # estreito o telao inteiro so' cabe de mais longe.
        "vertical": False,
        # Abertura da lente. Menor = mais "teleobjetiva", achata a formacao e
        # aproxima o telao; maior = mais cenario e mais distorcao nas bordas.
        "camera_fov": 62,
        #[[ Distancia da camera pra quem ela esta' seguindo, no plano de perto.
        #
        #   E' o numero que decide entre "close claustrofobico" e "palco".
        #
        #   PRECISA BATER com Config.CAMERA.DISTANCIA no Luau, e nao por
        #   simetria: e' este valor que os testes de enquadramento medem
        #   (roblox/testes/enquadramento.spec.luau). Com os dois diferentes, o
        #   teste aprova um quadro e a live mostra outro -- que e' o pior tipo
        #   de teste que existe. ]]
        "camera_distancia": 38,
        # Altura da camera no plano de perto.
        "camera_altura": 19,
    },
    "rotulo": {
        # O balao do nome em cima da cabeca.
        "fundo": "000000",
        "transparencia": 0.35,
        "cor_do_presente": True,
        "mostrar_nick_roblox": True,
    },
    # A CONTA DO TIKTOK, e se a ponte deve estar conectada nela.
    #
    # Fica gravado junto dos ajustes de proposito: assim o painel lembra a sua
    # conta entre uma live e outra, e reconectar depois de um reinicio e' um
    # clique em vez de digitar o @ de novo.
    #
    # `revisao` sobe a cada mudanca. E' por ela que a ponte percebe que voce
    # mexeu -- comparar a CONTA nao bastaria: desconectar e reconectar na mesma
    # conta nao muda o texto, e a ponte ficaria sem saber que precisa agir.
    "tiktok": {
        "conta": "",
        "ligado": False,
        "revisao": 0,
    },
}


# Secoes em que o painel manda a LISTA COMPLETA, e nao um pedaco.
#
# `presentes` e' o caso: quando voce DESLIGA o gatilho proprio de um presente,
# ele some do que o painel envia. Com a mesclagem normal, "sumiu" nao quer dizer
# nada -- o valor antigo continuaria la' pra sempre, e desligar um presente no
# painel simplesmente nao funcionaria. Aqui a secao inteira e' substituida, e
# ausencia passa a significar remocao.
SECOES_SUBSTITUIDAS = ("presentes",)


def _mesclar(base, novo):
    """Copia profunda de `base` com `novo` por cima.

    Chave a chave, e nao um update() raso: o painel manda so' o pedaco que ele
    conhece, e um update raso apagaria o resto. Ja' aconteceu com a secao
    `geral` quando o painel de placar salvou sem ela.
    """
    fora = dict(base)
    if not isinstance(novo, dict):
        return fora
    for k, v in novo.items():
        if k in SECOES_SUBSTITUIDAS:
            fora[k] = json.loads(json.dumps(v)) if isinstance(v, dict) else {}
        elif isinstance(v, dict) and isinstance(fora.get(k), dict):
            fora[k] = _mesclar(fora[k], v)
        else:
            fora[k] = v
    return fora


def _normalizar_efeito(efeito):
    """Corta um efeito pelos MESMOS limites que o jogo vai aplicar.

    O painel mostra o que esta' gravado. Se o gravado passar do teto, o painel
    mostra um numero que o jogo nunca vai usar -- e foi exatamente isso que
    aconteceu com o oculos gravado em escala 10 num motor que corta em 4.

    Normalizando na LEITURA, o arquivo, o painel e o jogo passam a dizer a
    mesma coisa, e "mexi no painel e o jogo faz outra coisa" deixa de ter como
    acontecer. Os campos de identidade (nome, id, apelidos) sao preservados: o
    `limitar` do regras.py so' conhece os campos de efeito.
    """
    if _regras is None or not isinstance(efeito, dict):
        return efeito
    limpo = _regras.limitar(efeito)
    for campo in ("grupo", "rotulo", "emoji", "moedas", "id", "apelidos", "ativo",
                  "a_cada"):
        if campo in efeito:
            limpo[campo] = efeito[campo]
    return limpo


def _migrar(dados):
    """Completa o que uma versao ANTERIOR do kit gravou.

    O `ajustes.json` de quem ja' usou o kit foi escrito por um painel que nao
    conhecia `grupo`, `rotulo`, `id` nem `crescimento`. Como a secao
    `presentes` e' SUBSTITUIDA na mesclagem (e precisa ser -- e' o que faz
    desligar um presente funcionar), esses campos nao voltam sozinhos: o
    arquivo antigo vence, e o painel novo abriria com quatro fichas sem nome e
    com crescimento zero. Ou seja, quem ATUALIZOU o kit teria presentes que
    nao fazem o avatar crescer, e nada na tela dizendo por que.

    Aqui cada apelido gravado e' reencontrado no catalogo de fabrica e recebe
    de volta so' o que falta. O que voce ajustou continua exatamente como voce
    deixou.
    """
    presentes = dados.get("presentes")
    if not isinstance(presentes, dict):
        return dados

    fabrica = AJUSTES_PADRAO["presentes"]
    for apelido, efeito in list(presentes.items()):
        if not isinstance(efeito, dict):
            presentes.pop(apelido, None)
            continue
        modelo = fabrica.get(apelido, {})
        efeito.setdefault("grupo", modelo.get("grupo") or apelido)
        efeito.setdefault("rotulo", modelo.get("rotulo") or apelido.title())
        efeito.setdefault("emoji", modelo.get("emoji") or "\U0001F381")
        efeito.setdefault("moedas", modelo.get("moedas") or 0)
        efeito.setdefault("id", "")
        efeito.setdefault("apelidos", modelo.get("apelidos") or [apelido])
        # O crescimento e' o unico campo NOVO que muda comportamento. Sem
        # padrao de fabrica pra copiar (um presente que voce mesmo criou), ele
        # sai do proprio tamanho: quem nasce grande cresce mais.
        if "crescimento" not in efeito:
            if "crescimento" in modelo:
                efeito["crescimento"] = modelo["crescimento"]
            else:
                try:
                    escala = float(efeito.get("escala") or 1.0)
                except (TypeError, ValueError):
                    escala = 1.0
                efeito["crescimento"] = round(max(0.0, (escala - 0.5)) * 0.5, 2)

    # As faixas herdam o crescimento da faixa de fabrica DE MESMO PISO. Um
    # padrao unico pra todas (0.3, por exemplo) achataria a escada inteira:
    # a galaxia passaria a crescer igual a uma rosa, e o presente de 1000
    # moedas ficaria indistinguivel do de 1 -- que e' precisamente o defeito
    # que este kit existe pra nao ter.
    por_piso = {f["min"]: f["efeito"].get("crescimento", 0.3)
                for f in AJUSTES_PADRAO["faixas"]}
    for faixa in dados.get("faixas") or []:
        if not isinstance(faixa, dict) or not isinstance(faixa.get("efeito"), dict):
            continue
        try:
            piso = int(faixa.get("min") or 0)
        except (TypeError, ValueError):
            piso = 0
        faixa["efeito"].setdefault("crescimento", por_piso.get(piso, 0.3))

    # A NORMALIZACAO vem por ULTIMO, depois de todos os setdefault. Antes
    # deles, os campos que acabaram de ser preenchidos ficariam de fora do
    # corte -- e um `crescimento` herdado de uma faixa poderia passar do teto
    # sem ninguem cortar.
    for apelido, efeito in list(presentes.items()):
        presentes[apelido] = _normalizar_efeito(efeito)
    for faixa in dados.get("faixas") or []:
        if isinstance(faixa, dict) and isinstance(faixa.get("efeito"), dict):
            faixa["efeito"] = _normalizar_efeito(faixa["efeito"])
    for chave, acao in (dados.get("acoes") or {}).items():
        if isinstance(acao, dict):
            dados["acoes"][chave] = _normalizar_efeito(acao)
    return dados


class Ajustes:
    def __init__(self, caminho=ARQ_AJUSTES):
        self.caminho = caminho
        self._trava = threading.Lock()
        self._dados = self._carregar()

    def _carregar(self):
        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                return _migrar(_mesclar(AJUSTES_PADRAO, json.load(f)))
        except (OSError, ValueError):
            # Arquivo ausente ou corrompido nao pode impedir a live de subir.
            return json.loads(json.dumps(AJUSTES_PADRAO))

    def ler(self):
        with self._trava:
            return json.loads(json.dumps(self._dados))

    def salvar(self, novo):
        with self._trava:
            self._dados = _mesclar(self._dados, novo)
            dados = json.loads(json.dumps(self._dados))
        os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
        # Escrita em dois passos: se o PC desligar no meio, o ajustes.json
        # antigo continua inteiro em vez de virar meio arquivo ilegivel -- e
        # meio arquivo ilegivel e' exatamente o que faria a live nao subir na
        # proxima vez.
        temp = self.caminho + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        os.replace(temp, self.caminho)
        return dados


# ══════════════════════════════════════════════════════════════════════
#  ESTADO VIVO (placar, foco da camera, diagnostico)
# ══════════════════════════════════════════════════════════════════════

class Diario:
    """O que aconteceu na live, em ordem, pro painel mostrar.

    POR QUE NAO BASTA O `print` DA JANELA PRETA

    A ponte ja' imprime tudo numa janela de console. So' que a janela preta
    e' o pior lugar possivel pra procurar um problema durante uma
    transmissao: ela rola sozinha, nao tem busca, some atras do OBS, e o que
    voce precisa ler (o comentario que NAO virou avatar) passou ha' quarenta
    linhas. Aqui o mesmo evento fica gravado e o painel mostra do lado dos
    controles, com a cor certa e sem rolar sozinho.

    Anel com cursor, igual a' Fila e pelo mesmo motivo: o painel pergunta "o
    que houve desde o numero N" e recebe so' o que ele ainda nao viu.
    """

    MAXIMO = 500

    def __init__(self):
        self._itens = []
        self._seq = 0
        self._trava = threading.Lock()

    def juntar(self, linhas):
        agora = time.time()
        with self._trava:
            for linha in linhas:
                if not isinstance(linha, dict):
                    continue
                self._seq += 1
                self._itens.append((self._seq, {
                    "n": self._seq,
                    "quando": float(linha.get("quando") or agora),
                    # info | ok | aviso | erro. Qualquer outra coisa vira info:
                    # um nivel desconhecido nao pode fazer a linha sumir do
                    # painel -- linha invisivel e' pior que linha sem cor.
                    "nivel": _nivel(linha.get("nivel")),
                    "origem": str(linha.get("origem") or "ponte")[:16],
                    "texto": str(linha.get("texto") or "")[:400],
                }))
            sobra = len(self._itens) - self.MAXIMO
            if sobra > 0:
                del self._itens[:sobra]
            return self._seq

    def desde(self, cursor):
        with self._trava:
            if cursor is None or cursor < 0:
                # Painel abrindo agora: entrega o fim do historico, e nao a
                # fila inteira. Quem acabou de abrir quer ver o que esta'
                # acontecendo, e as 500 linhas de dez minutos atras so' fariam
                # a tela nascer rolada no lugar errado.
                return self._seq, [ev for _, ev in self._itens[-40:]]
            return self._seq, [ev for n, ev in self._itens if n > cursor]


NIVEIS = ("info", "ok", "aviso", "erro")


def _nivel(valor):
    texto = str(valor or "info").strip().lower()
    return texto if texto in NIVEIS else "info"


class Jogadores:
    """Quem esta' participando da live, com o que se sabe de cada um.

    DOIS DONOS, CADA UM DA SUA METADE, E ISSO E' DE PROPOSITO

    A PONTE sabe o que veio do TikTok: o @, o nick do Roblox, quantos
    presentes, quantas moedas, quando foi a ultima interacao.

    O JOGO sabe o que so' existe dentro do Roblox: o TAMANHO atual do avatar
    e quantos bonecos aquela pessoa tem na tela.

    Se um dos dois escrevesse a linha inteira, ele apagaria os campos do outro
    a cada atualizacao -- e o painel piscaria entre duas metades da verdade.
    Cada lado escreve so' as chaves que ele conhece.
    """

    MAXIMO = 400

    def __init__(self):
        self._trava = threading.Lock()
        self._por_id = {}

    def _linha(self, chave):
        linha = self._por_id.get(chave)
        if linha is None:
            linha = {"tiktok_id": chave, "nickname": "", "nick_roblox": "",
                     "roblox_id": 0, "presentes": 0, "moedas": 0,
                     "avatares": 0, "tamanho": 0.0, "ultima": 0.0}
            self._por_id[chave] = linha
        return linha

    def _aparar(self):
        """Segura a tabela num tamanho fixo, tirando quem sumiu ha' mais tempo.

        Sem isto, uma live de seis horas com trinta mil espectadores deixaria
        trinta mil linhas na memoria -- e o painel, que pede a lista inteira a
        cada dois segundos, passaria a mandar megabytes por resposta.
        """
        if len(self._por_id) <= self.MAXIMO:
            return
        ordenados = sorted(self._por_id.values(), key=lambda l: l["ultima"])
        for linha in ordenados[:len(self._por_id) - self.MAXIMO]:
            self._por_id.pop(linha["tiktok_id"], None)

    def por_ponte(self, lista):
        agora = time.time()
        with self._trava:
            for item in lista or []:
                if not isinstance(item, dict):
                    continue
                chave = str(item.get("tiktok_id") or "")
                if not chave:
                    continue
                linha = self._linha(chave)
                for campo in ("nickname", "nick_roblox"):
                    if item.get(campo):
                        linha[campo] = str(item[campo])[:40]
                for campo in ("roblox_id", "presentes", "moedas"):
                    try:
                        linha[campo] = int(item.get(campo) or linha[campo])
                    except (TypeError, ValueError):
                        pass
                linha["ultima"] = agora
            self._aparar()

    def por_jogo(self, tamanhos):
        """{tiktok_id: {"tamanho": n, "avatares": n}} vindo do Roblox."""
        with self._trava:
            for chave, dados in (tamanhos or {}).items():
                if not isinstance(dados, dict):
                    continue
                linha = self._linha(str(chave))
                try:
                    linha["tamanho"] = round(float(dados.get("tamanho") or 0), 2)
                    linha["avatares"] = int(dados.get("avatares") or 0)
                except (TypeError, ValueError):
                    pass
            self._aparar()

    def esquecer_tamanhos(self):
        """O ciclo limpou a formacao: ninguem tem avatar na tela agora.

        Chamado pelo jogo ao apagar a grade. Sem isto o painel continuaria
        mostrando "tamanho 4.2" de gente cujo boneco nao existe mais, e o
        numero so' voltaria ao normal se aquela pessoa participasse de novo --
        ou seja, quanto MENOS ativa a pessoa, mais errado o painel ficava.
        """
        with self._trava:
            for linha in self._por_id.values():
                linha["tamanho"] = 0.0
                linha["avatares"] = 0

    def ler(self, quantos=60):
        with self._trava:
            lista = sorted(self._por_id.values(),
                           key=lambda l: l["ultima"], reverse=True)
            return json.loads(json.dumps(lista[:quantos]))


class Estado:
    """O que muda o tempo todo e nao vale a pena gravar em disco."""

    def __init__(self):
        self._trava = threading.Lock()
        self.placar = {"moedas": [], "curtidas": [], "presenca": []}
        # Em quem a camera parou agora. A voz le' isto pra narrar.
        self.foco = {"nick": "", "presente": "", "tipo": "", "em": 0.0}
        self.contadores = {"recebidos": 0, "entregues": 0, "ultimo_push": 0.0,
                           "ultimo_pull": 0.0, "espectadores": 0}
        # O que a PONTE diz que esta' acontecendo com a conexao do TikTok.
        # `estado`: parada | conectando | conectada | offline | erro
        self.conexao = {"estado": "parada", "conta": "", "detalhe": "",
                        "em": 0.0}
        # Presentes que ja' chegaram nesta sessao, pelo ID do TikTok. E' a
        # lista que o painel usa pra te oferecer "cadastrar este presente" com
        # o ID certo, em vez de voce ter que descobri-lo em algum lugar.
        self.presentes_vistos = {}

    def por_conexao(self, dados):
        with self._trava:
            self.conexao = {
                "estado": str(dados.get("estado") or "parada")[:20],
                "conta": str(dados.get("conta") or "")[:40],
                "detalhe": str(dados.get("detalhe") or "")[:200],
                "em": time.time(),
            }

    def ler_conexao(self):
        with self._trava:
            return dict(self.conexao)

    def viu_presente(self, presente_id, nome, moedas):
        chave = str(presente_id or "").strip()
        if not chave or not chave.isdigit():
            return
        with self._trava:
            item = self.presentes_vistos.get(chave)
            if item is None:
                if len(self.presentes_vistos) >= 120:
                    return
                item = {"id": chave, "nome": "", "moedas": 0, "vezes": 0}
                self.presentes_vistos[chave] = item
            item["nome"] = str(nome or item["nome"])[:60]
            try:
                item["moedas"] = max(item["moedas"], int(moedas or 0))
            except (TypeError, ValueError):
                pass
            item["vezes"] += 1

    def ler_presentes_vistos(self):
        with self._trava:
            return sorted(self.presentes_vistos.values(),
                          key=lambda i: i["vezes"], reverse=True)[:40]

    def marcar(self, chave, quanto=1):
        with self._trava:
            self.contadores[chave] = self.contadores.get(chave, 0) + quanto

    def carimbar(self, chave, valor=None):
        with self._trava:
            self.contadores[chave] = time.time() if valor is None else valor

    def por_placar(self, dados):
        with self._trava:
            for k in ("moedas", "curtidas", "presenca"):
                lista = dados.get(k)
                if isinstance(lista, list):
                    self.placar[k] = lista[:10]

    def ler_placar(self):
        with self._trava:
            return json.loads(json.dumps(self.placar))

    def por_foco(self, dados):
        with self._trava:
            self.foco = {
                "nick": str(dados.get("nick") or "")[:60],
                "presente": str(dados.get("presente") or "")[:60],
                "tipo": str(dados.get("tipo") or "")[:20],
                "em": time.time(),
            }

    def ler_foco(self):
        with self._trava:
            return dict(self.foco)

    def ler_contadores(self):
        with self._trava:
            return dict(self.contadores)


# ══════════════════════════════════════════════════════════════════════
#  RESOLVER NICK DO ROBLOX (ajuda do painel)
# ══════════════════════════════════════════════════════════════════════
#
# O painel tem um campo "testar com o nick X". Resolver aqui, e nao no
# navegador, e' obrigatorio: a API do Roblox nao manda CORS, entao um fetch
# vindo da pagina seria bloqueado pelo navegador antes de sair.

CABECALHOS_ROBLOX = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    # Sem User-Agent de navegador a API responde 403 (o Cloudflare do Roblox
    # barra assinatura de cliente HTTP). O sintoma e' cruel: parece que o nick
    # nao existe, quando na verdade nenhuma consulta chegou a ser respondida.
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/",
}


def resolver_nick(nome):
    """Nick do Roblox -> UserId, ou None. Nunca levanta."""
    nome = str(nome or "").strip()
    if not nome:
        return None
    corpo = json.dumps({"usernames": [nome], "excludeBannedUsers": True}).encode()
    req = urllib.request.Request("https://users.roblox.com/v1/usernames/users",
                                 data=corpo, headers=CABECALHOS_ROBLOX, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            dados = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            TimeoutError, ValueError):
        return None
    for item in (dados or {}).get("data") or []:
        if item.get("id"):
            return {"id": int(item["id"]), "nome": item.get("name") or nome}
    return None


# ══════════════════════════════════════════════════════════════════════
#  HTTP
# ══════════════════════════════════════════════════════════════════════

FILA = Fila()
AJUSTES = Ajustes()
ESTADO = Estado()
DIARIO = Diario()
JOGADORES = Jogadores()

# Eventos que o PAINEL injetou (botao "testar"). Ficam aqui ate' a ponte
# buscar. Nao vao direto na fila do jogo de proposito: o painel manda um
# presente CRU ("Galaxy, 1000 moedas") e quem sabe traduzir isso em efeito --
# e resolver o nick, e aplicar o combo -- e' a ponte, num lugar so'.
TESTES = []
TESTES_TRAVA = threading.Lock()


class Manipulador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LiveInterativa/1.0"

    # ---------- utilidades ----------

    def log_message(self, formato, *args):
        # O log padrao imprime UMA LINHA POR REQUISICAO. Com o jogo perguntando
        # 1x/s e o painel 1x/2s, a janela vira uma cachoeira em que nenhum aviso
        # de verdade e' legivel. Os avisos que importam sao impressos na mao.
        pass

    def _responder(self, codigo, corpo=b"", tipo="application/json; charset=utf-8"):
        if isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        # O painel e os overlays sao servidos por este mesmo servidor, entao
        # CORS nao seria necessario. Mas quem poe o overlay no OBS as vezes o
        # abre de outro lugar, e um erro de CORS ali e' invisivel: a fonte fica
        # simplesmente preta, sem nenhuma mensagem.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type, x-chave")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, codigo, dados):
        self._responder(codigo, json.dumps(dados, ensure_ascii=False))

    def _corpo(self):
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if tamanho <= 0 or tamanho > 4_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, OSError):
            return {}

    def _autorizado(self, esperada):
        # Rodando em 127.0.0.1 nada disto e' alcancavel de fora da maquina. A
        # chave existe para o dia em que este servidor for pra nuvem: ai' e' a
        # unica coisa entre a sua live e quem quiser injetar avatar falso nela.
        return (self.headers.get("X-Chave") or "") == esperada

    def _arquivo(self, nome):
        caminho = os.path.join(WEB, nome)
        if not os.path.isfile(caminho):
            return self._responder(404, "nao encontrado", "text/plain; charset=utf-8")
        tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo == "application/javascript":
            tipo += "; charset=utf-8"
        with open(caminho, "rb") as f:
            self._responder(200, f.read(), tipo)

    # ---------- rotas ----------

    def do_OPTIONS(self):
        self._responder(204, b"", "text/plain")

    def do_GET(self):
        partes = urllib.parse.urlparse(self.path)
        rota = partes.path.rstrip("/") or "/"
        args = urllib.parse.parse_qs(partes.query)

        if rota == "/":
            self.send_response(302)
            self.send_header("Location", "/painel")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if rota == "/painel":
            return self._arquivo("painel.html")
        if rota == "/placar.html":
            return self._arquivo("placar.html")

        # O JOGO pergunta aqui, 1x por segundo.
        if rota == "/eventos":
            if not self._autorizado(CHAVE_LEITURA):
                return self._json(401, {"erro": "chave de leitura invalida"})
            cru = (args.get("desde") or [None])[0]
            try:
                cursor = int(cru) if cru is not None else None
            except (TypeError, ValueError):
                cursor = None
            seq, lista = FILA.desde(cursor)
            ESTADO.carimbar("ultimo_pull")
            if lista:
                ESTADO.marcar("entregues", len(lista))
            return self._json(200, {"seq": seq, "lista": lista})

        if rota == "/ajustes":
            return self._json(200, AJUSTES.ler())

        if rota == "/placar":
            return self._json(200, ESTADO.ler_placar())

        # A VOZ pergunta aqui pra saber em quem a camera parou.
        if rota == "/camera":
            return self._json(200, ESTADO.ler_foco())

        if rota == "/nick":
            nome = (args.get("nome") or [""])[0]
            achado = resolver_nick(nome)
            if not achado:
                return self._json(404, {"erro": "nick nao encontrado"})
            return self._json(200, achado)

        # A PONTE busca os testes que o painel injetou.
        if rota == "/testes":
            if not self._autorizado(CHAVE_ESCRITA):
                return self._json(401, {"erro": "chave de escrita invalida"})
            with TESTES_TRAVA:
                pendentes, TESTES[:] = list(TESTES), []
            return self._json(200, {"lista": pendentes})

        if rota == "/estado":
            c = ESTADO.ler_contadores()
            agora = time.time()
            conexao = ESTADO.ler_conexao()
            return self._json(200, {
                "fila": FILA.topo(),
                "recebidos": c.get("recebidos", 0),
                "entregues": c.get("entregues", 0),
                "espectadores": c.get("espectadores", 0),
                # Segundos desde o ultimo sinal de cada lado. E' o diagnostico
                # que responde "de que lado esta' o problema?" sem abrir
                # nenhuma outra janela: ponte muda ou jogo mudo.
                "ponte_ha": round(agora - c["ultimo_push"], 1) if c.get("ultimo_push") else None,
                "jogo_ha": round(agora - c["ultimo_pull"], 1) if c.get("ultimo_pull") else None,
                "conexao": conexao,
                # Ha' quanto tempo a ponte deu o ultimo sinal de vida sobre a
                # conexao. Sem isto, uma ponte que MORREU aparece pro painel
                # exatamente como uma ponte conectada e quieta -- o ultimo
                # estado que ela publicou fica congelado na tela pra sempre.
                "conexao_ha": (round(agora - conexao["em"], 1)
                               if conexao.get("em") else None),
            })

        if rota == "/controle":
            return self._json(200, (AJUSTES.ler().get("tiktok") or {}))

        if rota == "/jogadores":
            return self._json(200, {"lista": JOGADORES.ler()})

        if rota == "/presentes-vistos":
            return self._json(200, {"lista": ESTADO.ler_presentes_vistos()})

        if rota == "/logs":
            cru = (args.get("desde") or [None])[0]
            try:
                cursor = int(cru) if cru is not None else None
            except (TypeError, ValueError):
                cursor = None
            seq, linhas = DIARIO.desde(cursor)
            return self._json(200, {"seq": seq, "lista": linhas})

        return self._responder(404, "nao encontrado", "text/plain; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        rota = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

        # A PONTE empurra os spawns aqui.
        if rota == "/eventos":
            if not self._autorizado(CHAVE_ESCRITA):
                return self._json(401, {"erro": "chave de escrita invalida"})
            corpo = self._corpo()
            eventos = corpo.get("eventos")
            if not isinstance(eventos, list):
                return self._json(400, {"erro": "esperava {'eventos': [...]}"})
            seq = FILA.juntar(eventos[:500])
            ESTADO.marcar("recebidos", len(eventos))
            ESTADO.carimbar("ultimo_push")
            return self._json(200, {"seq": seq})

        if rota == "/ajustes":
            return self._json(200, AJUSTES.salvar(self._corpo()))

        # O JOGO publica os placares aqui (alimenta o overlay do OBS).
        if rota == "/placar":
            if not self._autorizado(CHAVE_LEITURA):
                return self._json(401, {"erro": "chave invalida"})
            ESTADO.por_placar(self._corpo())
            return self._json(200, {"ok": True})

        # O JOGO avisa em quem a camera parou (a voz usa isto).
        if rota == "/camera":
            if not self._autorizado(CHAVE_LEITURA):
                return self._json(401, {"erro": "chave invalida"})
            ESTADO.por_foco(self._corpo())
            return self._json(200, {"ok": True})

        # ─────────── A CONEXAO COM O TIKTOK ───────────
        #
        # O PAINEL pede (conta X, ligado/desligado) e a PONTE relata o que
        # conseguiu. Sao rotas separadas porque sao duas verdades diferentes:
        # "o que voce pediu" e "o que esta' acontecendo". Junta-las faria o
        # painel mostrar "conectado" no instante do clique, antes de o TikTok
        # ter dito qualquer coisa -- e uma conta errada apareceria como
        # conectada por varios segundos.
        if rota == "/controle":
            corpo = self._corpo()
            atual = AJUSTES.ler().get("tiktok") or {}
            conta = corpo.get("conta")
            conta = (str(atual.get("conta") or "") if conta is None
                     else str(conta))
            novo = {
                "conta": conta.strip().lstrip("@").strip()[:40],
                "ligado": bool(corpo.get("ligado")),
                # A revisao SOBE SEMPRE, mesmo sem nada ter mudado de valor.
                # E' o que faz "desconectar e conectar de novo na mesma conta"
                # ser uma ordem que a ponte enxerga -- comparando so' os
                # campos, esse clique nao mudaria nada e o botao pareceria
                # quebrado.
                "revisao": int(atual.get("revisao") or 0) + 1,
            }
            AJUSTES.salvar({"tiktok": novo})
            DIARIO.juntar([{
                "nivel": "info", "origem": "painel",
                "texto": ("pediu para CONECTAR em @" + novo["conta"]
                          if novo["ligado"] else "pediu para DESCONECTAR"),
            }])
            return self._json(200, novo)

        # A PONTE relata o estado real da conexao.
        if rota == "/conexao":
            if not self._autorizado(CHAVE_ESCRITA):
                return self._json(401, {"erro": "chave de escrita invalida"})
            ESTADO.por_conexao(self._corpo())
            return self._json(200, {"ok": True})

        # PONTE e JOGO escrevem no diario.
        if rota == "/logs":
            corpo = self._corpo()
            linhas = corpo.get("linhas")
            if not isinstance(linhas, list):
                return self._json(400, {"erro": "esperava {'linhas': [...]}"})
            return self._json(200, {"seq": DIARIO.juntar(linhas[:200])})

        if rota == "/jogadores":
            corpo = self._corpo()
            if isinstance(corpo.get("lista"), list):
                JOGADORES.por_ponte(corpo["lista"])
            if isinstance(corpo.get("tamanhos"), dict):
                JOGADORES.por_jogo(corpo["tamanhos"])
            if corpo.get("limpar_tamanhos"):
                JOGADORES.esquecer_tamanhos()
            return self._json(200, {"ok": True})

        # A PONTE avisa que viu um presente, com o ID de verdade dele.
        if rota == "/presentes-vistos":
            corpo = self._corpo()
            ESTADO.viu_presente(corpo.get("id"), corpo.get("nome"),
                                corpo.get("moedas"))
            return self._json(200, {"ok": True})

        # O PAINEL simula um presente sem gastar moeda.
        if rota == "/testar":
            corpo = self._corpo()
            pedido = {
                "presente": str(corpo.get("presente") or "Teste")[:60],
                "moedas": max(0, int(corpo.get("moedas") or 0)),
                "vezes": max(1, min(int(corpo.get("vezes") or 1), 100)),
                "nick": str(corpo.get("nick") or "")[:40],
                "tipo": str(corpo.get("tipo") or "presente")[:20],
            }
            with TESTES_TRAVA:
                if len(TESTES) > 200:
                    return self._json(429, {"erro": "muitos testes na fila"})
                TESTES.append(pedido)
            return self._json(200, {"ok": True, "pedido": pedido})

        return self._responder(404, "nao encontrado", "text/plain; charset=utf-8")


def _porta_livre(porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", porta))
            return True
        except OSError:
            return False


# O mesmo piso de versao da ponte (ver ponte/deps.py, MINIMO).
#
# Este servidor sozinho rodaria num Python mais velho -- ele so' usa biblioteca
# padrao antiga. Recusar assim mesmo e' de proposito: a ponte NAO roda (a
# TikTokLive exige 3.10), e um servidor no ar sem ponte produz o pior
# diagnostico que existe neste kit -- todas as janelas abrem, o painel carrega,
# e simplesmente nao acontece nada. Melhor parar aqui, com o motivo escrito.
MINIMO = (3, 10)


def principal():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    if sys.version_info < MINIMO:
        v = sys.version_info
        print()
        print("  ============================================================")
        print("   ESTE PYTHON E ANTIGO DEMAIS PRO KIT")
        print("  ============================================================")
        print()
        print("   O kit precisa do Python %s ou mais novo."
              % ".".join(str(n) for n in MINIMO))
        print("   Este aqui e o %d.%d (%s)" % (v.major, v.minor, sys.executable))
        print()
        print("   Rode o INSTALAR.bat: ele baixa e instala uma versao nova")
        print("   do lado, sem mexer na que ja esta ai.")
        print()
        input("   Aperte ENTER para fechar. ")
        raise SystemExit(1)

    if not _porta_livre(PORTA):
        print()
        print("  ============================================================")
        print(f"   A PORTA {PORTA} JA ESTA OCUPADA")
        print("  ============================================================")
        print()
        print("   Quase sempre e' uma janela desta mesma live que ficou")
        print("   aberta de uma sessao anterior.")
        print()
        print("   Feche TODAS as janelas pretas e rode o INICIAR-LIVE.bat de novo.")
        print("   Se nao achar as janelas, reiniciar o PC resolve.")
        print()
        input("   Aperte ENTER para fechar. ")
        raise SystemExit(1)

    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Manipulador)
    servidor.daemon_threads = True

    print()
    print("  ============================================================")
    print("   SERVIDOR DA LIVE NO AR")
    print("  ============================================================")
    print()
    print(f"   Painel de controle : http://localhost:{PORTA}/painel")
    print(f"   Overlay do OBS     : http://localhost:{PORTA}/placar.html")
    print()
    print("   Deixe esta janela ABERTA durante a live inteira.")
    print("   Se ela fechar, nada mais aparece no jogo.")
    print()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n   Servidor encerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    principal()
