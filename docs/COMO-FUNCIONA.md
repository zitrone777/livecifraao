# Como funciona por dentro

Documento técnico. É o mapa pra você mexer no kit sem quebrar nada — e pra
responder ticket sem adivinhar.

---

## O desenho geral

```
  TikTok Live
      │  (biblioteca TikTokLive)
      ▼
  ponte/ponte.py ──────── POST /eventos ────────▶ servidor/servidor.py
   • acha nick no chat                             (porta 8000)
   • resolve nick → UserId                            │
   • aplica regras de presente                        │  fila com cursor
   • segura o ritmo                                   │
                                                      │
  painel (navegador) ◀──── GET/POST /ajustes ─────────┤
  overlay do OBS    ◀──── GET /placar ────────────────┤
                                                      │
                              GET /eventos?desde=N     │
  Roblox Studio (Play) ◀───────────────────────────────┘
   • monta a skin real
   • posiciona na grade
   • move a câmera
```

## A pergunta central: por que o jogo *pergunta*?

O Roblox **não fala WebSocket**, e o `HttpService` só faz requisição de **saída**,
para URLs públicas. Não existe jeito de o jogo ser *avisado* de que alguém
comentou.

Então o jogo pergunta, uma vez por segundo. E é por isso que existe o **cursor**:
cada resposta diz até onde o jogo já leu, e a pergunta seguinte continua dali.
Sem ele, ou o jogo receberia tudo de novo a cada segundo, ou perderia o que
chegou entre duas perguntas.

Um servidor de jogo que sobe no meio da live **se ancora no fim da fila** em vez
de receber o histórico — senão a primeira coisa que ele faria era spawnar uma
multidão de gente que já foi embora.

---

## As rotas do servidor

| Rota | Quem chama | Chave | O que faz |
|---|---|---|---|
| `POST /eventos` | ponte | escrita | põe spawns na fila |
| `GET /eventos?desde=N` | Roblox | leitura | devolve o que chegou depois de N |
| `GET/POST /ajustes` | painel, ponte, Roblox | — | a configuração |
| `POST /placar` | Roblox | leitura | publica os rankings |
| `GET /placar` | overlay do OBS | — | lê os rankings |
| `POST /camera` | Roblox | leitura | avisa em quem a câmera parou |
| `GET /camera` | (a voz, quando existir) | — | lê o foco atual |
| `POST /testar` | painel | — | injeta um presente de teste |
| `GET /testes` | ponte | escrita | busca os testes injetados |
| `GET /nick?nome=` | painel | — | resolve nick do Roblox |
| `GET /estado` | painel | — | diagnóstico |

**Duas chaves, e não uma.** A de leitura vai dentro do jogo Roblox, que qualquer
um com o arquivo do lugar consegue abrir. Se ela vazar, o pior que fazem é ler a
fila. Com a de escrita, injetariam avatares falsos na live.

---

## O caminho de um comentário

1. **A ponte recebe** `"BuilderMan"` no chat.
2. **`nicks.achar_nick`** decide se aquilo parece um nick. Filtro de *formato*,
   nunca de existência — quem decide se existe é a API do Roblox.
3. **A janela de 1 segundo** junta todos os candidatos. Numa live movimentada
   isso troca ~50 requisições por 1, porque a API aceita 100 nomes de uma vez.
4. **`nicks.Buscador`** resolve em lote, com cache de acertos *e* de erros. O
   cache de erros é o que segura a conta: o mesmo "kkkk" chega centenas de vezes.
5. **`painel.efeito_do_comentario`** diz o que esse evento vale.
6. **`Tradutor.escolher`** decide o que cabe no orçamento do segundo.
7. **POST** pro servidor.
8. **O jogo puxa**, ordena por prioridade, e spawna um de cada vez.

## O caminho de um presente

Igual, com quatro diferenças que importam:

- **O valor unitário escolhe a faixa; o combo inteiro escolhe a prioridade.** Um
  combo de 10 rosas de 1 moeda vale 10 no total, mas cada rosa continua sendo
  uma rosa de 1. Tratar o total como unitário jogaria dez rosinhas numa faixa
  que elas não compraram.
- **Presente de quem ainda não disse o nick fica guardado por 3 minutos.** Essa é
  a ordem natural: o presente é o impulso, o nick é o passo seguinte. Sem isso a
  pessoa perderia o que pagou.
