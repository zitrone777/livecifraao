# -*- coding: utf-8 -*-
"""Gera o Cenario.model.json: um ESTUDIO DE TRANSMISSAO.

POR QUE UM GERADOR E NAO O JSON NA MAO

O cenario tem umas 200 pecas, e a maioria e' repeticao com um parametro
mudando (as barras de LED, os degraus, as luzes da grade). Escrito na mao, o
arquivo tem 5000 linhas em que ninguem consegue achar nada -- e mudar "a cor do
piso" vira procurar e substituir vinte blocos identicos, com a chance certa de
esquecer um. Aqui a cor do piso e' uma linha na paleta.

O ARQUIVO GERADO E' QUE E' O PRODUTO: o Rojo le' ele, e este script existe pra
poder REGERAR quando for mexer no mapa. Ele fica em ferramentas/ pra viajar
junto com o kit.

═══════════════════════════════════════════════════════════════════
A DIRECAO DE ARTE
═══════════════════════════════════════════════════════════════════

O pedido foi: nao um mapa preto, nem um mapa colorido. Alguma coisa com a cara
de uma live.

O que isso quer dizer na pratica: um ESTUDIO. Nao um palco de show noturno
(preto com neon), nem um mundo de brinquedo (saturado). Um set de transmissao
de verdade -- daqueles de podcast e de programa gravado -- que e' um lugar
neutro e QUENTE, feito pra que a camera enxergue bem quem esta' nele.

  PISO       concreto polido claro. Claro de proposito: ele devolve luz pros
             avatares por baixo, que e' o que impede o "boneco escuro em cima
             de um chao escuro" do cenario anterior. E' o truque mais barato
             de iluminacao que existe.
  CICLORAMA  a parede curva de fundo dos estudios. Substitui o horizonte de
             predios noturnos: cidade de fundo compete com os avatares e data
             a live; um fundo liso nao compete com nada.
  MADEIRA    a plataforma e as laterais. E' o que tira o cenario do
             "corporativo cinza" sem cair no colorido.
  LUZ        softbox e luz de recorte, cor de estudio (levemente quente na
             frente, fria no contra). Nada de refletor colorido apontando pra
             lugar nenhum.
  ACENTO     UMA cor, e so' uma: o coral da marca, em faixas finas. Acento e'
             o que separa "neutro" de "sem graca"; duas cores de acento ja'
             viram "colorido".

A REGRA QUE NAO PODE MUDAR: o topo do piso fica em y=0. E' onde a formacao
planta os pes (ver Formacao.posicao). Subir o piso um stud deixa cem bonecos
flutuando.
"""

import io
import json
import os

# A pasta do kit e' a MAE desta (ferramentas/). Caminho relativo ao
# arquivo, e nao ao diretorio de onde voce chamou: assim o gerador
# funciona do Explorer, do prompt e de dentro de um editor.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "roblox/src/Workspace/Cenario.model.json")


# ═══════════════════════ A PALETA ═══════════════════════
#
# Um lugar so'. Trocar o clima do estudio inteiro e' mexer aqui.

def rgb(r, g, b):
    return [round(r / 255, 4), round(g / 255, 4), round(b / 255, 4)]


CONCRETO       = rgb(196, 192, 186)   # piso do estudio, claro
CONCRETO_ESC   = rgb(151, 147, 141)   # rodape e recuos
CICLORAMA      = rgb(214, 210, 203)   # a parede de fundo
CICLORAMA_ALTO = rgb(178, 174, 168)   # o alto dela, um degrade em degraus
MADEIRA        = rgb(122, 88, 61)     # plataforma e laterais
MADEIRA_ESC    = rgb(88, 63, 43)      # frisos
GRAFITE        = rgb(58, 58, 63)      # trelicas, tripes, moldura
GRAFITE_CLARO  = rgb(86, 86, 92)
PRETO_TELA     = rgb(10, 11, 18)      # so' o telao e' escuro -- pra ele brilhar
ACENTO         = rgb(255, 45, 111)    # UMA cor de acento
LUZ_QUENTE     = rgb(255, 236, 208)
LUZ_FRIA       = rgb(214, 231, 255)


# ═══════════════════════ Auxiliares ═══════════════════════

def peca(nome, tamanho, pos, cor, material="SmoothPlastic", **extra):
    """Uma BasePart ancorada, sem colisao e sem consulta.

    Tudo no cenario e' assim: os avatares nao colidem com nada (eles sao
    plantados na grade), e peca com CanQuery ligado entra em raycast a' toa.
    Cada peca do cenario que participa da fisica e' um custo por quadro pra
    nada -- e com 200 pecas isso aparece no FPS da gravacao.
    """
    props = {
        "Size": [float(x) for x in tamanho],
        "CFrame": [float(pos[0]), float(pos[1]), float(pos[2]),
                   1.0, 0, 0.0, 0, 1, 0, -0.0, 0, 1.0],
        "Anchored": True,
        "Locked": True,
        "CanCollide": False,
        "CanTouch": False,
        "CanQuery": False,
        "CastShadow": False,
        "Material": material,
        "Color": cor,
        "TopSurface": "Smooth",
        "BottomSurface": "Smooth",
    }
    props.update(extra)
    return {"name": nome, "className": "Part", "properties": props}


def pasta(nome, filhos):
    return {"name": nome, "className": "Folder", "children": filhos}


