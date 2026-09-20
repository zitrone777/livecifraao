@echo off
setlocal
title Live Interativa NexivoLive - partida
color 0B

rem ============================================================
rem  LIVE DE VERDADE -- tudo na sua maquina, sem nuvem.
rem
rem   TikTok --> ponte --> servidor local --> Roblox Studio (Play)
rem
rem  IMPORTANTE: o jogo tem que rodar no STUDIO em modo PLAY.
rem  O jogo PUBLICADO roda na nuvem da Roblox e nao alcanca o
rem  seu PC -- com ele, nada aparece, e nao ha' configuracao
rem  que resolva.
rem
rem  Tudo aqui esta' entre aspas de proposito: esta pasta PODE
rem  ficar num caminho com espaco ou acento, e vai funcionar.
rem
rem  E NAO LIGUE `enabledelayedexpansion`. Com ela o cmd come o
rem  "!" de dentro de tudo que expande -- inclusive do %~dp0.
rem  Numa pasta chamada "LIVE!" o caminho chegava mutilado nos
rem  `if exist` e o kit acusava "KIT INCOMPLETO" com os arquivos
rem  todos no lugar; e a lista de comandos la' embaixo saia sem
rem  o "!" na frente, ensinando o comando errado pra quem le'.
rem  Os lacos daqui sao de `goto`, e `goto` rele' a linha a cada
rem  volta -- nada aqui precisa de expansao atrasada.
rem ============================================================

set "RAIZ=%~dp0"
set "MEMORIA=%~dp0config\ultimo-usuario.txt"

rem As duas chaves do servidor. Rodando local nada disto e' alcancavel de fora
rem da sua maquina; elas existem pro dia em que voce quiser por o servidor na
rem nuvem, e ai' sao a unica coisa entre a sua live e quem quiser injetar
rem avatar falso nela.
set "CHAVE_ESCRITA=escrita-local"
set "CHAVE_LEITURA=leitura-local"
set "SERVIDOR_URL=http://127.0.0.1:8000"

rem Quem MAIS pode usar os comandos de teste no chat (separe por virgula).
rem CUIDADO: quem estiver aqui dispara de graca o mesmo efeito dos presentes
rem pagos, e isso mata o motivo de alguem mandar presente.
set "DONOS_EXTRA="

rem ---------- o kit chegou inteiro? ----------
rem
rem Sem esta conferencia, uma pasta faltando so' aparece la' embaixo como
rem "o sistema nao pode encontrar o caminho especificado", numa janela que
rem fecha antes de dar pra ler.

set "FALTA="
if not exist "%~dp0servidor\servidor.py" set "FALTA=%FALTA% servidor\servidor.py"
if not exist "%~dp0servidor\web\painel.html" set "FALTA=%FALTA% servidor\web\painel.html"
if not exist "%~dp0ponte\ponte.py" set "FALTA=%FALTA% ponte\ponte.py"
if not exist "%~dp0roblox\default.project.json" set "FALTA=%FALTA% roblox\default.project.json"

if defined FALTA (
    call :kit_incompleto
    exit /b 1
)

rem ---------- achar o Python ----------

set "PY="
set "PY_ANTIGO="
for %%C in (py python python3) do if not defined PY call :testar_python "%%C"

if not defined PY (
    call :sem_python
    exit /b 1
)

rem ---------- limpar sobras da sessao anterior ----------
rem
rem Sem isto, um processo antigo segura a porta e o novo morre no boot com
rem "Errno 10048" -- no meio da live, com uma mensagem que nao parece ter
rem nada a ver com o problema.

echo.
echo   Limpando processos de sessoes anteriores...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000"') do taskkill /PID %%p /T /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":34872"') do taskkill /PID %%p /T /F >nul 2>&1

rem As janelas PRETAS que sobraram, e nao so' os programas dentro delas.
rem Matar o rojo.exe deixava a janela "0 - Rojo" aberta num prompt morto, e a
rem cada partida sobrava mais uma. Depois de algumas lives a barra de tarefas
rem enche de janelas identicas e voce nao sabe mais qual e' a desta sessao --
rem inclusive na hora de achar a que tem a mensagem de erro.
rem
rem O /T e' obrigatorio e faltava: sem ele o taskkill mata o cmd.exe da janela
rem e DEIXA VIVO o programa que roda dentro dela. Era assim que sobrava um
rem rojo.exe orfao, sem janela nenhuma, ainda segurando a porta 34872 -- e a
rem sessao seguinte nao conseguia subir o Rojo.
taskkill /FI "WINDOWTITLE eq 0 - Rojo*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq 1 - SERVIDOR DA LIVE*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq 2 - PONTE*" /T /F >nul 2>&1
taskkill /IM rojo.exe /F >nul 2>&1