- **Cada unidade do combo vira um avatar**, mas só a primeira ganha cinemática e
  só a primeira abre chuva. Sem isso, 50 rosquinhas = 50 cinemáticas em fila, e
  10 galáxias = 10 chuvas simultâneas enchendo a grade inteira.
- **Presente passa sempre** no orçamento. É raro e foi pago.

---

## A grade

Preenchimento em ordem estrita, e **slot nunca é reaproveitado**.

A versão óbvia devolveria o slot de quem saiu. Mas o buraco pode estar numa
fileira **de trás**: o próximo a chegar nasceria atrás de fileiras já formadas e
ficaria tapado por elas — justamente enquanto a câmera tenta mostrá-lo.

Com o cursor só andando pra frente, **quem chega está sempre na frente de todo
mundo**. Quando a vida de alguém acaba, o boneco some e o espaço fica vazio.
Quando a grade enche, o ciclo fecha: a câmera abre, mostra tudo, e a formação
recomeça.

**A serpentina** (fileiras ímpares invertidas) existe pra câmera não atravessar a
formação inteira toda vez que uma fileira enche.

---

## A câmera

Ela vive **no cliente**, e isso não é detalhe. A câmera no Roblox é propriedade
do cliente; movê-la do servidor exigiria replicar CFrame 60 vezes por segundo, e
o resultado no vídeo seria uma câmera aos trancos. O servidor manda só o
**evento** ("agora é cena naquele avatar, por 9 segundos") e o movimento é
calculado localmente.

Três modos: **seguir** (o padrão), **cena** (presente caro, gira em volta) e
**aberta** (fim de ciclo).

Uma cena em andamento **não pode ser interrompida** por um comentário comum que
chegou logo atrás — senão o momento que a pessoa pagou duraria até o próximo
"oi" no chat.

---

## Por que a ponte segura o ritmo

`TETO_POR_SEGUNDO = 1.8` em `ponte.py`. Ele casa com o ritmo do jogo: 0,4s de
`segura` por comentário mais ~0,15s pra montar o avatar.

Empurrar mais que isso é desperdício — o excedente só engorda a fila do jogo com
gente velha. E filtrar **na ponte**, e não no jogo, é melhor por um motivo: ali
ainda se sabe o que é presente e o que é comentário, então dá pra jogar fora
comentário antigo e nunca um presente.

Se você mexer no `segura` do comentário em `regras.py`, refaça a conta.

---

## Onde as coisas moram

```
INSTALAR.bat / INICIAR-LIVE.bat / TESTAR.bat   os três cliques do comprador
LEIA-PRIMEIRO.md                          o guia dele

config/          ajustes.json (o painel escreve aqui) e o último @ usado
ferramentas/     rojo.exe, baixado pelo INSTALAR

servidor/
  servidor.py    o servidor HTTP inteiro, stdlib pura
  web/
    painel.html  o painel de controle
    placar.html  o overlay do OBS

ponte/
  ponte.py       conexão com o TikTok + tradução de eventos
  regras.py      a tabela de fábrica: o que cada presente faz
  painel.py      lê os ajustes do servidor (com regras.py de reserva)
  nicks.py       acha nick no chat e resolve pra UserId
  deps.py        instala o que falta e explica erro em português

roblox/
  default.project.json          o projeto Rojo
  src/ReplicatedStorage/
    Config.luau                 câmera, formação, dança, rótulo
  src/ServerScriptService/
    Segredos.luau               URL e chave (nunca replicado)
    Servidor.luau               o cliente HTTP
    Formacao.luau               a grade (puro, sem efeito colateral)
    Avatares.luau               monta a skin real, dança, rótulo, brilho
    Principal.server.luau       o maestro
  src/StarterPlayerScripts/
    Camera.client.luau          os três modos de câmera
```

---

## Se quiser pôr o servidor na nuvem

Hoje ele roda em `127.0.0.1`, e o jogo alcança porque no Studio em modo Play o
servidor do jogo roda na máquina do cliente.

Pra ir pra nuvem, três coisas:

1. Hospedar `servidor/servidor.py` num lugar com HTTPS
2. Trocar `URL` e `CHAVE` em `roblox/src/ServerScriptService/Segredos.luau`
3. **Trocar as chaves por valores longos e aleatórios** — na nuvem elas passam a
   ser a única proteção real

Aí o jogo **publicado** passa a funcionar, e o cliente não precisa mais do Studio
aberto. É o upgrade natural pra vender mais caro.