def udim2(sx, sy, ox=0, oy=0):
    return {"UDim2": [[sx, ox], [sy, oy]]}


def texto(nome, y, altura, conteudo, cor, fonte="GothamBold",
          alinhar="Center", x=0.23, largura=0.54):
    return {
        "name": nome,
        "className": "TextLabel",
        "properties": {
            "Size": udim2(largura, altura),
            "Position": udim2(x, y),
            "BackgroundTransparency": 1,
            "Text": conteudo,
            "TextColor3": cor,
            "TextScaled": True,
            "TextXAlignment": alinhar,
            "Font": fonte,
        },
    }


# ═══════════════════════ 1. O CHAO ═══════════════════════
#
# O piso do estudio: concreto CLARO. Ele e' o refletor mais importante do
# cenario -- devolve luz pros avatares por baixo e impede o "boneco escuro
# sobre chao escuro" que o palco preto anterior produzia.

def chao():
    #[[ ═══════════════ A REGRA DO CHAO PISCANDO ═══════════════
    #
    #   NENHUMA superficie horizontal pode dividir a mesma altura com outra
    #   que esteja embaixo dela. Duas faces coplanares fazem a placa de video
    #   alternar entre as duas a cada quadro, e o chao PISCA -- forte, e mais
    #   ainda quando a camera se move, que e' o tempo inteiro numa live.
    #
    #   O caso concreto que aconteceu aqui: a plataforma de madeira tinha o
    #   topo em y=0 e o piso de concreto tambem. Os dois disputavam o mesmo
    #   plano em toda a area da formacao.
    #
    #   A solucao e' um DEGRAU DE VERDADE, e nao um empurraozinho: o piso
    #   desce 0.6 stud, e a plataforma fica sozinha em y=0. Meio stud e' pouco
    #   pra vista de longe e MUITO pro buffer de profundidade -- que e' o que
    #   importa.
    #
    #   A verificacao no fim deste arquivo (`conferir_coplanares`) reprova a
    #   geracao se alguem reintroduzir o problema. ]]
    PISO_TOPO = -0.6

    itens = [
        # O chao do mundo, la' fora do estudio. Fica um tom abaixo pra o piso
        # do estudio se destacar como um lugar, e nao como uma continuacao.
        peca("ChaoDoMundo", (1600, 12, 1600), (0, -14, 100), CONCRETO_ESC,
             "Concrete", CanCollide=True),

        # O PISO DO ESTUDIO, 0.6 stud abaixo da plataforma.
        peca("PisoDoEstudio", (200, 8, 340), (0, PISO_TOPO - 4, 100), CONCRETO,
             "Concrete", CanCollide=True, Reflectance=0.04),
    ]

    #[[ A PLATAFORMA DE MADEIRA sob a formacao.
    #
    #   Ela existe por um motivo de enquadramento, e nao de decoracao: sem
    #   nada sob os bonecos, a metade de baixo do quadro e' um campo de
    #   concreto vazio. A plataforma da' um chao VISUAL a' formacao, e a
    #   madeira e' o que tira o estudio do cinza corporativo.
    #
    #   O TOPO DELA E' O y=0 DO KIT INTEIRO: e' onde a formacao planta os pes
    #   (ver Formacao.posicao e Avatares.plantar). Esta e' a unica medida do
    #   mapa que nao pode mudar -- subir a plataforma um stud deixa cem
    #   bonecos flutuando. ]]
    itens.append(peca("Plataforma", (150, 1.2, 190), (0, -0.6, 30), MADEIRA,
                      "WoodPlanks", CanCollide=True))

    #[[ As reguas do assoalho, como SULCOS e nao como frisos em relevo.
    #
    #   Rente ao topo da plataforma (a versao anterior deixava 0.06 de
    #   diferenca) eles voltam a piscar exatamente como o chao piscava. Um
    #   relevo alto o bastante pra nao piscar (0.25+) viraria um degrau que os
    #   avatares pisam.
    #
    #   Como SULCO, os dois problemas somem: o topo do friso fica 0.3 ABAIXO da
    #   plataforma (longe do plano dela) e o resultado ainda le' como assoalho
    #   de madeira -- que e' um piso feito de reguas separadas por frestas. ]]
    for i in range(11):
        x = -70 + i * 14
        itens.append(peca(f"Sulco{i}", (0.5, 1.0, 190), (x, -0.8, 30),
                          MADEIRA_ESC, "WoodPlanks"))

    #[[ A FAIXA DE ACENTO na borda da plataforma.
    #
    #   Neon, e a UNICA fonte de cor saturada do cenario inteiro. E' o que
    #   separa "neutro" de "sem graca". Fina de proposito: uma faixa grossa
    #   vira uma segunda fonte de luz e comeca a competir com o telao. ]]
    #   A borda fica 0.35 ACIMA da plataforma: alto o bastante pra nao brigar
    #   com o plano dela, baixo o bastante pra ninguem tropecar visualmente.
    for nome, tam, pos in (
            ("BordaAcentoFrente", (150, 1.5, 0.8), (0, -0.4, 125.4)),
            ("BordaAcentoEsq", (0.8, 1.5, 190), (-74.6, -0.4, 30)),
            ("BordaAcentoDir", (0.8, 1.5, 190), (74.6, -0.4, 30))):
        itens.append(peca(nome, tam, pos, ACENTO, "Neon"))
    return pasta("Chao", itens)


