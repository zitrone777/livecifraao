# Instalação e uso

Guia completo, do zero até a live no ar.

---

## Pré-requisitos

| O quê | Por quê | Como conseguir |
|---|---|---|
| **Windows 10 ou 11** | Os `.bat` do kit são de Windows | — |
| **Python 3.10+** | Lê o chat da sua live | O `INSTALAR.bat` baixa e instala sozinho |
| **Roblox Studio** | É onde o jogo roda | https://create.roblox.com/ |
| **Conta no TikTok** | A live tem que ser sua | — |
| **Internet** | Chat do TikTok + avatares do Roblox | — |

Rojo **não** está nessa lista de propósito: ele vem dentro do kit
(`ferramentas\rojo.exe`), e o jogo já vem montado. Ele só é necessário para
**editar** o código.

---

## 1. Instalar

1. Clique com o **botão direito** no `.zip` → **Extrair Tudo**.
2. Abra a pasta que apareceu e dê dois cliques em **`INSTALAR.bat`**.
3. Espere terminar (1 a 5 minutos na primeira vez).

> **Não rode o `INSTALAR.bat` de dentro do ZIP.** O Windows copia só aquele
> arquivo para uma pasta temporária, o resto do kit fica para trás, e o erro que
> aparece não tem nada a ver com a causa. O instalador detecta isso e avisa.

### Conferir se ficou tudo certo

Dê dois cliques em **`VERIFICAR.bat`**. Ele confere, um a um:

- os arquivos do kit
- o Python e a versão dele
- a biblioteca do TikTok (pelo *import*, não pelo `pip` — com dois Pythons na
  máquina, o `pip` diz que está tudo certo e o kit quebra na primeira live)
- o Rojo: se existe, se **executa**, e qual versão
- se o projeto do jogo **monta**
- o plugin do Rojo dentro do Studio
- as portas 8000 e 34872, dizendo **qual programa** está ocupando cada uma
- o Roblox Studio

Cada item que falha vem com o que fazer.

---

## 2. Testar sem live

Dê dois cliques em **`TESTAR.bat`**. Ele inventa comentários e presentes para
você ver o jogo funcionando e mexer no painel à vontade, sem ninguém assistindo.

**Faça isso antes da primeira live de verdade.** Configurar no ar, com gente
assistindo, é o caminho mais rápido para uma live ruim.

---

## 3. Live de verdade

Dê dois cliques em **`INICIAR-LIVE.bat`**. Ele abre, nesta ordem:

| Janela | O que é | Pode fechar? |
|---|---|---|
| `1 - SERVIDOR DA LIVE` | O meio de campo entre o TikTok e o Roblox | **Não** |
| `2 - PONTE DO TIKTOK` | Lê o chat da sua live | **Não** |
| `0 - Rojo` | Só para editar o código | Sim |
| Navegador (painel) | Onde você controla tudo | Sim, dá para reabrir |
| Roblox Studio | O jogo | **Não** |

Quando o Studio abrir, **aperte PLAY** (o triângulo azul no topo).

> O jogo tem que rodar no **Studio em modo Play**. O jogo *publicado* roda na
> nuvem da Roblox e não alcança o seu PC — com ele, nada aparece, e não há
> configuração que resolva.

---

## 4. Conectar à live do TikTok

No painel (`http://localhost:8000/painel`), aba **Conexão**:

1. Digite o seu `@` (sem o arroba, ou com — tanto faz).
2. Clique em **Conectar**.
3. O crachá mostra o estado real:

| Crachá | O que significa |
|---|---|
| `CONECTADA` | Chegando comentário e presente |
| `CONECTANDO...` | Falando com o TikTok agora |
| `A CONTA NÃO ESTÁ AO VIVO` | Está tudo certo; abra a live no TikTok. Ele conecta sozinho |
| `ERRO` | Leia a linha abaixo do crachá — ela diz o quê |
| `DESCONECTADA` | Você não pediu para conectar ainda |

Trocar de conta **não** exige fechar nada: mude o `@` e clique em Conectar de
novo.

---

## 5. Usar o painel

### Conexão
Estado da live, conta conectada, e os botões de conectar/desconectar. Também
tem o **teste sem gastar moeda**: informe um nick do Roblox que exista e dispare
qualquer presente — ele passa pelo mesmo caminho de um presente de verdade.

### Presentes
Uma ficha por presente. Tudo que está aqui é **exatamente** o que o jogo aplica.

