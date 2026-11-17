# Histórico, continuidade e níveis de voz

Atualizado em 14/11/2026.

## Texto e voz

O chat de texto desbloqueado é o canal do proprietário. Recebe o histórico salvo da conversa selecionada, incluindo os turnos de voz que aconteceram nela, sem exigir biometria a cada mensagem. O bloqueio de abertura do aplicativo continua valendo.

Na voz, cada pedido precisa de evidência nova. Apenas o perfil principal (`role=admin`) reconhecido pela **voz** recebe histórico privado, memórias e ferramentas pessoais. Rosto reconhecido, seleção manual de perfil, dizer um nome ou reaproveitar um token não liberam esse acesso. Trechos mistos/incertos continuam sem acesso privado.

Turnos de voz sem acesso privado são salvos com escopo definido pelo servidor. Ao responder, o modelo recebe somente a conversa daquele escopo: visitante não recebe turnos privados, nem o resumo privado. O proprietário pode ler a transcrição completa no texto. Um visitante anônimo compartilha o escopo de visitantes daquele chat; pessoas identificadas usam seu próprio perfil/revisão. Trocar de chat troca o histórico.

## Níveis configuráveis

Em **Identidade → Níveis de acesso por voz**, digite a senha de desbloqueio e escolha o nível da pessoa:

| Nível | Comandos disponíveis |
| --- | --- |
| Visitante | Conversa geral e análise de câmeras solicitada pela interface |
| Usuário autorizado | Criar temporizadores/alarmes; esperar entre ações; clima com cidade explícita, notícias, cotações e feriados; mídia e volume |
| Administrador delegado | Tudo acima; brilho, telemetria CPU/RAM, bloqueio de tela; abrir Calculadora e Paint |
| Administrador principal | Recursos pessoais e comandos completos quando sua voz é reconhecida |

Delegado é um nível de comandos, não um segundo proprietário. Não recebe arquivos, clipboard, scripts, navegador de automação, conversas pessoais, agenda, memória ou poder para conceder permissões. A autorização é conferida no servidor antes de propor e executar a ferramenta, inclusive após uma aprovação pendente. As regras normais de confirmação das ferramentas continuam valendo.

Cadastros novos começam como visitantes. A antiga permissão `assistant_private` deixou de conceder dados privados. Perfis antigos sem nível explícito começam como visitantes até o proprietário selecionar o nível. Nenhum perfil real é alterado automaticamente por esta atualização.

## Compactação

O comportamento segue o princípio de continuidade descrito pela OpenAI para o [loop do Codex](https://openai.com/index/unrolling-the-codex-agent-loop/): manter um estado compacto e continuar o mesmo trabalho. Não é uma cópia da compactação nativa/encriptada da [Responses API](https://developers.openai.com/api/docs/guides/compaction); o Jarvis conserva seus provedores Gemini, Groq e Oxyy.

- O gatilho usa estimativa de tokens do histórico de trabalho (3.000), reservando espaço para instruções, ferramentas e a próxima pergunta.
- O checkpoint contém objetivo ativo, pedidos/restrições, decisões, resultados comprovados, referências, estado atual e próximos passos. Corrige decisões superadas e separa intenção de execução.
- Mantém pelo menos seis mensagens recentes completas, cortando o trecho antigo no início de um turno do usuário. O resumo é limitado a 4.500 caracteres.
- Atualizações incorporam o checkpoint anterior e os novos turnos. Entradas muito longas são processadas em blocos, sem abandonar o final de uma mensagem antiga.
- O resumo é preservado nos limites de contexto dos provedores e no loop de ferramentas. Foram removidos os cortes fixos de 10/20 mensagens; no ReAct, o resumo também não some depois de seis mensagens.
- A manutenção normalmente ocorre após o turno. Se uma conversa já estiver longa ao reabrir ou durante uma ligação, prepara o contexto antes do próximo envio. Não precisa encerrar a chamada para compactar.
- O histórico original permanece no disco. Edições invalidam checkpoints incompatíveis por assinatura; falha do modelo não substitui a transcrição. Consultas simples à primeira/última mensagem usam o histórico original autorizado.
- O cliente aguarda o salvamento anterior antes de enviar a próxima mensagem, incluindo respostas de câmeras.

O resumo continua sujeito à qualidade do modelo. Limites de requisição muito pequenos podem exigir remover parte dos turnos recentes; a pergunta atual e o checkpoint são preservados, e o histórico completo continua salvo. A estimativa de tokens é aproximada, não uma medição do tokenizer de cada provedor.

Reinicie o Jarvis para carregar o backend e a interface atualizados. Conversas antigas que só existiam na memória do processo e nunca foram salvas não podem ser reconstruídas por esta correção.