if not exist "%~dp0ferramentas\rojo.exe" (
    echo   AVISO: o Rojo nao esta' instalado ^(rode o INSTALAR.bat^).
)

rem ---------- O ROJO E O ARQUIVO DO JOGO MORAM NO ABRIR-JOGO.BAT ----------
rem
rem Aqui NAO se monta o jogo nem se sobe o Rojo, e isso e' o conserto de um
rem defeito que aparecia como "o Rojo nao conecta".
rem
rem Antes este arquivo montava o jogo e subia um `rojo serve`; alguns segundos
rem depois ele chamava o ABRIR-JOGO.bat, que MATAVA esse Rojo e subia outro no
rem lugar. Dois servidores na mesma porta, um matando o outro, com o Studio
rem abrindo no meio: se voce clicasse Connect na hora errada, conectava no que
rem estava sendo derrubado -- e o erro que aparecia era "connection lost", que
rem nao aponta pra causa nenhuma.
rem
rem Agora quem cuida do Rojo e' UM arquivo so', o ABRIR-JOGO.bat, chamado la'
rem embaixo. Um servidor, uma vez, conferido antes de o Studio abrir.
echo.

rem ---------- perguntar o @ do TikTok ----------

set "TIKTOK_USUARIO="
if exist "%MEMORIA%" set /p TIKTOK_USUARIO=<"%MEMORIA%"

if not "%TIKTOK_USUARIO%"=="" (
    set /p TIKTOK_USUARIO="  Usuario do TikTok [Enter = %TIKTOK_USUARIO%]: "
) else (
    set /p TIKTOK_USUARIO="  Usuario do TikTok (ex: fulano ou @fulano): "
)

rem ---------- tirar os espacos das pontas ----------
rem
rem O `set /p` guarda EXATAMENTE o que foi digitado, espaco sobrando incluido --
rem e sobra sempre, porque colar um @ de outro lugar traz espaco junto. Esse
rem espaco ia parar dentro do --usuario, o TikTok respondia "usuario nao
rem encontrado", e a mensagem mostrava o @ certo (o espaco nao aparece na tela).
rem O erro ficava impossivel de ver: o nome estava certo e mesmo assim nao
rem achava.

for /f "tokens=* delims= " %%a in ("%TIKTOK_USUARIO%") do set "TIKTOK_USUARIO=%%a"
:tirar_espaco_do_fim
if not "%TIKTOK_USUARIO%"=="" if "%TIKTOK_USUARIO:~-1%"==" " (
    set "TIKTOK_USUARIO=%TIKTOK_USUARIO:~0,-1%"
    goto tirar_espaco_do_fim
)

if "%TIKTOK_USUARIO%"=="" (
    echo.
    echo   Precisa digitar um usuario. Rode de novo.
    pause
    exit /b 1
)

if not exist "%~dp0config" mkdir "%~dp0config"
> "%MEMORIA%" echo %TIKTOK_USUARIO%

echo.
echo   Abrindo: servidor local e ponte do TikTok (%TIKTOK_USUARIO%)...
echo.

rem ---------- o servidor ----------
rem
rem chcp 65001 antes de tudo: sem isso os acentos das mensagens viram lixo na
rem tela -- inclusive os avisos de erro, que sao justamente os que precisam ser
rem lidos.

start "1 - SERVIDOR DA LIVE" /D "%~dp0servidor" cmd /k "chcp 65001 >nul && set CHAVE_ESCRITA=%CHAVE_ESCRITA%&& set CHAVE_LEITURA=%CHAVE_LEITURA%&& "%PY%" servidor.py"

rem ---------- ESPERAR o servidor ATENDER de verdade ----------
rem
rem Antes aqui era um "timeout /t 3" e seguia em frente. Tres segundos e' um
rem CHUTE, e quando ele errava a live subia quebrada de um jeito dificil de
rem entender: o navegador abria numa pagina morta, a ponte comecava a acumular
rem "servidor falhou" numa janela que ninguem estava olhando, e o Studio abria
rem por cima de tudo. Tres janelas no ar, nenhuma funcionando, e nada dizendo
rem qual delas era o problema.
rem
rem Aqui a gente PERGUNTA pela porta ate' ela responder. Se ela nao responder,
rem para agora e diz por que -- e' muito melhor falhar aqui, com uma frase, do
rem que quinze minutos depois no meio da transmissao.

echo   Esperando o servidor subir...
set "TENTATIVAS=0"

