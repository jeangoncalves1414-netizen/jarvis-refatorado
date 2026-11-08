# bugs-chat-voz

## Alterado
- frontend/src/hooks/useChat.ts: vigia de turno (a cada 4s e ao voltar para a janela). Sem evento do servidor por 15s, consulta /api/runs da conversa. Run terminal vira resposta no chat (result_summary ou aviso de falha/cancelado). awaiting_confirmation mostra "Aguardando aprovação na Central". Limite de 10 min encerra com erro. Nova função appendExchange.
- frontend/src/hooks/useMediaAssistant.ts: cada fala da ligação gera um turno novo (id único), enviado ao chat como mensagem de usuário + assistente. /api/chat/stream agora recebe session_id.
- frontend/src/components/LiveCallModal.tsx: mostra o histórico de turnos da ligação, não só o último.
- frontend/src/App.tsx: liga appendExchange e liveTurns.

## Testar
1. Pedir "abrir os hábitos de hoje", ir à Central, aprovar, voltar ao chat. Deve sair de "pensando" em até ~15s com o resultado do Run. A janela não abre sozinha nesse caminho; aparece só o resumo.
2. Ligação: falar várias vezes. Cada fala deve aparecer como novo par Você/Jarvis na ligação e no chat.