# ═══════════════════════ 2. O CICLORAMA ═══════════════════════
#
# A parede de fundo dos estudios de verdade: lisa, clara, sem cantos.
#
# Ela substitui o horizonte de predios noturnos do cenario antigo, e a troca
# tem duas razoes. A primeira e' de leitura: uma cidade ao fundo compete com os
# avatares pela atencao de quem assiste num celular. A segunda e' de luz -- um
# fundo claro atras dos bonecos os separa do fundo, e era isso que faltava no
# ceu preto: silhueta escura contra fundo escuro.
#
# "Curva" e' feita em DEGRAUS: o Roblox nao tem parede curva barata, e vinte
# blocos de altura crescente lidos de 100 studs de distancia leem como uma
# curva. Cada degrau um tom mais escuro que o de baixo faz o degrade vertical
# que os estudios conseguem com luz.

def ciclorama():
    itens = []
    DEGRAUS = 14
    for i in range(DEGRAUS):
        t = i / (DEGRAUS - 1)
        cor = [CICLORAMA[c] + (CICLORAMA_ALTO[c] - CICLORAMA[c]) * t
               for c in range(3)]
        altura = 8.0
        y = altura / 2 + i * altura
        # Recua um pouco a cada degrau: e' o que da' a impressao de curva
        # em vez de parede reta.
        z = -96 - (t ** 2) * 10
        itens.append(peca(f"Cyc{i}", (420, altura + 0.2, 6),
                          (0, y, z), cor, "Concrete"))

    #[[ As laterais, dobrando pra frente. Fecham o quadro dos dois lados e
    #   impedem que a camera pegue o vazio alem do estudio quando a formacao
    #   anda pra frente.
    #
    #   Os degraus delas sao DESLOCADOS 4 studs em relacao aos do fundo. Sem
    #   esse deslocamento, o topo de cada degrau lateral fica na mesma altura
    #   do topo do degrau de fundo correspondente, e os dois planos brigam bem
    #   no canto do quadro. E de quebra o desencontro fica melhor de olhar:
    #   uma emenda em degraus alternados le' como curva, e em degraus alinhados
    #   le' como erro de construcao. ]]
    for lado, sinal in (("Esq", -1), ("Dir", 1)):
        for i in range(6):
            t = i / 5
            cor = [CICLORAMA[c] + (CICLORAMA_ALTO[c] - CICLORAMA[c]) * t
                   for c in range(3)]
            itens.append(peca(f"CycLat{lado}{i}", (6, 8.2, 200),
                              (sinal * 150, 8 + i * 8, -10), cor, "Concrete"))
    return pasta("Ciclorama", itens)


# ═══════════════════════ 3. O TELAO ═══════════════════════
#
# A unica coisa ESCURA do cenario, e de proposito: num estudio claro, a tela
# preta e' a coisa que a vista procura. Era o contrario no cenario anterior --
# telao escuro num mundo escuro, e ele desaparecia no fundo.

#[[ ═══════════════════════════════════════════════════════════════════
#   A PAREDE E' TRES PECAS, E A DO MEIO E' O CONTRATO COM A CAMERA
#   ═══════════════════════════════════════════════════════════════════
#
#   PainelInferior y  4..18  (148 x 14)  ATRAS DA GALERA. Escuro e mudo.
#   Telao          y 18..32  (148 x 14)  A MENSAGEM. So' esta peca se chama
#                                        "Telao", e e' ela que o
#                                        Camera.client.luau mede e promete
#                                        caber no quadro.
#   PainelSuperior y 32..56  (148 x 24)  A marca, em letra gigante. Enfeite
#                                        de plano aberto.
#
#   POR QUE A MENSAGEM NAO MORA EMBAIXO
#
#   Porque a camera filma NA ALTURA DO PEITO (Config.CAMERA.ALTURA = 1). Com a
#   lente a 4 studs do chao e as cabecas da galera a 6, TODA CABECA FICA ACIMA
#   DA LINHA DO HORIZONTE -- e tapa o que estiver atras dela e mais baixo.
#
#   A conta, na distancia de trabalho: a cabeca de quem a camera segue sobe uns
#   7 graus acima do centro; a 90 studs de parede, 7 graus sao 11 studs de
#   altura. Tudo que estiver abaixo de y=15 no telao esta', na pratica, atras
#   de alguem. A faixa de baixo continua existindo (a parede precisa chegar no
#   chao), so' nao carrega recado nenhum.
#
#   O ALTO TAMBEM NAO SERVE: a lente baixa alcanca ate' uns 29 studs de parede
#   antes da borda de cima do quadro. Sobra a janela do MEIO -- y 18..32 -- e e'
#   por isso que ela e' uma peca separada, com nome proprio.
#
#   Antes era uma peca so', de 52 studs, e a camera prometia caber ela inteira.
#   O solver obedecia do unico jeito que podia: recuando ate' 40 studs pra
#   enquadrar um topo que ninguem precisa ler, e desfazendo o plano de perto
#   que a lente veio buscar.
#
#   MEXEU NA ALTURA OU NA POSICAO DO `Telao`? A camera recua junto, e a
#   mensagem pode sumir atras da galera. Rode o TESTAR-TUDO.bat. ]]
BASE_TELAO = 18.0
ALTURA_TELAO = 14.0
TOPO_TELAO = BASE_TELAO + ALTURA_TELAO      # 32
BASE_PAREDE = 4.0
TOPO_PAREDE = 56.0

