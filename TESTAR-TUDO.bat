@echo off
setlocal
title Testes - Live Interativa NexivoLive
color 0A

rem ============================================================
rem  TESTES AUTOMATICOS
rem
rem  Roda todas as verificacoes do kit sem abrir o Studio, sem
rem  conectar no TikTok e sem gastar moeda. Leva uns 15 segundos.
rem
rem    1. as REGRAS (presentes, nicks, ajustes, limitador)
rem    2. o ENQUADRAMENTO da camera (telao e avatares no quadro)
rem    3. o CENARIO (chao piscando, superficies coplanares)
rem    4. o BUILD do Rojo (o jogo monta?)
rem
rem  QUANDO RODAR: sempre que mexer em qualquer arquivo de
rem  ponte\, servidor\ ou roblox\. Os quatro erros que estes
rem  testes pegam tem uma coisa em comum -- nenhum deles da'
rem  mensagem de erro no Studio. Eles aparecem como "a rosa
rem  ficou do tamanho da galaxia", "o telao esta' cortado", "o
rem  chao pisca" e "mudei o codigo e nada mudou".
rem
rem  NAO USE `setlocal enabledelayedexpansion` NESTE ARQUIVO.
rem  Com ela o cmd come o "!" de dentro de tudo que expande,
rem  inclusive do %~dp0.
rem ============================================================

set "FALHOU=0"

echo.
echo   ============================================================
echo    TESTES DA LIVE INTERATIVA
echo   ============================================================

rem ---------- achar o Python ----------

set "PY="
for %%C in (py python python3) do if not defined PY call :testar_python "%%C"
if not defined PY (
    echo.
    echo   [X] Python nao encontrado. Rode o INSTALAR.bat.
    echo.
    pause
    exit /b 1
)

rem ---------- 1. as regras ----------

echo.
echo   [1/4] Regras: presentes, nicks, ajustes e limitador de taxa
echo   ------------------------------------------------------------
"%PY%" "%~dp0ponte\testes.py"
if errorlevel 1 set "FALHOU=1"

rem ---------- 2. o enquadramento ----------

echo.
echo   [2/4] Enquadramento da camera
echo   ------------------------------------------------------------
if not exist "%~dp0ferramentas\luau.exe" (
    echo   [!] o luau.exe nao esta' na pasta ferramentas -- pulando.
    echo       Ele vem no kit; se sumiu, foi o antivirus.
) else (
    "%~dp0ferramentas\luau.exe" "%~dp0roblox\testes\enquadramento.spec.luau"
    if errorlevel 1 set "FALHOU=1"
)

rem ---------- 3. o cenario ----------
rem
rem O gerador RECUSA gravar quando acha duas superficies na mesma altura (o
rem defeito do "chao piscando"). Rodar ele aqui, alem de conferir, mantem o
rem Cenario.model.json em dia com o ferramentas\gerar-cenario.py -- se alguem
rem editou o JSON na mao, esta linha desfaz a edicao, e isso e' de proposito:
rem o gerador e' a fonte da verdade do mapa.

echo.
echo   [3/4] Cenario: superficies coplanares ^(chao piscando^)
echo   ------------------------------------------------------------
"%PY%" "%~dp0ferramentas\gerar-cenario.py"
if errorlevel 1 set "FALHOU=1"

rem ---------- 4. o build ----------

echo.
echo   [4/4] O jogo monta?
echo   ------------------------------------------------------------
set "ROJO="
if exist "%~dp0ferramentas\rojo.exe" (
    "%~dp0ferramentas\rojo.exe" --version >nul 2>&1
    if not errorlevel 1 set "ROJO=%~dp0ferramentas\rojo.exe"
)
if not defined ROJO (
    for /f "delims=" %%f in ('where rojo.exe 2^>nul') do if not defined ROJO set "ROJO=%%f"
)

if not defined ROJO (
    echo   [!] Rojo nao encontrado -- pulando. Rode o VERIFICAR.bat.
) else (
    "%ROJO%" build "%~dp0roblox" --output "%TEMP%\teste-live.rbxlx"
    if errorlevel 1 (
        echo   [X] o Rojo NAO conseguiu montar o jogo
        set "FALHOU=1"
    ) else (
        echo   [OK] monta sem erro
    )
    del "%TEMP%\teste-live.rbxlx" >nul 2>&1
)

rem ---------- veredito ----------

echo.
echo   ============================================================
if "%FALHOU%"=="0" (
    echo    TODOS OS TESTES PASSARAM
) else (
    echo    ALGUM TESTE FALHOU -- role pra cima e leia qual
    echo.
    echo    Cada teste diz o que ele estava conferindo e por que
    echo    aquilo importa na live.
)
echo   ============================================================
echo.
pause
exit /b 0


:testar_python
rem Igual ao do INSTALAR.bat: o Windows tem um atalho FALSO chamado
rem python.exe que so' abre a Microsoft Store, e em algumas versoes ele
rem responde com codigo de saida ZERO. Mandar ele EXECUTAR codigo e' o que
rem separa o Python de verdade do atalho.
set "VNUM="
"%~1" -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])" > "%TEMP%\kit-pyver.txt" 2>nul
if errorlevel 1 goto :testar_python_fim
for /f "usebackq delims=" %%v in ("%TEMP%\kit-pyver.txt") do set "VNUM=%%v"
if not defined VNUM goto :testar_python_fim
for /f "delims=0123456789" %%x in ("%VNUM%") do set "VNUM="
if not defined VNUM goto :testar_python_fim
if %VNUM% LSS 310 goto :testar_python_fim
set "PY=%~1"

:testar_python_fim
del "%TEMP%\kit-pyver.txt" >nul 2>&1
exit /b 0
