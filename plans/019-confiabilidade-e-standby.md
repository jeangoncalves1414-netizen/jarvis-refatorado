# Confiabilidade e standby

Ordem: corrigir confirmação sem ações e seleção de ferramentas; medir o processo
desktop; suspender trabalho de interface oculto; validar; avaliar Rust com evidências.

Também limitar contexto auxiliar, separar memórias de evidências atuais e testar
respostas inventadas, falhas, confirmação pendente e retomada de ações.
Não apagar memórias nem reescrever o painel antes das medições.

Implementado:
- Encerramento sem ação tenta corrigir o plano uma vez e falha explicitamente se persistir.
- Espera pedida de até 1h não pode ser declarada cumprida sem wait bem-sucedido.
- Resultados de abertura/reprodução usam recibos observados, não o texto livre do modelo.
- Pedidos operacionais reconhecidos no chat nativo não transmitem resposta antes da validação.
- Abrir vídeo no YouTube inclui ferramentas de descoberta e navegação no filtro de intenção.
- Memórias auxiliares deduplicadas, limitadas a 2400 caracteres; histórico enviado sem metadados
  visuais e com orçamento de 16000 caracteres, preservando a mensagem mais recente inteira.
- Incertezas e fontes deixaram de ser removidas pelo filtro de estilo.
- Registro compacto de todas as ações no prompt do loop evita esquecer etapas antigas.
- Consultas visuais de central, aprovações, plano, bridge, voz e dashboard param ao ocultar;
  retornam ao mostrar/focar. Métricas e logs só são consultados na página Análises.
- Acompanhamento de pedidos ativos e conexão WebSocket continuam em segundo plano.
- Eventos desktop de minimizar/restaurar/fechar para bandeja sinalizam standby; animações pausam.

Medições e limites:
- Amostra de 10s, processo Python do desktop PID 17936: 487,3 MB RSS e 13,91% de um núcleo.
- A segunda amostra não representa minimização: a automação falhou; leitura nativa posterior
  confirmou janela visível e não minimizada. Não usar para comparar antes/depois.
- Falhas do controle nativo: geometria indisponível, captura FrameArrived timeout e GetCursorPos
  Acesso negado. Sem reiniciar o app real ou executar comandos de mídia contra a conta do usuário.
- Teste de navegador com APIs simuladas: zero consultas dos oito endpoints visuais/idle
  monitorados durante 30s oculto; retomada imediata; pedidos ativos continuam monitorados.
- Não há estimativa comprovada de economia de CPU/RAM após as mudanças.

Decisão de arquitetura: manter React por enquanto. Tauri permite camada desktop em Rust,
mas mantém WebView no Windows (https://v2.tauri.app/concept/process-model/).
A amostra também mostra custo relevante no Python; trocar apenas a janela não elimina esse
custo. Reavaliar após medição nativa aberta/minimizada da versão reiniciada, incluindo detector
de voz e as janelas secundárias criadas no boot. Nenhuma migração Rust iniciada.

Limites de confiabilidade: essas proteções reduzem confirmações falsas, não provam todos os
fatos de uma resposta livre. Reconhecimento de pedidos operacionais é por regras; a comparação
semântica de todas as cláusulas de um pedido com seus efeitos ainda não é uma prova formal.

Validação: 225 testes Python passaram, cobrindo loop, evidências, espera/cancelamento,
contexto, execução nativa e catálogo. Os 7 cenários de navegador passaram; standby foi
reexecutado após incluir retorno por foco (bandeja) e passou. Compilação Python e TypeScript
passaram. Testes usam dados isolados e provedores simulados.