#[[ A ZONA SEGURA: num video 9:16 so' ~24% da LARGURA do telao aparece no pior
#   caso (fileira 0, avatar normal -- medido em
#   roblox/testes/enquadramento.spec.luau, que trava esse numero num piso).
#
#   ERA 54%, com a camera antiga. A queda e' consequencia direta da camera de
#   hoje: PERTO da galera quer dizer LONGE do fundo em termos de quadro -- a
#   uns 13 studs do alvo, a lente de 40 graus abre pouco mais de 35 studs de
#   largura la' na parede, que fica 87 studs atras.
#
#   E' a conta que ninguem faz de cabeca e que morde toda vez: aproximar a
#   camera ESTREITA o telao. Tudo que precisa ser LIDO mora nesta coluna
#   central; o que fica fora dela e' conteudo de 16:9. ]]
SEGURA = 0.22
BORDA = (1 - SEGURA) / 2

#[[ AS ASAS: a lista de presentes, que so' aparece no 16:9.
#
#   `ASA_FORA` e' a borda externa dos chips, e ela e' o numero critico: o
#   quadro deitado enxerga ~76% da largura da parede no pior caso, ou seja de
#   0.12 a 0.88. Em 0.13 os chips cabem com uma folga fina -- e o teste trava
#   esse piso, porque "a lista sumiu pelas bordas" e' o tipo de defeito que
#   ninguem percebe ate' alguem perguntar quanto custa a rosquinha. ]]
ASA_FORA = 0.13
ASA = BORDA - 0.02 - ASA_FORA

#[[ A FAIXA QUE A MULTIDAO TAPA, ja' DENTRO da janela do meio.
#
#   A janela y 18..32 foi escolhida pra ficar acima das cabecas (ver o bloco la'
#   em cima), mas a margem no pe' dela e' fina: um presente grande na fileira da
#   frente sobe mais que um boneco normal. Estes 12% de baixo ficam vazios de
#   proposito -- e' a folga que impede o "quase da' pra ler". ]]
PE_TAPADO = 0.12

BRANCO = [1.0, 1.0, 1.0]
CIANO = [0.35, 0.85, 1.0]
AMARELO = [1.0, 0.839, 0.251]
CORAL = [1.0, 0.42, 0.55]


def _redondo(raio=0.2):
    return {"name": "Redondo", "className": "UICorner",
            "properties": {"CornerRadius": {"UDim": [raio, 0]}}}


def _superficie(nome_peca, filhos, pixels=26):
    """A SurfaceGui de uma peca da parede, com o fundo preto por baixo."""
    return {
        "name": nome_peca,
        "className": "SurfaceGui",
        "properties": {
            # A peca esta' em z=-74 sem rotacao, e no Roblox a face "Front"
            # aponta pra -Z. A camera fica do lado +Z: e' a "Back" que ela ve'.
            "Face": "Back",
            # Sem influencia de luz: um telao que escurece quando a luz do
            # estudio muda e' um telao que as vezes nao da' pra ler.
            "LightInfluence": 0,
            "PixelsPerStud": pixels,
            "SizingMode": "PixelsPerStud",
            "ZIndexBehavior": "Sibling",
        },
        "children": [{
            "name": "Fundo",
            "className": "Frame",
            "properties": {
                "Size": udim2(1, 1),
                "BackgroundColor3": PRETO_TELA,
                "BorderSizePixel": 0,
            },
            "children": filhos,
        }],
    }


def _cartao(nome, visivel, linhas):
    #[[ Um CARTAO da coluna central. O telao mostra UM DE CADA VEZ, e quem
    #   troca e' o jogo (ver `girarTelao` no Principal.server.luau).
    #
    #   POR QUE RODIZIO E NAO TUDO JUNTO
    #
    #   A coluna central tem 37 studs de largura por 17 de altura -- e' o que
    #   sobra depois que o 9:16 corta o resto do telao. Empilhar a chamada MAIS
    #   a lista de presentes MAIS o que cada um faz nesse espaco significa
    #   encolher cada linha ate' o tamanho em que nenhuma delas se le' no video
    #   de um celular, que e' exatamente o problema que este telao existe pra
    #   resolver.
    #
    #   Em rodizio, cada cartao usa a coluna INTEIRA e cada linha fica com uns
    #   4,5 studs de altura -- ~6,5% da altura do quadro, ou 126 pixels num
    #   video de 1920. Da' pra ler de relance, que e' o unico jeito que um
    #   telao e' lido no meio de uma transmissao.
    #
    #   E a troca em si CHAMA ATENCAO: uma parede que muda a cada poucos
    #   segundos e' a unica coisa do cenario que se mexe sozinha. ]]
    filhos = [texto(sub, y, altura, conteudo, cor, fonte=fonte,
                    x=0.0, largura=1.0)
              for sub, y, altura, conteudo, cor, fonte in linhas]
    return {
        "name": nome,
        "className": "Frame",
        "properties": {
            "Size": udim2(SEGURA, 1 - PE_TAPADO),
            "Position": udim2(BORDA, 0.0),
            "BackgroundTransparency": 1,
            "Visible": visivel,
        },
        "children": filhos,
    }


