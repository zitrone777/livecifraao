# NexivoLive Launcher

Launcher Windows do NexivoLive.

Fluxo:
1. O cliente baixa somente o Launcher.
2. O Launcher valida a licença pela API.
3. A API gera uma URL temporária para o pacote privado.
4. O Launcher baixa e extrai o NexivoLive em %LOCALAPPDATA%\NexivoLive.
5. A janela mostra apenas o botão Abrir pasta.

Nenhum segredo do Supabase é distribuído no executável.