| Campo | O que faz |
|---|---|
| **Nome / ~moedas** | Só para você se achar no painel |
| **ID do TikTok** | **Vence o nome.** Veja o ID de cada presente na aba Logs |
| **Nomes que o TikTok pode mandar** | Os apelidos, separados por vírgula |
| **Tamanho ao nascer** | De que tamanho o boneco aparece (0,5 a 4) |
| **Crescimento** | Quanto **soma** no boneco de quem já está na tela |
| **Segura a câmera** | Segundos em que ninguém mais nasce depois deste |
| **Cinemática** | Segundos de close (desligado por padrão no Config) |
| **Prioridade** | Quem tem número maior fura a fila |
| **Brilho** | Força da aura, 0 a 5 |
| **Chuva** | Segundos cuspindo mais avatares da mesma pessoa |
| **Derruba todo mundo** | Segundos varrendo a formação |
| **Colosso** | Um gigante atrás da formação (0 = normal) |
| **Troca a dança de todos** | Segundos com a formação inteira em outra dança |
| **Cor / Dança** | Cor do nome e da aura; passo que este avatar dança |

**Por que cadastrar o ID:** o nome do presente muda de país para país. A mesma
rosa chega como `Rose` para uns e `Rosa` para outros. O ID não muda nunca. A aba
**Logs** mostra o ID de cada presente que chegar na sua live, e a seção
*"Presentes que chegaram nesta sessão"* tem um botão **Cadastrar** que cria a
ficha já preenchida.

**Presente que você não cadastrou continua funcionando**: ele cai nas **faixas
de preço**, pelo valor em moedas. É isso que faz o kit funcionar com um presente
que o TikTok lançou ontem.

### Jogadores
Quem participou: `@` do TikTok, nick do Roblox, se está na tela, **tamanho atual
do boneco** (medido dentro do jogo, não previsto), presentes e moedas, e quando
foi a última interação.

### Logs
Comentários lidos, nicks detectados, avatares criados, presentes com ID, erros e
conexões — da ponte **e** de dentro do jogo, na mesma lista, com filtro.

### Formação e câmera

| Ajuste | O que faz |
|---|---|
| **Avatares antes de recomeçar** | Quantos cabem antes de a formação limpar |
| **Bonecos por fileira** | Muda a régua da grade (fecha o ciclo na hora) |
| **Máximo de bonecos por combo** | Teto de avatares que um combo único rende |
| **Ao receber um presente** | `Personagem novo` (padrão) / `Crescer` / `As duas coisas` |
| **Tamanho máximo do avatar** | Até onde um boneco pode crescer |
| **Duração da animação** | Quanto o crescimento demora |
| **Vídeo em pé (9:16)** | Composição para TikTok Live / OBS em retrato |
| **Distância / Altura / FOV** | Ponto de partida do enquadramento |
| **Recuo no plano geral** | Distância no plano aberto do fim do ciclo |

> A câmera **calcula** o enquadramento: ela garante que o telão e o avatar
> cabem os dois no quadro, afastando-se sozinha quando precisa. Ela nunca chega
> mais perto do que a distância que você pediu.

> **O que "o telão" quer dizer aqui.** A parede de LED são duas peças: a faixa
> de baixo (`Telao`, y 4..21) carrega a mensagem e é a que a câmera promete
> enquadrar; a de cima (`PainelSuperior`) é enfeite de plano aberto. Se você
> **aumentar a faixa de baixo** no Studio, a câmera recua para caber o topo
> novo — e o plano de perto se perde. É o preço de uma lente baixa, e ele é
> visível: rode o `TESTAR-TUDO.bat` depois de mexer no mapa.

### O que o telão mostra

A coluna do meio **vira página** a cada poucos segundos: o convite da live
("comente seu nick") e, entre um e outro, **um presente de cada vez — com o que
ele faz** ("você entra gigante", "derruba todo mundo"). Nos lados, só visíveis
em 16:9, ficam os quatro presentes do catálogo com o mesmo par nome + efeito.

Nada disso está escrito no mapa: nome, preço e efeito saem do **catálogo do
painel**. Desligou o furacão do óculos? O telão para de prometer furacão na
volta seguinte. É a regra de sempre — um telão que mente sobre o que aceitar é
pior que um telão sem lista.

---

## 6. Overlays para o OBS

Fonte de Navegador, com estes endereços:

```
http://localhost:8000/placar.html?tipo=moedas
http://localhost:8000/placar.html?tipo=curtidas
http://localhost:8000/placar.html?tipo=presenca
```

---

## 7. Comandos de teste no chat

Digite no chat da **sua** live para disparar o efeito de graça. Só funcionam
para você (o `@` que está conectado):

```
!teste     presente barato
!medio     presente medio
!grande    presente grande
!enorme    derruba a formacao inteira
!lenda     chuva de avatares por 30s
```

Comente o seu nick antes, ou mande junto: `!lenda SeuNickDoRoblox`.

---

## Problemas comuns

### "Apertei Play e não acontece nada"

Rode o **`VERIFICAR.bat`**. Ele separa as oito causas possíveis. As mais comuns:

| Sintoma | Causa | Solução |
|---|---|---|
| Aviso na tela do jogo: *LIGUE AS REQUISIÇÕES HTTP* | HttpService desligado | No Studio: **Home → Game Settings → Security → Allow HTTP Requests** |
| Aviso: *O SERVIDOR DA LIVE NÃO RESPONDE* | A janela preta fechou | Feche tudo e rode o `INICIAR-LIVE.bat` de novo |
| Painel diz *Ponte: nunca falou* | A ponte não subiu | Veja a janela `2 - PONTE DO TIKTOK` |
| Tudo verde e a tela vazia | Ninguém comentou um **nick do Roblox** | Normal. Só quem comenta o próprio nick entra |

### "O chat está andando e não aparece ninguém"

Só vira avatar o comentário que **é** um nick do Roblox — a graça é mostrar a
skin da pessoa. "oi", "kkkk" e "top" não viram nada, de propósito. Confira na
aba **Logs**: cada nick lido aparece lá, e nick que não existe no Roblox aparece
com aviso.

### "O Rojo não conecta"

1. O plugin está instalado? O `VERIFICAR.bat` responde.
2. Se o plugin veio com `localhost` e o Connect falha, **troque por
   `127.0.0.1`**. São o mesmo computador, mas alguns Windows resolvem
   `localhost` primeiro pelo IPv6 e o Rojo escuta em IPv4.
3. Porta 34872 ocupada? O `VERIFICAR.bat` diz **qual programa** está segurando.

### "Mudei o código e nada mudou"

O Studio carrega o código **uma vez**, ao abrir o arquivo. Apertar Play de novo
não recarrega. Feche o Studio **inteiro** e rode o `ABRIR-JOGO.bat`.

### "O rojo.exe não executa"

É antivírus, em praticamente todos os casos — executável baixado da internet e
sem assinatura é o perfil clássico de falso positivo. Restaure da quarentena e
marque como permitido. **Alternativa:** se você já tem Rojo instalado (Rokit,
Aftman, Foreman ou solto no PATH), o kit usa esse automaticamente.

### "Mudei no painel e o jogo faz outra coisa"

Não deveria mais acontecer: o servidor **corta** os valores gravados pelos
mesmos limites que o jogo aplica, então o painel mostra o número que vai valer.
Se você digitar 10 num campo cujo teto é 4, ao salvar ele volta como 4 — isso é
o painel dizendo a verdade, e não um bug.

Os ajustes levam **até 5 segundos** para chegar no jogo e na ponte.

---

## Para quem vai editar o código

```bash
TESTAR-TUDO.bat
```

Roda as quatro verificações, sem abrir o Studio (uns 15 segundos):

1. **Regras** — presentes, leitura de nick, ajustes, limitador de taxa
2. **Enquadramento** — telão e avatares no quadro, em 16:9 e 9:16
3. **Cenário** — superfícies coplanares (o defeito do "chão piscando")
4. **Build** — o jogo monta?

Os quatro erros que esses testes pegam têm uma coisa em comum: **nenhum deles dá
mensagem de erro no Studio.** Eles aparecem como "a rosa ficou do tamanho da
galáxia", "o telão está cortado", "o chão pisca" e "mudei o código e nada mudou".

### O mapa

O `Cenario.model.json` é **gerado**, não editado à mão:

```bash
python ferramentas\gerar-cenario.py
```

A paleta e as medidas ficam no topo do script. Ele **recusa** gravar se
encontrar duas superfícies horizontais na mesma altura — é o que faz o chão
piscar.

### Ver o enquadramento sem abrir o Studio

```bash
python ferramentas\previa-da-camera.py
```

Gera SVGs em `previas\` com a mesma matemática da câmera do jogo: 16:9, 9:16,
formação cheia e presente grande em destaque.

---

## Onde fica cada coisa

```
INSTALAR.bat        instala Python, bibliotecas e Rojo
VERIFICAR.bat       diagnostico completo, item por item
TESTAR.bat          live de mentira, para configurar sem publico
INICIAR-LIVE.bat    a live de verdade
ABRIR-JOGO.bat      remonta o jogo e abre o Studio
TESTAR-TUDO.bat     os testes automaticos

config/ajustes.json    tudo que o painel salva
ponte/                 le' o TikTok e traduz em spawns
  regras.py            os efeitos de fabrica e os tetos
  nicks.py             acha o nick do Roblox no meio do chat
  painel.py            le' a configuracao do painel
  testes.py            a suite de testes
servidor/              o meio de campo + o painel
  web/painel.html      o painel
roblox/                o jogo
  src/ReplicatedStorage/Config.luau         camera, dancas, formacao
  src/ReplicatedStorage/Enquadramento.luau  a conta do enquadramento
  src/ServerScriptService/Principal.*       o maestro
  src/Workspace/Cenario.model.json          o mapa (GERADO)
  testes/                                   testes do enquadramento
ferramentas/
  rojo.exe             leva o jogo pro Studio
  luau.exe             roda os testes de Luau
  gerar-cenario.py     gera o mapa
  previa-da-camera.py  renderiza o enquadramento
```