def _chip_presente(i, x, y, largura, altura):
    #[[ Um presente da lista lateral: NOME em cima, O QUE ELE FAZ embaixo.
    #
    #   Duas linhas, e nao uma. "Rosquinha \u00b7 30" responde quanto custa e nao
    #   responde a pergunta que faz alguem mandar: o que acontece na tela se eu
    #   mandar isso. Sem essa resposta, a lista e' uma tabela de precos de uma
    #   coisa que o espectador nao sabe o que e'.
    #
    #   AS DUAS LINHAS SAO ESCRITAS PELO JOGO, e as duas saem do catalogo do
    #   painel -- inclusive o efeito, que e' derivado dos campos que o proprio
    #   presente tem (ver `frasePresente` no Principal.server.luau). E' o que
    #   impede o telao de prometer um furacao que voce desligou ontem.
    #
    #   Estes chips ficam FORA da zona segura de prop\u00f3sito: eles sao conteudo
    #   de 16:9. Num video em pe' eles nao aparecem, e quem carrega a lista la'
    #   e' o rodizio da coluna central. ]]
    return {
        "name": f"Presente{i}",
        "className": "Frame",
        "properties": {
            "Size": udim2(largura, altura),
            "Position": udim2(x, y),
            "BackgroundColor3": [0.11, 0.12, 0.17],
            "BackgroundTransparency": 0.25,
            "BorderSizePixel": 0,
            # Escondido: quem acende e' o jogo, e so' se o presente existir no
            # catalogo. Um slot visivel e em branco e' pior que slot nenhum.
            "Visible": False,
        },
        "children": [
            _redondo(0.22),
            texto("Nome", 0.06, 0.42, "", AMARELO, x=0.04, largura=0.92),
            texto("Efeito", 0.52, 0.38, "", CIANO, fonte="GothamMedium",
                  x=0.04, largura=0.92),
        ],
    }


def tela_do_telao():
    """A FAIXA DE BAIXO da parede: a unica parte que precisa ser LIDA."""
    filhos = []

    # Um fio de acento no topo da faixa: separa a mensagem do painel de cima e
    # da' a ela a cara de tarja de transmissao, em vez de tela flutuando.
    filhos.append({
        "name": "FioDoTopo",
        "className": "Frame",
        "properties": {
            "Size": udim2(1, 0.035),
            "Position": udim2(0, 0),
            "BackgroundColor3": ACENTO,
            "BorderSizePixel": 0,
        },
    })

    #[[ \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 A COLUNA CENTRAL, EM RODIZIO \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    #
    #   O cartao da CHAMADA nasce visivel: e' o que o telao diz enquanto o
    #   servidor nao respondeu, e e' a unica coisa que a live PRECISA dizer pra
    #   funcionar. Se o relay estiver fora do ar, a live continua convidando. ]]
    filhos.append(_cartao("CartaoChamada", True, [
        ("Linha1", 0.09, 0.28, "COMENTE SEU", BRANCO, "GothamBold"),
        ("Linha2", 0.38, 0.28, "NICK DO ROBLOX", AMARELO, "GothamBold"),
        ("Linha3", 0.69, 0.24, "E APARE\u00c7A AQUI", BRANCO, "GothamMedium"),
    ]))

    #[[ O cartao do PRESENTE. Nasce escondido e com o texto vazio: quem
    #   escreve as tres linhas e acende e' o jogo, uma vez por presente do
    #   catalogo, em rodizio com a chamada. ]]
    filhos.append(_cartao("CartaoPresente", False, [
        ("Nome", 0.07, 0.30, "", AMARELO, "GothamBold"),
        ("Efeito", 0.39, 0.28, "", CIANO, "GothamBold"),
        ("Preco", 0.71, 0.20, "", CORAL, "GothamMedium"),
    ]))

    #[[ \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 A LISTA LATERAL (s\u00f3 16:9) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    #
    #   Quatro slots, dois de cada lado da coluna central, PREENCHIDOS EM TEMPO
    #   DE EXECUCAO a partir do catalogo do painel.
    #
    #   POR QUE NAO ESCREVER OS NOMES AQUI: porque o catalogo e' editavel. Voce
    #   pode adicionar um presente novo no painel, mudar o preco de outro ou
    #   desligar um -- e um telao com a lista gravada no mapa passaria a
    #   anunciar presentes que nao fazem mais nada, ou a esconder os que fazem.
    #   Um telao que mente sobre o que aceitar e' pior que um telao sem lista:
    #   o espectador manda o presente errado e nao acontece o que ele esperava.
    #
    #   AS COLUNAS SAO SIMETRICAS em volta do centro, e as duas terminam dentro
    #   do que o 16:9 enxerga (ver ASA_FORA). Mais pra fora e o chip sai do
    #   quadro tambem no video deitado. ]]
    for i in range(4):
        lado, linha = i % 2, i // 2
        x = ASA_FORA if lado == 0 else (BORDA + SEGURA + 0.02)
        filhos.append(_chip_presente(i + 1, x, 0.10 + linha * 0.40, ASA, 0.34))

    return _superficie("Tela", filhos)