:esperar_servidor
netstat -ano | findstr "LISTENING" | findstr "127.0.0.1:8000" >nul 2>&1
if not errorlevel 1 goto servidor_no_ar
set /a TENTATIVAS+=1
if %TENTATIVAS% geq 20 goto servidor_mudo
timeout /t 1 /nobreak >nul
goto esperar_servidor

:servidor_mudo
echo.
echo   ============================================================
echo    O SERVIDOR DA LIVE NAO SUBIU
echo   ============================================================
echo.
echo    Esperei 20 segundos e a porta 8000 nao respondeu.
echo.
echo    A resposta esta' na janela "1 - SERVIDOR DA LIVE", que
echo    abriu junto com esta. Va' nela e leia a mensagem: e' ela
echo    que diz o que aconteceu.
echo.
echo    O que costuma ser:
echo      - outra sessao da live ainda aberta segurando a porta;
echo      - antivirus bloqueando o Python de abrir porta local;
echo      - o Python instalado pela metade.
echo.
echo    Reiniciar o PC resolve o primeiro caso, que e' o mais comum.
echo.
pause
exit /b 1

:servidor_no_ar
echo   Servidor no ar.

rem ---------- o painel ----------
rem
rem localhost e nao 127.0.0.1: o navegador embutido do OBS trata os dois como
rem origens diferentes, e usar o mesmo endereco em todo lugar evita uma classe
rem inteira de "a fonte do OBS fica preta".

start "" "http://localhost:8000/painel"

rem ---------- a ponte ----------

rem O @ vai ENTRE ASPAS. Sem elas, um espaco sobrando no que a pessoa digitou
rem (ou colou) parte o comando em dois: o argparse recebe metade do nome, a
rem ponte diz "usuario nao encontrado", e o @ que aparece na mensagem esta'
rem certo -- porque o pedaco que faltou nem chegou a ser impresso.
start "2 - PONTE DO TIKTOK" /D "%~dp0ponte" cmd /k "chcp 65001 >nul && set SERVIDOR_URL=%SERVIDOR_URL%&& set CHAVE_ESCRITA=%CHAVE_ESCRITA%&& set DONOS=%DONOS_EXTRA%&& "%PY%" ponte.py --usuario "%TIKTOK_USUARIO%""

echo   ============================================================
echo    ABRINDO O JOGO
echo   ============================================================
echo.
echo    IMPORTANTE: se voce ja' tem outro lugar aberto no Studio,
echo    FECHE ele antes. Um lugar antigo com outro codigo dentro
echo    briga com este e nada aparece.
echo.
timeout /t 3 /nobreak >nul
call "%~dp0ABRIR-JOGO.bat"
echo    Quando o Studio abrir, aperte PLAY (o triangulo azul no topo).
echo.
echo   ============================================================
echo    OVERLAYS PRO OBS (Fonte de Navegador)
echo   ============================================================
echo.
echo      http://localhost:8000/placar.html?tipo=moedas
echo      http://localhost:8000/placar.html?tipo=curtidas
echo      http://localhost:8000/placar.html?tipo=presenca
echo.
echo   ============================================================
echo    COMANDOS DE TESTE (so' funcionam pra VOCE)
echo   ============================================================
echo.
echo    Digite no chat da sua live pra disparar o efeito de graca:
echo.

rem Estas cinco linhas sao a razao pratica de a expansao atrasada estar
rem DESLIGADA no arquivo inteiro. Com ela ligada, o cmd trata "!" como abertura
rem de variavel: num texto com um "!" solto ele nao acha o par, desiste, e APAGA
rem o "!". As linhas saiam na tela como "teste", "medio", "grande" -- os
rem comandos impressos errados, sem nenhum sinal de que estavam errados. Quem
rem lia digitava "teste" no chat e nao acontecia nada.
echo      !teste     presente barato
echo      !medio     presente medio (segura a camera)
echo      !grande    presente grande
echo      !enorme    derruba a formacao inteira
echo      !lenda     chuva de avatares por 30s
echo.
echo    Na primeira vez, comente seu nick do Roblox antes -- ou
echo    mande o nick junto:  !lenda SeuNickDoRoblox
echo.
echo   Pra parar tudo, feche as janelas pretas.
echo.
pause
exit /b 0


rem ============================================================
rem  SUB-ROTINAS
rem ============================================================

:kit_incompleto
rem Distingue os DOIS casos, porque a solucao de um nao resolve o outro.
set "ONDE=%~dp0"
set "NO_TEMP="
if not "%ONDE%"=="%ONDE:\AppData\Local\Temp\=%" set "NO_TEMP=1"
if not "%ONDE%"=="%ONDE:Rar$=%" set "NO_TEMP=1"
if not "%ONDE%"=="%ONDE:\7z=%" set "NO_TEMP=1"

echo.
echo   ============================================================
echo    O KIT ESTA INCOMPLETO
echo   ============================================================
echo.
echo    Nao encontrei:%FALTA%
echo.
if defined NO_TEMP (
    echo    JA' SEI O QUE ACONTECEU. Voce deu dois cliques neste arquivo
    echo    DE DENTRO do ZIP, sem extrair antes.
    echo.
    echo    O Windows deixa voce abrir o ZIP e ver os arquivos, mas quando
    echo    voce clica num deles ele copia SO' AQUELE arquivo pra uma pasta
    echo    temporaria e roda de la'. O resto do kit fica dentro do ZIP.
    echo.
    echo    COMO RESOLVER:
    echo.
    echo      1^) Feche esta janela
    echo      2^) Clique com o BOTAO DIREITO no arquivo .zip
    echo      3^) Escolha "Extrair Tudo..." e confirme
    echo      4^) Abra a pasta que apareceu e rode o INICIAR-LIVE.bat de la'
    echo.
    echo    A pasta certa e' a que tem o INICIAR-LIVE.bat E as pastas
    echo    "servidor", "ponte" e "roblox" juntos.
) else (
    echo    Faltam arquivos nesta pasta:
    echo      %~dp0
    echo.
    echo    Duas causas possiveis:
    echo.
    echo      1^) O ZIP foi extraido pela metade. Extraia de novo, inteiro.
    echo.
    echo      2^) O antivirus apagou algum arquivo. Se foi isso, ele avisou
    echo         em alguma notificacao. Restaure a partir da quarentena, ou
    echo         extraia o ZIP de novo numa pasta fora do Desktop.
)
echo.
pause
exit /b 1


