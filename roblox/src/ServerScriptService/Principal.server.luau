--!strict
--[[
	O maestro: puxa do servidor, decide quem entra, spawna e limpa no tempo.

	DOIS LACOS INDEPENDENTES, e isso e' de proposito:

	  lacoServidor   so' fala HTTP e enfileira. Nunca spawna.
	  lacoSpawn      so' spawna, um de cada vez, do mais prioritario pro menos.

	Separados porque cada um tem um ritmo proprio e um deles e' LENTO: montar um
	avatar leva centenas de milissegundos e faz HTTP por baixo. Se o spawn
	morasse dentro do laco do servidor, um combo de 50 presentes travaria a
	consulta, e a live acumularia atraso ate' nunca mais alcancar o chat.

	O TEMPO DE TELA (`vida`) FUNCIONA, E O SLOT NUNCA VOLTA

	Quando a vida de um avatar acaba, ele some -- mas o SLOT dele continua
	gasto pra sempre. Essa e' a diferenca que faz a coisa toda funcionar.

	A versao obvia devolveria o slot pra fila. So' que o buraco pode estar numa
	fileira DE TRAS: o proximo a chegar nasceria atras de fileiras ja' formadas
	e ficaria tapado por elas, justamente enquanto a camera tenta mostra-lo.

	Mantendo o slot gasto, o `vida` entrega exatamente o que o painel promete --
	quem pagou fica na tela os 300 segundos que comprou, quem so' comentou sai
	em 45 -- e quem chega esta' SEMPRE na frente de todo mundo.
]]

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Config"))
local Avatares = require(script.Parent:WaitForChild("Avatares"))
local Formacao = require(script.Parent:WaitForChild("Formacao"))
local Segredos = require(script.Parent:WaitForChild("Segredos"))
local Servidor = require(script.Parent:WaitForChild("Servidor"))

--[[ Voce so' assiste; ninguem precisa de um boneco proprio andando no meio da
	formacao.

	ATENCAO -- isto tem um efeito colateral que custa horas pra descobrir: sem
	personagem, o Roblox nao tem referencia de onde o jogador "esta'". Com
	Workspace.StreamingEnabled LIGADO (o padrao de todo lugar novo), o servidor
	entao nao envia peca NENHUMA pro cliente -- nem o chao, nem o corpo dos
	avatares. Os modelos chegam, mas so' com Humanoid e roupa, e a tela fica num
	limbo cinza que nao parece ter nada a ver com a causa.

	Por isso o default.project.json forca StreamingEnabled = false. O palco e'
	minusculo e streaming nao traria beneficio nenhum aqui. ]]
Players.CharacterAutoLoads = false

-- ─────────────────────────── Estado ───────────────────────────

local formacao = Formacao.novo()

local pasta = Instance.new("Folder")
pasta.Name = "Avatares"
pasta.Parent = workspace

-- O canal server -> client da camera. Criado aqui, em tempo de execucao, pra
-- Rojo nao precisar declarar nada: um arquivo a menos pra dar errado na
-- instalacao de quem comprou.
local canalCamera = Instance.new("RemoteEvent")
canalCamera.Name = "CameraLive"
canalCamera.Parent = ReplicatedStorage