def painel_superior():
    #[[ O ALTO DA PAREDE: enfeite de plano aberto.
    #
    #   A camera de perto nao alcanca esta faixa -- ela existe pro plano geral
    #   do fim de ciclo, que recua pra 100 studs e mostra o estudio inteiro.
    #   Por isso a letra e' GIGANTE e o texto e' curto: e' o unico momento em
    #   que ela aparece, e aparece por 3 segundos.
    #
    #   Nada que o espectador PRECISE ler mora aqui. Se um dia voce escrever
    #   uma instrucao nesta peca, ela vai passar a live inteira fora do quadro. ]]
    filhos = [
        {
            "name": "PontoAoVivo",
            "className": "Frame",
            "properties": {
                "Size": udim2(0.022, 0.075),
                "Position": udim2(0.335, 0.175),
                "BackgroundColor3": ACENTO,
                "BorderSizePixel": 0,
            },
            "children": [_redondo(0.5)],
        },
        texto("AoVivo", 0.16, 0.11, "AO VIVO", BRANCO,
              alinhar="Left", x=0.372, largura=0.3),
        texto("Marca", 0.36, 0.34, "SUA SKIN NO PALCO", BRANCO,
              x=0.05, largura=0.9),
        texto("Assinatura", 0.73, 0.15, "COMENTE \u2022 GANHE DESTAQUE \u2022 DANCE",
              AMARELO, fonte="GothamMedium", x=0.05, largura=0.9),
    ]
    # Menos pixels por stud: e' uma peca grande, vista de longe, e 26 aqui
    # dobraria a textura da GUI sem ninguem nunca ver a diferenca.
    return _superficie("TelaSuperior", filhos, pixels=12)


def parede_de_led():
    #[[ AS MEDIDAS DO TELAO SAO CONTRATO COM A CAMERA.
    #
    #   O Camera.client.luau MEDE esta peca em tempo de execucao pra garantir
    #   que ela cabe no quadro, e o Config.TELAO guarda os mesmos numeros como
    #   reserva. Mexer no tamanho ou na posicao aqui muda o enquadramento da
    #   live inteira -- e o teste em roblox/testes/enquadramento.spec.luau usa
    #   estes valores. Mexeu aqui? Rode o TESTAR-TUDO.bat.
    #
    #   `Telao` e' SO' A FAIXA DE BAIXO (ver o bloco no topo desta secao). O
    #   nome ficou com ela de proposito: e' o que a camera procura, e e' a
    #   parte que carrega a mensagem. ]]
    meio_telao = BASE_TELAO + ALTURA_TELAO / 2
    telao = peca("Telao", (148, ALTURA_TELAO, 4), (0, meio_telao, -74),
                 PRETO_TELA, "SmoothPlastic")
    telao["children"] = [tela_do_telao()]

    alto = TOPO_PAREDE - TOPO_TELAO
    superior = peca("PainelSuperior", (148, alto, 4),
                    (0, TOPO_TELAO + alto / 2, -74), PRETO_TELA,
                    "SmoothPlastic")
    superior["children"] = [painel_superior()]

    # A faixa de baixo nao leva SurfaceGui nenhuma: ela passa a live inteira
    # atras da galera, e uma GUI que ninguem ve' e' textura desenhada a' toa.
    baixo = BASE_TELAO - BASE_PAREDE
    inferior = peca("PainelInferior", (148, baixo, 4),
                    (0, BASE_PAREDE + baixo / 2, -74), PRETO_TELA,
                    "SmoothPlastic")

    itens = [inferior, telao, superior]

    #[[ Os fios que separam as tres telas.
    #
    #   Sem eles as pecas pretas encostam e a parede volta a ser um bloco so' --
    #   e ai' a janela do meio, que e' a unica que fala, nao se distingue de
    #   nada. Com os fios, o olho le' uma FAIXA acesa entre duas apagadas, que
    #   e' exatamente o que ela e'. ]]
    for i, y in enumerate((BASE_TELAO, TOPO_TELAO)):
        itens.append(peca(f"FrisoDivisor{i}", (150, 0.7, 4.6),
                          (0, y, -74), ACENTO, "Neon"))

    #[[ A moldura: grafite, fina, so' pra a tela ter uma borda contra o
    #   ciclorama claro. Sem ela o preto do telao encosta direto no bege da
    #   parede e o contraste fica duro demais.
    #
    #   As laterais TERMINAM ANTES do topo e da base (52 de altura em vez de
    #   58), e nao por estilo: com todas as quatro chegando na mesma altura, o
    #   topo da lateral e o topo da barra de cima disputam o plano y=59 no
    #   canto -- e o canto da moldura pisca. Encaixadas por dentro, cada face
    #   de cima fica sozinha na altura dela. ]]
    itens += [
        peca("MolduraTopo", (156, 3, 5), (0, 57.5, -74), GRAFITE),
        peca("MolduraBase", (156, 3, 5), (0, 2.5, -74), GRAFITE),
        peca("MolduraEsq", (3, 52, 5), (-75.5, 30, -74), GRAFITE),
        peca("MolduraDir", (3, 52, 5), (75.5, 30, -74), GRAFITE),
    ]

    #[[ PAINEIS DE MADEIRA nas laterais do telao.
    #
    #   No lugar das barras de LED coloridas do cenario anterior. As barras
    #   ficavam nas pontas, ou seja, exatamente na parte do telao que o video
    #   em pe' CORTA -- eram luz gasta em pixels que ninguem ve'. A madeira
    #   faz o servico que importa: encosta o set no ciclorama sem chamar
    #   atencao. ]]
    for lado, sinal in (("Esq", -1), ("Dir", 1)):
        itens.append(peca(f"PainelMadeira{lado}", (46, 58, 4),
                          (sinal * 101, 30, -74), MADEIRA, "WoodPlanks"))
        for i in range(5):
            itens.append(peca(f"FrisoPainel{lado}{i}", (0.6, 54, 4.4),
                              (sinal * (80 + i * 10.5), 30, -74),
                              MADEIRA_ESC, "WoodPlanks"))
        # Uma faixa de acento vertical, fina, encostada no telao.
        itens.append(peca(f"AcentoLateral{lado}", (0.8, 52, 4.6),
                          (sinal * 77.6, 30, -74), ACENTO, "Neon"))
    return pasta("ParedeDeLED", itens)