:sem_python
echo.
echo   ============================================================
echo    O PYTHON NAO FOI ENCONTRADO
echo   ============================================================
echo.
if defined PY_ANTIGO (
    echo    Achei um Python instalado, mas ele e' antigo demais pro kit
    echo    ^(%PY_ANTIGO%^). O kit precisa do Python 3.10 ou mais novo.
    echo.
    echo    Rode o INSTALAR.bat: ele instala uma versao nova do lado,
    echo    sem mexer na que ja' esta' ai'.
) else (
    echo    Rode o INSTALAR.bat primeiro -- ele baixa e instala o
    echo    Python pra voce.
    echo.
    echo    Se ja' rodou: FECHE esta janela e abra de novo. O Windows
    echo    so' enxerga programas recem-instalados em janelas abertas
    echo    DEPOIS da instalacao.
)
echo.
pause
exit /b 1


:testar_python
rem Recebe um comando (py, python, python3) e SO' aceita se ele for um Python
rem de verdade e novo o bastante. Igual ao do INSTALAR.bat -- se mexer num,
rem mexa nos dois.
rem
rem POR QUE NAO BASTA `--version`: o Windows 10/11 tem um ATALHO FALSO chamado
rem python.exe dentro de WindowsApps, que so' abre a Microsoft Store. Em algumas
rem versoes do Windows ele responde com codigo de saida ZERO, e ai' o kit o
rem aceitava como Python valido -- a Store abria sozinha e nada funcionava.
rem Aqui a gente manda ele EXECUTAR codigo: o atalho falso nao executa nada.
rem
rem O piso de 3.10 tambem nao e' opcional: a TikTokLive 6.6.6 declara
rem "Requires-Python: >=3.10", e a ponte usa asyncio.to_thread (3.9). Sem esta
rem barreira o kit subia inteiro e quebrava na primeira live, com um erro que
rem nao fala de versao do Python em lugar nenhum.
set "VNUM="
"%~1" -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])" > "%TEMP%\kit-pyver.txt" 2>nul
if errorlevel 1 goto :testar_python_fim
rem `for /f` e nao `set /p`: o print do Python termina em CRLF, e o `set /p`
rem deixa o CR pendurado no valor em algumas versoes do Windows -- um CR
rem invisivel reprovaria a conferencia de digitos logo abaixo.
for /f "usebackq delims=" %%v in ("%TEMP%\kit-pyver.txt") do set "VNUM=%%v"
if not defined VNUM goto :testar_python_fim

rem Se sobrou qualquer coisa que nao seja digito, nao foi o nosso print que
rem respondeu -- descarta em vez de comparar e explodir com erro de sintaxe.
for /f "delims=0123456789" %%x in ("%VNUM%") do set "VNUM="
if not defined VNUM goto :testar_python_fim

if %VNUM% LSS 310 (
    set "PY_ANTIGO=%~1"
    goto :testar_python_fim
)
set "PY=%~1"

:testar_python_fim
del "%TEMP%\kit-pyver.txt" >nul 2>&1
exit /b 0