--[[ O canal do AVISO NA TELA.

	Existe por causa do relato mais comum de quem comprou o kit: "apertei Play e
	nao acontece nada". Nao acontecer nada tem tres causas possiveis (servidor
	fechado, HttpService desligado, ninguem comentou nick) e ate' agora as tres
	se pareciam exatamente com a mesma coisa: um palco vazio.

	O aviso so' aparece quando o jogo esta' MUDO ha' varias tentativas seguidas
	-- ou seja, quando a live ja' esta' quebrada de qualquer jeito -- e some
	sozinho no instante em que o servidor responde. Ele nunca entra em cima de
	uma live que esta' funcionando. ]]
local canalAviso = Instance.new("RemoteEvent")
canalAviso.Name = "AvisoLive"
canalAviso.Parent = ReplicatedStorage

-- O ultimo aviso mostrado, pra nao reenviar a mesma frase 60 vezes por minuto.
local avisoNaTela = ""

local function avisar(titulo: string?, texto: string?)
	local marca = tostring(titulo) .. "|" .. tostring(texto)
	if avisoNaTela == marca then
		return
	end
	avisoNaTela = marca
	canalAviso:FireAllClients(titulo, texto)
end

-- LISTA, e nao mapa por tiktok_id: a MESMA pessoa pode ter varios avatares na
-- tela ao mesmo tempo, porque cada comentario spawna o seu.
local naTela: { Avatares.Avatar } = {}

--[[ tiktok_id -> o avatar MAIS RECENTE daquela pessoa.

	E' por ele que o presente sabe QUEM fazer crescer. "Mais recente" e nao "o
	primeiro" de proposito: se a pessoa comentou de novo depois de mandar
	presente, o boneco que a camera acabou de mostrar e' o novo -- e crescer o
	antigo, la' na terceira fileira, seria um presente pago acontecendo fora do
	quadro.

	Zerado junto com a formacao a cada ciclo. Sem isso ele acumularia
	referencias pra modelos destruidos e o presente da pessoa tentaria crescer
	um boneco que ja' nao existe. ]]
local porPessoa: { [string]: Avatares.Avatar } = {}

local fila: { Servidor.Spawn } = {}

local cursor = 0
-- Ate' quando nenhum avatar novo pode nascer (o `segura` de quem chegou por
-- ultimo). E' isto que da' tempo de tela pra cada um.
local seguraAte = 0
-- Ate' quando a formacao fica na danca especial. 0 = danca normal.
local especialAte = 0
--[[ Quantos COLOSSOS ja' nasceram neste ciclo.

	O colosso nao reserva slot na grade (de proposito), entao nada impedia dois
	deles de nascerem exatamente no mesmo ponto -- e dois gigantes ocupando o
	mesmo lugar viram um borrao de pernas e bracos atravessados. O numero decide
	pra que lado o proximo vai. ]]
local colossosNoCiclo = 0

--[[ O painel mudou "por fileira"? Entao a formacao precisa RECOMECAR pra regua
	nova valer.

	Sem isto a mudanca so' entraria em vigor no fim do ciclo natural -- que so'
	acontece quando a grade enche. Numa live normal isso demora tanto que, na
	pratica, mexer no painel nao fazia nada: era exatamente o sintoma de "botei 5
	e continua 10". ]]
local pedirFormacaoNova = false

-- tiktok_id -> {nick, id, moedas, curtidas, presenca}
local placar: { [string]: any } = {}

local function agora(): number
	--[[ GetServerTimeNow, e nao os.clock: em Luau o os.clock devolve tempo de
		CPU, e nao tempo de parede. Num servidor ocioso ele anda mais devagar que
		o relogio, e os avatares ficariam na tela muito alem dos segundos
		contratados -- logo os de quem pagou, que sao os que mais duram. ]]
	return workspace:GetServerTimeNow()
end

-- ─────────────────────────── O palco ───────────────────────────

--[[ O MAPA vem pronto dentro do arquivo do jogo.

	Ele mora em roblox/src/Workspace/Cenario.model.json e o Rojo o monta junto
	com o codigo: palco, parede de LED, treliças, refletores, arquibancada e
	horizonte. Por isso ele aparece no Studio ANTES de voce apertar Play -- um
	lugar que abre vazio parece um kit quebrado, e era exatamente o que
	acontecia quando o cenario nascia so' em tempo de execucao.

	O piso do palco tem o TOPO em y=0, que e' onde a formacao planta os pes
	(ver Formacao.posicao). Se voce for mexer no mapa, essa e' a unica medida
	que nao pode mudar: subir o palco 1 stud deixa cem bonecos flutuando.

	Esta funcao nao CONSTROI o mapa -- ela so' confere se ele chegou, e monta um
	chao de emergencia se nao chegou (lugar novo em branco, ou cenario apagado
	sem querer). Sem isso, os avatares dançariam no vazio. ]]
local function montarPalco()
	-- O SpawnLocation vem junto com o Baseplate de um lugar novo e nao serve
	-- pra nada aqui (ninguem tem personagem). Ficaria um podio solto no meio
	-- da grade.
	local spawn = workspace:FindFirstChildOfClass("SpawnLocation")
	if spawn then
		spawn:Destroy()
	end

	if workspace:FindFirstChild("Cenario") then
		return -- o mapa do kit chegou inteiro
	end

	--[[ O Baseplate cinza de um lugar novo: serve de chao, mas fica ABAIXO do
		mapa do kit. Se ele estiver aqui sozinho, deixa como esta' -- e' chao
		suficiente pra live nao rodar no vazio. ]]
	if workspace:FindFirstChild("Baseplate") then
		warn("[live] o mapa (Cenario) nao esta' neste lugar -- rodando so' com o "
			.. "chao padrao. Abra o jogo pelo ABRIR-JOGO.bat pra ele ser "
			.. "remontado com o mapa inteiro.")
		return
	end

	warn("[live] lugar sem chao nenhum -- montando um de emergencia. O mapa do "
		.. "kit vem do arquivo JOGO-DA-LIVE.rbxlx; rode o ABRIR-JOGO.bat.")

	--[[ Chao de emergencia, com o TOPO em y=0 exatamente como o Baseplate
		original: dois chaos empilhados no mesmo y fazem a placa de video
		alternar entre eles a cada quadro, e o chao PISCA preto sempre que a
		camera se move. ]]
	local chao = Instance.new("Part")
	chao.Name = "Baseplate"
	chao.Size = Vector3.new(512, 16, 512)
	chao.Position = Vector3.new(0, -8, 0)
	chao.Anchored = true
	chao.Locked = true
	chao.Color = Color3.fromRGB(163, 162, 165)
	chao.Material = Enum.Material.Plastic
	chao.TopSurface = Enum.SurfaceType.Smooth
	chao.Parent = workspace
end

-- ─────────────────────────── O placar ───────────────────────────

--[[ Soma por PESSOA, e nao por avatar: quem mandou 100 rosas aparece UMA vez
	com o total, e nao cem vezes ocupando o top 10 inteiro.

	Tres placares separados porque eles medem coisas diferentes e premiar tudo
	junto apaga os dois menores: as moedas do presente valem direto, a curtida
	tem o placar dela, e a presenca (comentar, seguir, compartilhar) rende 1
	ponto -- assim quem nunca gastou nada tambem aparece em algum lugar. ]]
local function contarNoPlacar(spawn: Servidor.Spawn)
	local chave = spawn.tiktok_id
	if chave == "" then
		return
	end
	local linha = placar[chave]
	if not linha then
		linha = { nick = spawn.nickname, id = spawn.roblox_id,
			moedas = 0, curtidas = 0, presenca = 0 }
		placar[chave] = linha
	end
	linha.nick = spawn.nickname
	linha.moedas += math.max(0, spawn.moedas)
	linha.curtidas += math.max(0, spawn.curtidas)
	if spawn.tipo ~= "curtida" then
		linha.presenca += 1
	end
end

local function topo(campo: string): { Servidor.LinhaDePlacar }
	local lista = {}
	for _, linha in pairs(placar) do
		if linha[campo] > 0 then
			table.insert(lista, { nick = linha.nick, id = linha.id, pontos = linha[campo] })
		end
	end
	table.sort(lista, function(a, b)
		return a.pontos > b.pontos
	end)
	while #lista > 10 do
		table.remove(lista)
	end
	return lista
end

-- ───────────────────── Limpeza e fim de ciclo ─────────────────────

local function limparFormacao()
	for _, avatar in ipairs(naTela) do
		if avatar.modelo and avatar.modelo.Parent then
			avatar.modelo:Destroy()
		end
	end
	table.clear(naTela)
	table.clear(porPessoa)
	formacao:limpar()
	colossosNoCiclo = 0
	-- O painel precisa saber que ninguem tem avatar agora, senao a coluna
	-- "tamanho" continua mostrando os numeros do ciclo passado pra sempre.
	task.spawn(Servidor.limparTamanhos)
end

--[[ Reacomoda TODO MUNDO nas posicoes que a formacao calculou agora.

	Chamado depois de qualquer coisa que mude a geometria da grade: um avatar
	que nasce, um que cresce. A formacao ja' recalculou os CFrames; aqui a
	gente so' move os bonecos pra onde eles passaram a pertencer.

	Planta pelo `escalaVisual` e nao pelo `escala`: durante a animacao de
	crescimento os dois sao diferentes, e usar o tamanho de destino levantaria
	o boneco do chao ate' o corpo alcancar -- ele cresceria flutuando. ]]
local function reacomodar()
	for _, avatar in ipairs(naTela) do
		if avatar.indice > 0 and avatar.modelo.Parent then
			local posicao = formacao:posicaoDe(avatar.indice)
			if posicao then
				Avatares.plantar(avatar.modelo, posicao, avatar.escalaVisual)
			end
			--[[ A fileira vai junto, e nao so' na hora de nascer: quando
				alguem cresce, quem vinha depois pode mudar de fileira. Um
				rotulo com a fileira antiga ficaria aceso (ou apagado) na
				fileira errada
				de nomes -- um nome solto no meio de uma fileira sem nomes. ]]
			Avatares.marcarFileira(avatar.modelo, formacao:fileiraDe(avatar.indice))
		end
	end
	-- O cliente precisa saber quantas fileiras existem pra fechar a volta do
	-- qual e' a da frente. Atributo, e nao RemoteEvent: replica sozinho.
	workspace:SetAttribute("FileirasNaTela", formacao:fileiras())
end

--[[ O fim do ciclo: a camera abre, mostra a formacao inteira, e so' entao a
	grade e' apagada.

	O plano aberto nao e' enfeite -- e' o unico momento em que quem assiste ve'
	QUANTA gente entrou. Cortar direto pro palco vazio jogaria fora a prova de
	que a live esta' cheia, que e' o argumento que faz a proxima pessoa comentar. ]]
local function fecharCiclo()
	canalCamera:FireAllClients({
		modo = "aberta",
		centro = formacao:centro(),
		-- A camera recua a partir da FRENTE da formacao, e pra isso ela precisa
		-- saber o tamanho dela: uma live cheia de presente grande e' duas vezes
		-- mais funda que uma so' de comentarios.
		profundidade = formacao:profundidade(),
		duracao = Config.CAMERA.ABERTA_S,
	})
	task.wait(Config.CAMERA.ABERTA_S)
	limparFormacao()
	canalCamera:FireAllClients({ modo = "seguir" })
end

--[[ O FURACAO: o avatar sai varrendo a formacao e derrubando todo mundo, e no
	fim a grade recomeca.

	Feito com a fisica de verdade (desancorando as pecas) e nao com animacao: um
	tombo calculado sai sempre igual, e depois da terceira vez o publico ja'
	decorou. Com fisica, cada varrida cai diferente. ]]
local function furacao(avatar: Avatares.Avatar, segundos: number)
	local raiz = avatar.modelo:FindFirstChild("HumanoidRootPart")
	if not raiz or not raiz:IsA("BasePart") then
		return
	end

	task.spawn(function()
		local fim = agora() + segundos
		while agora() < fim and avatar.modelo.Parent do
			for _, outro in ipairs(naTela) do
				if outro ~= avatar and outro.modelo.Parent then
					local alvo = outro.modelo:FindFirstChild("HumanoidRootPart")
					if alvo and alvo:IsA("BasePart") then
						local distancia = (alvo.Position - raiz.Position).Magnitude
						if distancia < 12 then
							for _, peca in ipairs(outro.modelo:GetDescendants()) do
								if peca:IsA("BasePart") then
									--[[ A COLISAO VOLTA AQUI -- sem isto o efeito
										mais caro da live vira um defeito.

										Todo avatar nasce com CanCollide = false
										(cem bonecos colidindo se empurram e a
										formacao desmancha sozinha). So' que um
										boneco desancorado SEM colisao nao tomba:
										ele atravessa o piso do palco e cai pra
										sempre, ate' o Roblox apagar o modelo la'
										embaixo. A varrida do oculos entao nao
										derrubava a formacao -- fazia ela SUMIR
										pelo chao, e o presente de 199 moedas
										parecia um bug. ]]
									peca.CanCollide = true
									peca.Massless = false
									peca.Anchored = false
								end
							end
							local empurrao = (alvo.Position - raiz.Position).Unit
							alvo.AssemblyLinearVelocity =
								(empurrao + Vector3.new(0, 1, 0)) * 45
						end
					end
				end
			end
			task.wait(0.25)
		end
		-- A grade ficou uma bagunca de bonecos caidos: recomecar e' a unica
		-- saida honesta, e e' tambem o momento mais bonito da varrida.
		pedirFormacaoNova = true
	end)
end

-- ─────────────────────────── O spawn ───────────────────────────

--[[ Os limites do crescimento, vindos do painel.

	Lidos a cada uso, e nao guardados: e' o que faz mexer no painel valer na
	hora, sem esperar o ciclo virar. ]]
local function tamanhoMaximo(): number
	local v = tonumber(workspace:GetAttribute("TamanhoMax"))
	return math.clamp(v or Config.CRESCIMENTO.TAMANHO_MAX, 1, 12)
end

local function suavidadeDoCrescimento(): number
	local v = tonumber(workspace:GetAttribute("CrescimentoSuave"))
	return math.clamp(v or Config.CRESCIMENTO.SUAVE_S, 0, 5)
end

--[[ O que um presente faz na tela: "novo", "crescer" ou "ambos".

	Vem do painel. Qualquer valor desconhecido cai em "ambos" -- e nao num
	erro: um ajuste torto nao pode fazer os presentes pararem de funcionar no
	meio da live. ]]
local function modoDoPresente(): string
	local v = workspace:GetAttribute("PresenteFaz")
	if v == "novo" or v == "crescer" or v == "ambos" then
		return v
	end
	return Config.CRESCIMENTO.MODO
end

--[[ Depois de cada efeito, a camera olha pra ele e ninguem nasce por um tempo.

	Num lugar so' porque vale igual pro avatar que NASCE e pro que CRESCE: os
	dois sao "o momento daquela pessoa", e quem pagou pra ver o proprio boneco
	inflar merece o mesmo tempo de tela de quem pagou pra ver um nascer. Antes
	isto so' existia no caminho do nascimento, e o presente que fazia crescer
	passava despercebido -- a camera continuava em outro lugar. ]]
local function darOMomento(spawn: Servidor.Spawn, modelo: Model)
	canalCamera:FireAllClients({
		modo = if spawn.cena > 0 then "cena" else "seguir",
		alvo = modelo,
		duracao = spawn.cena,
	})

	-- Avisa a voz. Dentro de task.spawn porque isto faz HTTP: uma fala perdida
	-- nao vale segurar o laco de spawn.
	task.spawn(function()
		Servidor.avisarCamera(spawn.tipo, spawn.nickname, spawn.presente)
	end)

	if spawn.danca_geral > 0 then
		especialAte = agora() + spawn.danca_geral
		Avatares.trocarDancaDeTodos(pasta, true)
	end

	seguraAte = agora() + math.max(spawn.segura, spawn.cena)
end

--[[ O presente fez o avatar desta pessoa CRESCER. Devolve false se nao deu.

	"Nao deu" e' rotina e nao erro: a pessoa pode nao ter boneco na tela (nunca
	comentou, ou o ciclo limpou a formacao), o presente pode nao ter
	crescimento configurado, ou o avatar dela ja' pode estar no teto. Em todos
	esses casos quem chama cai no caminho do nascimento, e a pessoa ganha um
	boneco novo em vez de nada. ]]
local function crescer(spawn: Servidor.Spawn, comMomento: boolean): boolean
	if spawn.crescimento <= 0 then
		return false
	end

	local avatar = porPessoa[spawn.tiktok_id]
	if not avatar or not avatar.modelo.Parent or avatar.indice <= 0 then
		return false
	end

	local teto = tamanhoMaximo()
	--[[ NO TETO, O PRESENTE NAO E' IGNORADO -- ELE VIRA UM BONECO NOVO.

		Este `return false` e' o que impede o pior caso do produto: a pessoa que
		mais gastou na live e' justamente a que chega ao teto primeiro, e a
		partir dali cada presente novo dela nao faria absolutamente nada na
		tela. Devolvendo false, quem chama spawna outro avatar pra ela -- entao
		continuar mandando presente continua tendo efeito visivel, so' que
		agora em quantidade em vez de tamanho. ]]
	if avatar.escala >= teto - 0.01 then
		return false
	end

	local destino = math.min(avatar.escala + spawn.crescimento, teto)
	--[[ A formacao abre espaco ANTES de o corpo crescer.

		Se ela recusar (o tamanho novo nao cabe na grade), o crescimento nao
		acontece e o presente vira um boneco novo. Crescer assim mesmo poria o
		gigante por cima dos vizinhos ate' o fim do ciclo. ]]
	if not formacao:mudarEscala(avatar.indice, destino) then
		return false
	end

	Avatares.crescer(avatar, destino, suavidadeDoCrescimento(), function(atual)
		avatar.escalaVisual = atual
		local posicao = formacao:posicaoDe(avatar.indice)
		if posicao then
			Avatares.plantar(avatar.modelo, posicao, atual)
		end
		Avatares.ajustarRotulo(avatar.modelo, atual)
	end)

	-- Todo mundo se afasta pra dar lugar ao que cresceu.
	reacomodar()

	--[[ No modo "ambos" quem da' o momento e' o boneco NOVO, que nasce logo
		em seguida. Sem esta guarda, a camera olharia pro que cresceu e no
		instante seguinte pularia pro que nasceu, e o `segura` seria contado
		duas vezes pro mesmo presente -- o dobro de pausa que o painel diz. ]]
	if comMomento then
		darOMomento(spawn, avatar.modelo)
		if spawn.furacao > 0 then
			furacao(avatar, spawn.furacao)
		end
	end
	return true
end

--[[ Nasce um avatar. Devolve false quando a grade encheu (fim do ciclo). ]]
local function spawnar(spawn: Servidor.Spawn): boolean
	local ehColosso = spawn.colosso > 0
	-- A MESMA conta que o Avatares usa pra chamar o ScaleTo. Ver
	-- `Avatares.escalaDe`: os dois lados discordarem ja' custou o colosso
	-- inteiro, que nascia do tamanho de gente normal.
	local escala = Avatares.escalaDe(spawn)

	local posicao, indice
	if ehColosso then
		-- O colosso vive FORA da grade, atras de todo mundo. Nao entra na
		-- formacao: entrar faria um gigante consumir meia fileira e o ciclo
		-- fecharia cedo demais toda vez que alguem mandasse o presente caro.
		posicao = Formacao.posicaoColosso(colossosNoCiclo)
		colossosNoCiclo += 1
		indice = -1
	else
		local entrou = formacao:entrar(escala)
		if not entrou then
			return false -- a grade encheu: fim do ciclo
		end
		indice = entrou
		posicao = formacao:posicaoDe(indice) or CFrame.identity
	end

	local modelo = Avatares.criar(spawn, posicao, pasta)
	if not modelo then
		-- Nao carregou (limite da Roblox, conta apagada, rede). O lugar na
		-- grade ja' foi gasto de proposito: devolve-lo faria o proximo avatar
		-- nascer no buraco, ATRAS de quem ja' esta' na frente -- o problema que
		-- a grade so'-pra-frente existe pra evitar.
		return true
	end

	local avatar: Avatares.Avatar = {
		modelo = modelo,
		indice = indice,
		tiktok_id = spawn.tiktok_id,
		nascido = agora(),
		vida = spawn.vida,
		prio = spawn.prio,
		escala = escala,
		escalaVisual = escala,
		geracao = 0,
	}
	table.insert(naTela, avatar)
	if spawn.tiktok_id ~= "" then
		porPessoa[spawn.tiktok_id] = avatar
	end

	-- Quem entrou empurrou a grade: os que ja' estavam podem ter mudado de
	-- lugar (uma fileira nova comecou, ou este e' grande e abriu espaco).
	reacomodar()
	darOMomento(spawn, modelo)

	if spawn.furacao > 0 then
		furacao(avatar, spawn.furacao)
	end
	return true
end

--[[ O QUE FAZER COM UM EVENTO: crescer o boneco que existe, criar um, ou os dois.

	Esta e' a decisao central do produto, e ela mora aqui -- e nao na ponte --
	porque so' o jogo sabe quem esta' na tela NESTE instante. A formacao e'
	apagada a cada ciclo, entao "esta pessoa ja' tem avatar" e' uma verdade que
	muda a cada poucos minutos.

	  novo      cada presente poe um boneco NOVO na tela.
	  crescer   o presente engorda o boneco que a pessoa ja' tem. So' cria um
	            novo quando ela ainda nao esta' na tela.
	  ambos     as duas coisas (padrao).

	O PLACAR E' CONTADO UMA VEZ SO', AQUI.

	Antes ele era contado dentro do `crescer` E dentro do `spawnar`. Enquanto
	os dois eram exclusivos isso funcionava; no modo "ambos" o mesmo presente
	passaria pelos dois caminhos e as moedas entrariam em DOBRO no top 10 --
	um erro que ninguem nota olhando a tela, e que premia a pessoa errada.

	E vem ANTES de criar o avatar, de proposito: o avatar e' o que a Roblox
	pode negar (limite de requisicao, conta apagada); a participacao, nao. Quem
	pagou nao pode sumir do placar porque a API engasgou.

	Devolve false so' no caso que interessa a quem chama: a grade encheu e o
	ciclo precisa fechar. ]]
local function aplicar(spawn: Servidor.Spawn): boolean
	contarNoPlacar(spawn)

	if spawn.tipo ~= "presente" then
		return spawnar(spawn)
	end

	local modo = modoDoPresente()
	if modo == "novo" then
		return spawnar(spawn)
	end

	if modo == "crescer" then
		-- Cresceu? Acabou. Nao cresceu (a pessoa nao tem boneco, ou ja' esta'
		-- no teto)? Entao ela ganha um boneco novo, em vez de nada.
		return crescer(spawn, true) or spawnar(spawn)
	end

	-- "ambos": o que ela ja' tinha cresce, e um novo aparece. Quem da' o
	-- momento da camera e' o novo -- ele e' o que acabou de entrar em cena.
	crescer(spawn, false)
	return spawnar(spawn)
end

-- ─────────────────────────── Os lacos ───────────────────────────

--[[ Traduz o erro cru da Roblox na frase que resolve o problema.

	Sao dois casos, e a solucao de um nao serve pro outro -- por isso eles nao
	podem virar um aviso generico. O texto e' curto de proposito: ele aparece
	POR CIMA da live, e uma parede de texto no meio da transmissao e' pior que o
	problema que ela explica. ]]
local function explicar(motivo: string): (string, string)
	if string.find(motivo, "Http requests are not enabled", 1, true)
		or string.find(motivo, "HttpService", 1, true) then
		return "LIGUE AS REQUISICOES HTTP",
			"No Studio: aba HOME > Game Settings > Security > "
				.. "Allow HTTP Requests. Depois aperte Play de novo."
	end
	return "O SERVIDOR DA LIVE NAO RESPONDE",
		"A janela preta \"1 - SERVIDOR DA LIVE\" precisa estar aberta. "
			.. "Feche tudo e rode o INICIAR-LIVE.bat (ou o TESTAR.bat) de novo."
end

-- Quantas voltas mudas antes de por o aviso na tela. 5 voltas = ~5 segundos:
-- tempo de sobra pro servidor terminar de subir, e pouco o bastante pra quem
-- esta' olhando a tela receber a resposta antes de desistir.
local MUDO_ATE_AVISAR = 5

--[[ Ja' sabemos ONDE a fila esta'? Ver `ancorar` logo abaixo.

	Comeca FALSO, e nada e' puxado antes de virar verdadeiro. Isso e' a correcao
	de um defeito que so' aparecia quando alguma outra coisa dava errado -- o
	pior tipo. ]]
local ancorado = false

--[[ Pergunta ao servidor em que ponto da fila ele esta', e pula pra la'.

	POR QUE ISTO NAO PODE FALHAR EM SILENCIO

	O `cursor` comeca em 0, e 0 quer dizer "me manda desde o comeco". Numa fila
	que guarda ate' 2000 eventos, isso e' uma multidao inteira de gente que
	comentou ha' dez minutos e ja' foi embora nascendo de uma vez no primeiro
	segundo do Play.

	Antes, quando a ancoragem falhava -- o servidor demorando meio segundo a mais
	pra subir e' o bastante -- o codigo apenas AVISAVA e seguia em frente com o
	cursor em 0. O aviso ia pro Output do Studio, que ninguem esta' olhando com a
	live no ar, e o que se via era exatamente o sintoma que este kit promete que
	nao acontece: bonecos aparecendo sozinhos, sem ninguem ter comentado nada.

	Agora a falha nao anda pra frente: enquanto nao ancorar, o jogo NAO puxa. Ele
	tenta de novo a cada volta do laco, e quando o servidor responde a live
	comeca do ponto certo -- do que esta' acontecendo agora, e nao do historico. ]]
local function ancorar(): boolean
	local ancora = Servidor.ancorar()
	if not ancora then
		return false
	end
	cursor = ancora
	ancorado = true
	return true
end

local function lacoServidor()
	local mudo = 0

	while true do
		--[[ Nada de puxar antes de saber onde a fila esta'. Um servidor que
			demorou a subir deixaria o cursor em 0, e o cursor em 0 spawna o
			historico inteiro. ]]
		local spawns: { Servidor.Spawn } = {}
		if ancorado or ancorar() then
			local novoCursor, novos = Servidor.puxar(cursor)
			cursor = novoCursor
			spawns = novos
		end

		--[[ O DIAGNOSTICO. Falar SEMPRE que falha afogaria o Output; falar
			nunca era o que produzia a tela vazia sem explicacao. Fala uma vez,
			quando o silencio vira problema, e desfaz sozinho quando volta. ]]
		local ok, motivo = Servidor.estado()
		if ok then
			if mudo >= MUDO_ATE_AVISAR then
				print("[live] o servidor voltou a responder.")
			end
			mudo = 0
			avisar(nil, nil)
		else
			mudo += 1
			if mudo == MUDO_ATE_AVISAR then
				local titulo, texto = explicar(motivo)
				warn("[live] " .. titulo .. " -- " .. texto)
				warn("[live] detalhe tecnico: " .. motivo)
				avisar(titulo, texto)
			end
		end

		for _, spawn in ipairs(spawns) do
			table.insert(fila, spawn)
		end

		--[[ Ordena por prioridade, mas ESTAVEL dentro da mesma prioridade.

			table.sort do Luau nao e' estavel, entao dois comentarios com prio 0
			poderiam trocar de lugar a cada ordenacao -- e quem comentou primeiro
			perderia a vez pra quem comentou depois, aleatoriamente. Comparar
			so' quando as prioridades DIFEREM preserva a ordem de chegada. ]]
		if #fila > 1 then
			local ordem: { [any]: number } = {}
			for i, item in ipairs(fila) do
				ordem[item] = i
			end
			table.sort(fila, function(a, b)
				if a.prio ~= b.prio then
					return a.prio > b.prio
				end
				return ordem[a] < ordem[b]
			end)
		end

		-- A fila nao pode crescer sem limite. Se ela passar disso, o que sobra
		-- e' gente que comentou ha' tanto tempo que ja' saiu da live -- mostrar
		-- essas pessoas e' pior que nao mostrar.
		while #fila > 300 do
			table.remove(fila)
		end

		task.wait(Segredos.INTERVALO)
	end
end

--[[ O TETO de bonecos que podem existir ao mesmo tempo. Vem do painel.

	Ao bater nele, a formacao INTEIRA e' apagada e o ciclo recomeca do zero. E'
	o que segura o custo da live: cada avatar e' um rig R15 completo, com roupa,
	acessorio e uma animacao tocando. Cem ja' pesam; quinhentos derrubam o
	servidor do Studio, e a live cai junto. ]]
local function tetoDeBonecos(): number
	local v = tonumber(workspace:GetAttribute("TotalAvatares"))
	return math.clamp(math.floor(v or Config.MAX_AVATARES), 4, 400)
end

local function lacoSpawn()
	while true do
		--[[ TETO RIGIDO, contando os bonecos DE VERDADE na pasta.

			A grade ja' fecha o ciclo sozinha quando os slots acabam, e na live
			normal e' ela que manda. Mas existe um caminho que ESCAPA dela: o
			COLOSSO nasce fora da grade e nao reserva slot nenhum (de proposito
			-- um gigante consumindo meia fileira fecharia o ciclo cedo demais).

			Sem esta contagem, uma sequencia de presentes de colosso empilharia
			gigantes sem nunca encher a grade, e o servidor iria afundando sem
			nada no codigo dizendo por que. Contar o que EXISTE, e nao o que foi
			reservado, fecha esse buraco. ]]
		if #pasta:GetChildren() >= tetoDeBonecos() then
			pedirFormacaoNova = true
		end

		if pedirFormacaoNova then
			pedirFormacaoNova = false
			fecharCiclo()
		end

		if especialAte > 0 and agora() >= especialAte then
			especialAte = 0
			Avatares.trocarDancaDeTodos(pasta, false)
		end

		if #fila > 0 and agora() >= seguraAte then
			local spawn = table.remove(fila, 1)
			if spawn and not aplicar(spawn) then
				-- A grade encheu. Devolve o spawn pro comeco da fila: ele nao
				-- pode ser perdido so' porque chegou no instante em que o ciclo
				-- virou -- ainda mais se for um presente pago.
				table.insert(fila, 1, spawn)
				fecharCiclo()
			end
		end

		-- 0.1s e nao 0: um laco apertado demais come CPU do mesmo processo que
		-- monta os avatares, e o spawn fica MAIS lento, nao mais rapido.
		task.wait(0.1)
	end
end

local function lacoPlacar()
	while true do
		task.wait(3)
		Servidor.publicarPlacar(topo("moedas"), topo("curtidas"), topo("presenca"))
	end
end

--[[ NAO EXISTE REMOCAO POR TEMPO, E ISSO E' DELIBERADO.

	A versao anterior tirava cada avatar quando a `vida` dele acabava. Parecia
	certo e ficava HORRIVEL: comentario vivia 45s e presente 300s, entao depois
	de um minuto a formacao virava um queijo suico -- buraco no meio da terceira
	fileira, dois no fim da primeira, um bloco vago no canto. A grade so' parece
	uma PLATEIA enquanto esta' cheia; furada, parece um bug.

	Agora ninguem sai sozinho. A formacao inteira vive ate' o ciclo fechar (a
	grade encher ou bater o teto de bonecos) e ai' e' apagada de uma vez, com a
	camera aberta mostrando ela cheia antes de recomecar.

	O custo continua limitado -- e' exatamente o que o teto faz. O que se perde
	e' o campo `vida` mandar em alguma coisa; por isso ele saiu do painel, em vez
	de continuar la' enganando quem mexe nele. ]]

--[[ Le' os ajustes do painel e espelha nos atributos do workspace.

	Atributo, e nao variavel: assim o Formacao e o cliente da camera leem o valor
	novo sozinhos, sem ninguem precisar avisa-los. E' o que faz o "salvei e ja'
	valeu" do painel ser verdade tambem aqui dentro. ]]
--[[ Os ajustes do painel que viram ATRIBUTO do workspace, um por linha.

	Atributo, e nao variavel, porque quem le' varios deles e' o CLIENTE (a
	camera) e o modulo da Formacao -- e atributo replica sozinho, sem RemoteEvent
	nenhum no meio. E' o que faz o "salvei e ja' valeu" ser verdade nos dois
	lados.

	A lista e' declarativa pra adicionar um ajuste ser UMA linha aqui. Com um
	`if` escrito na mao por campo, o padrao que se repetia era esquecer de
	espelhar o novo -- e o sintoma disso e' o pior do painel: o valor aparece
	salvo na tela e o jogo continua com o antigo, sem nada indicando por que. ]]
local ESPELHADOS: { { chave: string, atributo: string, reiniciaCiclo: boolean? } } = {
	{ chave = "por_fila", atributo = "PorFila", reiniciaCiclo = true },
	{ chave = "total_avatares", atributo = "TotalAvatares" },
	{ chave = "camera_recuo", atributo = "CameraRecuo" },
	{ chave = "tamanho_max", atributo = "TamanhoMax" },
	{ chave = "crescimento_suave", atributo = "CrescimentoSuave" },
	{ chave = "camera_fov", atributo = "CameraFov" },
	{ chave = "camera_distancia", atributo = "CameraDistancia" },
	{ chave = "camera_altura", atributo = "CameraAltura" },
}

-- Os de liga/desliga vao separados: `tonumber(false)` e' nil, entao eles
-- sumiriam calados do laco acima.
local ESPELHADOS_SIMNAO: { { chave: string, atributo: string } } = {
	{ chave = "vertical", atributo = "Vertical" },
}

-- E os de TEXTO, pelo mesmo motivo: `tonumber("novo")` tambem e' nil.
local ESPELHADOS_TEXTO: { { chave: string, atributo: string } } = {
	{ chave = "presente_faz", atributo = "PresenteFaz" },
}

--[[ ═══════════ O QUE O TELAO DIZ ═══════════

	O telao tem DOIS lugares onde presente aparece, e o jogo escreve nos dois:

	  a COLUNA CENTRAL, que gira entre o convite da live e um presente de cada
	  vez (ver `lacoTelao`). E' a unica parte que sobrevive ao corte do video em
	  pe', entao e' ela que carrega a mensagem.

	  a LISTA LATERAL, quatro slots fixos que so' aparecem no 16:9.

	POR QUE ISTO E' FEITO AQUI, E NAO GRAVADO NO MAPA

	O catalogo e' editavel: voce pode cadastrar um presente novo, mudar o preco
	de outro ou desligar um -- tudo ao vivo, pelo painel. Um telao com os nomes
	gravados no arquivo do mapa passaria a anunciar presentes que nao fazem mais
	nada, ou a esconder os que fazem. Um telao que mente sobre o que aceitar e'
	pior que um telao sem lista: o espectador manda o presente errado e nao
	acontece o que ele esperava.

	Vale pro PRECO e vale, agora, pro EFEITO: a frase "o que este presente faz"
	tambem sai do catalogo, derivada dos campos do proprio presente. ]]

--[[ O QUE ESTE PRESENTE FAZ, em uma linha curta.

	A pergunta que faz alguem mandar um presente nao e' quanto custa, e' o que
	acontece na tela. "Rosquinha · 30" e' uma tabela de precos de uma coisa que
	o espectador nao sabe o que e'; "VOCE ENTRA GIGANTE" e' o convite.

	A frase e' DERIVADA dos campos do proprio presente, e nao escrita na mao em
	lugar nenhum. E' a mesma regra que vale pra lista inteira: o catalogo e'
	editavel pelo painel, entao qualquer texto fixo vira mentira no dia em que
	voce desligar o furacao do oculos. Aqui, desligou o campo, a frase muda
	sozinha.

	UMA FRASE SO', e a ordem importa: um presente caro faz varias coisas ao
	mesmo tempo (o oculos cresce, brilha, dança diferente E derruba todo mundo),
	mas na altura que o telao tem cabe UMA linha. Ganha a mais espetacular --
	que e' tambem a que a pessoa quer ver de novo. ]]
local function frasePresente(efeito: any): string
	local function num(chave: string): number
		return tonumber(efeito[chave]) or 0
	end

	if num("colosso") > 0 then
		return "VOCÊ VIRA UM COLOSSO"
	end

	--[[ O TAMANHO VEM PRIMEIRO, e o numero e' o do proprio presente.

		A escadinha de tamanho e' o que a live vende, e ela so' funciona se o
		espectador CONSEGUIR COMPARAR: "2x maior" ao lado de "3x maior" ao lado
		de "4x maior" e' uma tabela de precos que se entende sem legenda. "VOCÊ
		ENTRA GIGANTE" nos tres -- que era o que estava escrito -- apagava
		justamente a diferenca pela qual a pessoa paga a mais.

		O teto vira "O MAIOR DE TODOS" em vez de "6x": quem chega no topo nao
		precisa de numero, precisa saber que nao da' pra ir mais alto. E se um
		dia o teto mudar no painel, a frase acompanha sozinha. ]]
	local escala = num("escala")
	-- O MESMO teto que o crescimento usa (painel > Config): duas fontes pra
	-- este numero e' o telao dizendo "o maior de todos" de um boneco que ainda
	-- pode crescer, ou o contrario.
	local teto = tamanhoMaximo()
	if escala >= teto then
		return "O MAIOR DE TODOS"
	elseif escala >= 2 then
		--[[ Sem casa decimal quando e' redondo: "2x MAIOR" se le' de relance,
			"2.0x MAIOR" faz o olho parar pra conferir se aquilo e' um numero
			ou um codigo. ]]
		local rotulo = if escala % 1 == 0
			then string.format("%d", escala)
			else string.format("%.1f", escala)
		return "VOCÊ FICA " .. rotulo .. "x MAIOR"
	elseif num("furacao") > 0 then
		return "DERRUBA TODO MUNDO"
	elseif num("chuva") > 0 then
		return "CHOVEM CÓPIAS SUAS"
	elseif tostring(efeito.danca or "") ~= "" then
		return "VOCÊ DANÇA DIFERENTE"
	elseif num("cena") > 0 then
		return "A CÂMERA SÓ PRA VOCÊ"
	elseif num("brilho") > 0 then
		return "SEU BONECO BRILHA"
	end
	return "VOCÊ ENTRA NA LIVE"
end

--[[ O SEGUNDO efeito -- o espetaculo, quando existe.

	Fica separado da frase do tamanho porque os dois cabem em lugares
	diferentes: o tamanho e' a linha grande do cartao, este aqui entra junto do
	preco, em letra menor. Um presente que so' aumenta devolve "" e a linha do
	preco fica limpa, em vez de inventar um efeito que ele nao tem. ]]
local function fraseExtra(efeito: any): string
	local function num(chave: string): number
		return tonumber(efeito[chave]) or 0
	end
	if num("furacao") > 0 then
		return "derruba todo mundo"
	elseif num("chuva") > 0 then
		return "chovem cópias suas"
	elseif num("cena") > 0 then
		return "a câmera para em você"
	elseif tostring(efeito.danca or "") ~= "" then
		return "dança só sua"
	elseif num("brilho") > 0 then
		return "seu boneco brilha"
	end
	return ""
end

--[[ A lista de presentes do catalogo, agrupada e em ordem de preco.

	AGRUPA PELOS APELIDOS. No catalogo, o mesmo presente aparece uma vez por
	apelido ("rose" e "rosa" sao a mesma rosa). Sem agrupar, o telao mostraria
	"Rosa, Rosa, Rosquinha, Rosquinha" e os quatro slots se esgotariam em dois
	presentes de verdade.

	ORDENA PELO PRECO, do mais barato pro mais caro: e' a ordem em que a pessoa
	decide o que mandar, e a que faz a escadinha de valor ficar obvia sem
	precisar explicar. ]]
local function listaDePresentes(ajustes: any)
	local vistos: { [string]: boolean } = {}
	local lista = {}
	for _, efeito in pairs((ajustes and ajustes.presentes) or {}) do
		if type(efeito) == "table" then
			local grupo = tostring(efeito.grupo or "")
			if grupo ~= "" and not vistos[grupo] then
				vistos[grupo] = true
				table.insert(lista, {
					rotulo = tostring(efeito.rotulo or grupo),
					emoji = tostring(efeito.emoji or ""),
					moedas = tonumber(efeito.moedas) or 0,
					frase = frasePresente(efeito),
					extra = fraseExtra(efeito),
				})
			end
		end
	end
	table.sort(lista, function(a, b)
		if a.moedas ~= b.moedas then
			return a.moedas < b.moedas
		end
		-- Desempate pelo nome pra a ordem NAO mudar a cada volta do laco: dois
		-- presentes do mesmo preco trocariam de lugar no telao a cada 5
		-- segundos, e uma lista que se mexe sozinha parece defeito.
		return a.rotulo < b.rotulo
	end)
	return lista
end

-- O que o rodizio da coluna central esta' mostrando. Guardado aqui porque os
-- dois lacos mexem nele: o dos ajustes reescreve a lista, o do rodizio vira a
-- pagina.
local telaoLista: { any } = {}
local telaoPagina = 0

local function fundoDoTelao(): Instance?
	local cenario = workspace:FindFirstChild("Cenario")
	local parede = cenario and cenario:FindFirstChild("ParedeDeLED")
	local peca = parede and parede:FindFirstChild("Telao")
	local tela = peca and peca:FindFirstChild("Tela")
	return tela and tela:FindFirstChild("Fundo")
end

--[[ Escreve as duas linhas de um slot da lista lateral.

	Os slots sao Frames com dois TextLabel dentro (Nome e Efeito) -- eram
	TextLabel unicos, e viraram dois quando o telao passou a dizer o que cada
	presente FAZ. O `if` em cada peca existe porque o mapa pode ser antigo: um
	Cenario gerado antes desta mudanca ainda tem os slots de uma linha so', e a
	live tem que continuar subindo. ]]
local function escreverSlot(slot: Instance?, item: any?)
	if not slot or not slot:IsA("GuiObject") then
		return
	end
	if not item then
		-- Menos de quatro presentes cadastrados: o slot some, em vez de ficar
		-- uma caixa vazia no meio do telao.
		slot.Visible = false
		return
	end
	local nome = slot:FindFirstChild("Nome")
	local efeito = slot:FindFirstChild("Efeito")
	if nome and nome:IsA("TextLabel") then
		nome.Text = string.format("%s %s · %d", item.emoji, item.rotulo, item.moedas)
		if efeito and efeito:IsA("TextLabel") then
			efeito.Text = item.frase
		end
	elseif slot:IsA("TextLabel") then
		--[[ MAPA ANTIGO: o slot ainda e' um TextLabel de uma linha so'. Escreve
			no formato velho em vez de acender uma caixa vazia -- que e' o que
			aconteceria se este ramo nao existisse, e seria pior que nao mostrar
			nada. Regerando o Cenario (ferramentas/gerar-cenario.py) o slot vira
			duas linhas e o efeito aparece junto. ]]
		slot.Text = string.format("%s %s  ·  %d", item.emoji, item.rotulo, item.moedas)
	else
		slot.Visible = false
		return
	end
	slot.Visible = true
end

local function atualizarTelao(ajustes: any)
	local fundo = fundoDoTelao()
	if not fundo then
		return -- mapa antigo, ou telao apagado: nao ha' o que preencher
	end

	telaoLista = listaDePresentes(ajustes)

	for i = 1, 4 do
		escreverSlot(fundo:FindFirstChild("Presente" .. i), telaoLista[i])
	end
end

local function lacoAjustes()
	while true do
		local ajustes = Servidor.lerAjustes()
		atualizarTelao(ajustes)
		if type(ajustes) == "table" and type(ajustes.geral) == "table" then
			local geral = ajustes.geral

			for _, item in ipairs(ESPELHADOS) do
				local valor = tonumber(geral[item.chave])
				if valor then
					local antigo = workspace:GetAttribute(item.atributo)
					workspace:SetAttribute(item.atributo, valor)
					--[[ Mudou a regua da grade? Fecha o ciclo AGORA.

						Sem isto a mudanca so' valeria quando a formacao
						enchesse sozinha -- o que numa live normal demora tanto
						que, na pratica, mexer no painel nao fazia nada. Era
						exatamente o sintoma de "botei 5 por fileira e continua
						10". ]]
					if item.reiniciaCiclo and antigo ~= nil and antigo ~= valor then
						pedirFormacaoNova = true
					end
				end
			end

			for _, item in ipairs(ESPELHADOS_SIMNAO) do
				local valor = geral[item.chave]
				if type(valor) == "boolean" then
					workspace:SetAttribute(item.atributo, valor)
				end
			end

			for _, item in ipairs(ESPELHADOS_TEXTO) do
				local valor = geral[item.chave]
				if type(valor) == "string" and valor ~= "" then
					workspace:SetAttribute(item.atributo, valor)
				end
			end
		end
		task.wait(5)
	end
end

--[[ ─────────────── O RODIZIO DA COLUNA CENTRAL ───────────────

	A coluna do meio do telao tem 37 studs de largura -- e' o que sobra depois
	que o video em pe' corta o resto da parede. Nesse espaco NAO cabem, ao mesmo
	tempo e legiveis, o convite da live e a lista do que cada presente faz.

	Entao ela vira pagina. A CHAMADA volta entre dois presentes, sempre, e nao
	uma vez a cada volta completa: ela e' a unica coisa que a live PRECISA
	dizer, e alguem que chegou agora nao pode cair num telao que so' fala de
	preco. Com dois presentes cadastrados o convite ocupa 60% do tempo; com
	quatro, ainda 60% -- porque ele entra entre cada par, e nao no fim da fila.

	O rodizio e' tambem a unica coisa do cenario que se MEXE sozinha, e isso
	trabalha a favor: uma parede que muda a cada poucos segundos puxa o olho
	num vídeo em que o resto do fundo esta' parado.

	Se o mapa for antigo (gerado antes dos cartoes), o laco sai na primeira
	volta e o telao continua funcionando como sempre funcionou. ]]
local TELAO_CHAMADA_S = 6
local TELAO_PRESENTE_S = 4

local function lacoTelao()
	while true do
		local fundo = fundoDoTelao()
		if not fundo then
			-- O Cenario chega junto com o lugar, mas este script pode subir
			-- antes de a arvore terminar de replicar.
			task.wait(2)
			continue
		end

		local chamada = fundo:FindFirstChild("CartaoChamada")
		local cartao = fundo:FindFirstChild("CartaoPresente")
		if not (chamada and chamada:IsA("GuiObject")
				and cartao and cartao:IsA("GuiObject")) then
			return -- mapa antigo: nao ha' cartoes pra girar
		end

		chamada.Visible = true
		cartao.Visible = false
		task.wait(TELAO_CHAMADA_S)

		if #telaoLista > 0 then
			telaoPagina = telaoPagina % #telaoLista + 1
			local item = telaoLista[telaoPagina]
			local nome = cartao:FindFirstChild("Nome")
			local efeito = cartao:FindFirstChild("Efeito")
			local preco = cartao:FindFirstChild("Preco")
			if nome and nome:IsA("TextLabel") then
				nome.Text = string.format("%s %s", item.emoji, item.rotulo)
			end
			if efeito and efeito:IsA("TextLabel") then
				efeito.Text = item.frase
			end
			if preco and preco:IsA("TextLabel") then
				-- "1 moeda", e nao "1 moedas". O presente mais barato e' o que
				-- mais aparece no telao, entao o erro de concordancia ficaria
				-- na tela a live inteira.
				local moedas = string.format("%d %s", item.moedas,
					if item.moedas == 1 then "moeda" else "moedas")
				-- O segundo efeito pega carona quando existe. Sem o `if`, um
				-- presente que so' aumenta ficaria com um "·" solto no fim.
				preco.Text = if item.extra ~= ""
					then moedas .. " · " .. item.extra
					else moedas
			end
			chamada.Visible = false
			cartao.Visible = true
			task.wait(TELAO_PRESENTE_S)
		end
	end
end

--[[ Conta ao painel de que tamanho esta' o avatar de cada pessoa.

	A cada 3s, junto do placar, e nao a cada crescimento: crescer e' um evento
	que acontece varias vezes por segundo num combo, e uma requisicao HTTP por
	crescimento estouraria o teto de 500/min do HttpService -- que nao da' erro,
	so' TRAVA as requisicoes por uns 30 segundos. A live inteira congelaria, e
	a causa seria o envio de uma informacao de diagnostico. ]]
local function lacoTamanhos()
	while true do
		task.wait(3)
		local tamanhos: { [string]: any } = {}
		local algum = false
		for _, avatar in ipairs(naTela) do
			if avatar.tiktok_id ~= "" and avatar.modelo.Parent then
				local linha = tamanhos[avatar.tiktok_id]
				if linha then
					linha.avatares += 1
					-- O MAIOR boneco da pessoa e' o que o painel mostra: e' o
					-- que ela ve' na tela e o que o crescimento afetou.
					if avatar.escala > linha.tamanho then
						linha.tamanho = avatar.escala
					end
				else
					tamanhos[avatar.tiktok_id] =
						{ tamanho = avatar.escala, avatares = 1 }
					algum = true
				end
			end
		end
		if algum then
			Servidor.publicarTamanhos(tamanhos)
		end
	end
end

-- ─────────────────────────── Subida ───────────────────────────

--[[ Liga as requisicoes HTTP sozinho, se der.

	Sem elas o jogo nao fala com o servidor da live e NADA aparece -- e a
	mensagem que a Roblox devolve ("Http requests are not enabled") nao diz onde
	fica a chave que liga isso.

	Em modo Play no Studio a propriedade costuma aceitar escrita, e ai' o kit
	resolve sozinho um dos motivos mais comuns de "nao acontece nada". Quando
	nao aceita, o pcall segura o erro e o aviso da tela ensina o caminho do
	Game Settings. ]]
local function ligarHttp()
	local http = game:GetService("HttpService")
	if http.HttpEnabled then
		return
	end
	local ok = pcall(function()
		http.HttpEnabled = true
	end)
	if ok and http.HttpEnabled then
		print("[live] liguei as requisicoes HTTP sozinho.")
	end
end

local function subir()
	--[[ O PALCO PRIMEIRO, antes de qualquer conferencia.

		Antes o mapa so' era montado DEPOIS do teste de configuracao, entao
		qualquer problema de servidor deixava o Studio numa tela vazia -- que e'
		o quadro que faz quem comprou concluir que o kit nao funciona. Agora o
		palco esta' de pe' aconteca o que acontecer, e o que falta aparece
		escrito em cima dele. ]]
	montarPalco()
	ligarHttp()

	if not Servidor.configurado() then
		warn("[live] URL ou CHAVE vazios em Segredos.luau -- o jogo nao vai "
			.. "receber nada. Isto e' de proposito: melhor parar aqui do que "
			.. "falhar em silencio no meio de uma live.")
		avisar("FALTA CONFIGURAR O SEGREDOS.LUAU",
			"URL ou CHAVE estao vazios em roblox/src/ServerScriptService/"
				.. "Segredos.luau.")
		return
	end

	Avatares.iniciarRelogio()
	-- Antes de qualquer avatar nascer: a danca principal carrega? Se nao, o
	-- modulo troca pra reserva sozinho e a live nem percebe.
	Avatares.escolherDanca()

	--[[ Ancora no FIM da fila antes de comecar.

		Sem isto, um servidor que sobe no meio da live receberia o historico
		inteiro de uma vez e spawnaria uma multidao de fantasmas no primeiro
		segundo -- gente que comentou ha' dez minutos e ja' foi embora. ]]
	if ancorar() then
		print(string.format("[live] conectado ao servidor. Ancorado no evento %d.", cursor))
	else
		--[[ Falhou agora, mas isto NAO libera o jogo pra puxar do zero: o
			`ancorado` continua falso e o lacoServidor tenta de novo a cada
			volta, sem spawnar nada enquanto isso. Uma live que demora dois
			segundos a mais pra comecar e' muito melhor que uma live que abre
			despejando o historico inteiro na tela. ]]
		warn("[live] nao consegui falar com o servidor em " .. Segredos.URL)
		warn("[live] confira: a janela 'SERVIDOR DA LIVE' esta' aberta? "
			.. "E o HttpService esta' ligado em Game Settings > Security?")
		warn("[live] vou continuar tentando -- nenhum boneco nasce ate' o "
			.. "servidor responder.")
	end

	task.spawn(lacoServidor)
	task.spawn(lacoSpawn)
	task.spawn(lacoPlacar)
	task.spawn(lacoAjustes)
	task.spawn(lacoTelao)
	task.spawn(lacoTamanhos)

	print("[live] tudo no ar. Comente um nick do Roblox na sua live.")
end

subir()