# ═══════════════════════ 4. A GRADE DE LUZ ═══════════════════════
#
# Trelica de estudio com SOFTBOX, e nao refletor colorido.
#
# O cenario antigo tinha 16 refletores com lentes Neon coloridas apontando pra
# baixo. Aquilo e' iluminacao de show, e ela briga com o produto: o jogo inteiro
# existe pra mostrar a SKIN das pessoas, e luz colorida repinta a roupa de todo
# mundo. Softbox branco faz o oposto -- entrega a cor real de cada avatar.

def grade_de_luz():
    itens = []

    # As quatro torres e as vigas.
    for nome, x, z in (("EsqFundo", -92, -66), ("EsqFrente", -92, 66),
                       ("DirFundo", 92, -66), ("DirFrente", 92, 66)):
        itens.append({
            "name": f"Torre{nome}",
            "className": "TrussPart",
            "properties": {
                "Size": [2.0, 74.0, 2.0],
                "CFrame": [float(x), 37.0, float(z),
                           1.0, 0, 0.0, 0, 1, 0, -0.0, 0, 1.0],
                "Anchored": True, "Locked": True, "CanCollide": False,
                "CanTouch": False, "CanQuery": False, "CastShadow": False,
                "Color": GRAFITE,
            },
        })
    #[[ As vigas LATERAIS correm 1 stud abaixo das transversais.
    #
    #   Numa grade de trelica de verdade e' assim mesmo (uma direcao apoia na
    #   outra), e aqui isso resolve de quebra o canto piscando: com as quatro
    #   na mesma altura, os topos se cruzam no mesmo plano nos quatro cantos. ]]
    itens += [
        peca("VigaFundo", (184, 3, 3), (0, 75.5, -66), GRAFITE_CLARO, "Metal"),
        peca("VigaFrente", (184, 3, 3), (0, 75.5, 66), GRAFITE_CLARO, "Metal"),
        peca("VigaEsq", (3, 3, 132), (-92, 74.5, 0), GRAFITE_CLARO, "Metal"),
        peca("VigaDir", (3, 3, 132), (92, 74.5, 0), GRAFITE_CLARO, "Metal"),
    ]

    #[[ OS SOFTBOX.
    #
    #   Caixa grafite + face branca grande e fosca. O "grande e fosco" e' o que
    #   define um softbox: fonte larga faz sombra suave, e sombra suave e' o
    #   que deixa um rosto legivel na compressao do TikTok.
    #
    #   A face e' Neon com cor QUENTE na frente e FRIA no fundo -- a receita de
    #   luz de tres pontos, resumida: a frente entrega a cor da pele e da
    #   roupa, o contra-luz separa o boneco do ciclorama. Isso NAO ilumina de
    #   verdade (Neon nao emite luz no Roblox); quem ilumina e' o Lighting do
    #   default.project.json. Aqui e' o objeto que aparece no quadro. ]]
    for i in range(7):
        x = -78 + i * 26
        itens.append(peca(f"SoftboxFrente{i}", (11, 3, 8), (x, 71, 66), GRAFITE))
        itens.append(peca(f"LuzFrente{i}", (10, 0.6, 7), (x, 69.3, 66),
                          LUZ_QUENTE, "Neon"))
    for i in range(5):
        x = -70 + i * 35
        itens.append(peca(f"SoftboxFundo{i}", (11, 3, 8), (x, 71, -66), GRAFITE))
        itens.append(peca(f"LuzFundo{i}", (10, 0.6, 7), (x, 69.3, -66),
                          LUZ_FRIA, "Neon"))
    return pasta("Luzes", itens)


# ═══════════════════════ 5. O SET LATERAL ═══════════════════════
#
# O que enche as laterais do quadro sem competir com a formacao.
#
# No lugar das caixas de som e da arquibancada (equipamento de show), o que um
# estudio tem: painel acustico, planta, e um praticavel de madeira. Sao objetos
# que a vista reconhece como "lugar onde se grava" e que nao pedem atencao.

