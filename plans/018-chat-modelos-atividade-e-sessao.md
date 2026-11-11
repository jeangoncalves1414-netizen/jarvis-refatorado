# Modelos por modo e experiência da conversa

Pedido de Jean, 10/11/2026. Implementação sobre as alterações locais existentes.

1. Rotas persistidas por modo (conversa, thinking, planejamento, pesquisa, código,
   navegação, etapas, Life OS, tutor, voz). Sem escolha, herdar conversa. Contexto
   de rota isolado por pedido e preservado na retomada após aprovação.
2. Indicador discreto; pensar apenas em thinking/planejamento. Atividades emitidas
   pelo executor real, com identificador, estado e fontes públicas; resumo expansível.
   Links encontrados não contam como páginas lidas. Sem expor argumentos sensíveis.
3. Contexto visível apenas quando uma ferramenta consulta memória por intenção.
4. Menu por mensagem, editar mensagem do usuário com corte persistente do histórico
   e bloqueio enquanto houver execução pendente. Horário real, sem inventar datas antigas.
5. Falha/ausência de resposta recupera o rascunho; não duplica mensagens nem apresenta
   sucesso falso. Parar pedido visível somente com execução ativa.
6. Perfil persistente do WebView; restaurar autenticação ao iniciar; renovação única,
   preservar credenciais em falha transitória e impedir renovação depois de logout.
   Aviso fixo no topo quando a restauração falhar.

Verificação: testes Python isolados para rotas, atividade e corte; TypeScript e build;
testes de navegador com APIs simuladas para edição, falha, atividade e login. Sem
usar provedores pagos, alterar conta real ou gravar nos dados pessoais de teste.

Implementação concluída:
- Rotas por modo, herdáveis, persistidas e isoladas por pedido; retomadas preservam a rota.
- Conversa padrão agora é explícita; somente Automático infere outro modo.
- Atividade real do executor e progresso durante leitura de fontes, com resumo expansível.
- Contexto visível e persistido somente para consultas intencionais à memória.
- Edição com corte no servidor, rejeição de histórico desatualizado e de pedidos pendentes.
- Horários por mensagem, recuperação de rascunho e descarte de respostas atrasadas.
- Botão Parar limitado aos pedidos ativos; perfil WebView persistente e aviso de reconexão.

Validação:
- 128 testes Python passaram (rotas, modos, conversa, executor e navegação).
- 5 cenários Playwright passaram (edição/falha, atividade/contexto/parar,
  login após recarregar, logout durante renovação e modelos independentes).
- Layout inspecionado em 1280x720 e 390x844; sem overflow horizontal.
- TypeScript e build de produção concluídos com sucesso.
- Um teste HTTP com timeout de 4s oscilou; passou isoladamente e na bateria final.
- Sem chamadas reais aos provedores ou reinício do app desktop com conta real.
  Compatibilidade dos parâmetros de persistência conferida no pywebview instalado.