def set_lateral():
    itens = []
    for lado, sinal in (("Esq", -1), ("Dir", 1)):
        # Painel acustico: uma grade de quadrados grafite. E' a textura de
        # fundo mais associada a estudio que existe.
        for linha in range(4):
            for col in range(5):
                itens.append(peca(
                    f"Acustico{lado}{linha}{col}", (9, 9, 1.5),
                    (sinal * 96, 6 + linha * 10.5, -30 + col * 10.5),
                    GRAFITE if (linha + col) % 2 == 0 else GRAFITE_CLARO,
                    "Fabric"))

        # Praticavel de madeira, com uma faixa mais escura no topo. A faixa
        # ENTRA no praticavel (nao encosta): duas faces horizontais no mesmo
        # plano piscam, e este e' o mesmo cuidado do chao la' em cima.
        itens.append(peca(f"Praticavel{lado}", (26, 6, 46),
                          (sinal * 92, 3, 78), MADEIRA, "WoodPlanks"))
        itens.append(peca(f"PraticavelTopo{lado}", (26.6, 1.2, 46.6),
                          (sinal * 92, 5.8, 78), MADEIRA_ESC, "WoodPlanks"))

        # Uma planta: vaso + folhagem em blocos. Nao e' enfeite gratuito --
        # e' o unico verde do cenario, e verde e' o que impede um set neutro
        # de parecer um escritorio vazio.
        itens.append(peca(f"Vaso{lado}", (7, 8, 7), (sinal * 84, 4, 108),
                          CONCRETO_ESC, "Concrete"))
        for i, (dy, tam) in enumerate(((9, 9), (14, 7), (18, 4.5))):
            itens.append(peca(f"Folha{lado}{i}", (tam, tam * 0.8, tam),
                              (sinal * 84, dy, 108), rgb(74, 106, 68), "Grass"))
    return pasta("Set", itens)


# ═══════════════════════ Montagem ═══════════════════════

# ═══════════════════ A CONFERENCIA DO CHAO PISCANDO ═══════════════════
#
# Duas superficies horizontais na MESMA altura, uma sobre a area da outra,
# fazem a placa de video alternar entre elas a cada quadro. O chao PISCA -- e
# pisca mais quanto mais a camera se mexe, que numa live e' o tempo inteiro.
#
# O defeito e' facil de reintroduzir (basta encostar uma peca nova no piso) e
# IMPOSSIVEL de ver no JSON: os numeros parecem certos, e o sintoma so' aparece
# com o jogo rodando. Por isso a geracao FALHA aqui em vez de avisar -- um mapa
# que pisca nao deve chegar ao arquivo.
#
# So' olha as faces de cima e de baixo: as verticais tambem podem brigar, mas
# na pratica elas nao aparecem no quadro desta live (a camera esta' sempre
# acima, olhando pra baixo).
FOLGA_MINIMA = 0.25


def _planos(peca_json):
    p = peca_json["properties"]
    x, y, z = p["CFrame"][0], p["CFrame"][1], p["CFrame"][2]
    sx, sy, sz = p["Size"]
    return {
        "nome": peca_json["name"],
        "x0": x - sx / 2, "x1": x + sx / 2,
        "z0": z - sz / 2, "z1": z + sz / 2,
        "baixo": y - sy / 2, "cima": y + sy / 2,
    }


def conferir_coplanares(mapa):
    todas = []
    for grupo in mapa["children"]:
        for p in grupo["children"]:
            if p["className"] == "Part":
                todas.append(_planos(p))

    brigas = []
    for i, a in enumerate(todas):
        for b in todas[i + 1:]:
            # Sem sobreposicao no chao? Entao nao ha' como brigarem.
            if a["x1"] <= b["x0"] or b["x1"] <= a["x0"]:
                continue
            if a["z1"] <= b["z0"] or b["z1"] <= a["z0"]:
                continue
            #[[ SO' TOPO CONTRA TOPO.
            #
            #   Duas faces viradas pro MESMO lado na mesma altura brigam: a
            #   placa de video nao tem como decidir qual esta' na frente.
            #
            #   Topo contra FUNDO nao briga, e essa distincao evita uma
            #   enxurrada de falso positivo: uma peca empilhada em cima da
            #   outra encosta fundo-com-topo por construcao, e a face de baixo
            #   da de cima nunca e' desenhada (ela esta' de costas pra camera,
            #   e tapada pela peca de baixo). Sem esta regra o verificador
            #   reprovava o cenario inteiro -- inclusive a moldura do telao, que
            #   esta' certa.
            #
            #   E so' `cima`: a camera desta live esta' sempre acima olhando
            #   pra baixo, entao duas faces de FUNDO coincidentes nunca chegam
            #   a aparecer no quadro. ]]
            d = abs(a["cima"] - b["cima"])
            if d < FOLGA_MINIMA:
                brigas.append(
                    f"{a['nome']} e {b['nome']}: os dois topos em "
                    f"y={a['cima']:.2f} (diferenca {d:.3f})")
    return brigas


def main():
    mapa = {
        "className": "Folder",
        "children": [
            chao(),
            ciclorama(),
            parede_de_led(),
            grade_de_luz(),
            set_lateral(),
        ],
    }

    brigas = conferir_coplanares(mapa)
    if brigas:
        print("SUPERFICIES QUE VAO PISCAR (nao gravei o arquivo):")
        for b in brigas:
            print("  " + b)
        raise SystemExit(1)

    with io.open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
        f.write("\n")

    total = sum(len(p["children"]) for p in mapa["children"])
    print(f"cenario gerado: {len(mapa['children'])} grupos, {total} pecas")
    for p in mapa["children"]:
        print(f"  {p['name']:<14} {len(p['children'])} pecas")
    print("nenhuma superficie coplanar -- o chao nao vai piscar")


main()
