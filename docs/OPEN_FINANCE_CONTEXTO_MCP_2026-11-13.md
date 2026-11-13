# Open Finance, contexto e MCP

## Operação

Em Finanças, o painel de conexões permite conectar vários bancos, renovar consentimento, desconectar, sincronizar e configurar intervalo de 5 a 1440 minutos. A sincronização automática começa desativada. Quando ativada, consulta na abertura do app e periodicamente enquanto o servidor está funcionando.

Configure PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no ambiente privado do servidor, reinicie e conecte cada banco pelo widget de consentimento. Não coloque chaves no frontend ou no chat. Requer conta e plano compatível no provedor. Sem essas credenciais, testes usam respostas simuladas: não há validação de conexão bancária real.

O intervalo consulta dados disponíveis no Pluggy; não força o banco a atualizar nesse intervalo. A atualização de origem depende do provedor, instituição e plano. Referência: https://docs.pluggy.ai/en/docs/integration-checklist/data-sync

Importação identifica transações por conta e ID, preserva categoria editada e exclusão manual, e mantém registros antigos quando ausentes numa consulta posterior. Correções explícitas são reaplicadas. Pendências, moedas diferentes de BRL, transferências próprias identificadas e pagamentos de fatura identificados ficam fora dos totais. Identificação depende dos metadados bancários; confira movimentos ambíguos. Recriar uma conexão com novos IDs pode exigir conciliação manual.

Categorias do provedor são aproveitadas. Sem categoria, descrição e tipo são enviados ao modelo configurado, com lista restrita de categorias e fallback Outros. Novos lançamentos usam o evento de atualização e recibo de finanças existente, respeitando a configuração de popups.

## Compactação

Executada após conclusão bem-sucedida do chat e adiada até encerrar a chamada ativa. Só ocorre acima do limite configurado no serviço (10 mil caracteres de histórico de trabalho), preservando as seis mensagens recentes. É manutenção independente do botão de cancelar o agente. O histórico original permanece salvo; falha do resumo não o substitui. Alterações concorrentes invalidam um resumo obsoleto. O banner informa enquanto está em andamento.

O indicador de contexto já existente continua sendo uma estimativa por chamada. O corte emergencial para caber no provedor é distinto do resumo persistido após a conversa.

## MCP avaliados

- GitHub oficial: candidato para substituir servidor antigo de exemplo, após conferir autenticação e permissões necessárias. https://github.com/github/github-mcp-server
- Playwright oficial: útil para automação com snapshots acessíveis; adição deve evitar sobreposição com browser/browser_agent já presentes. https://github.com/microsoft/playwright-mcp
- Google Maps Grounding: candidato para busca fundamentada de locais. Requer suporte a transporte remoto e autenticação no cliente MCP atual, que trabalha com stdio. https://developers.google.com/maps/architecture/grounding-with-maps-mcp

Nenhum servidor adicional instalado nesta etapa. Correção aplicada: structuredContent retornado pelo MCP agora permanece na observação entregue ao agente, preservando campos estruturados como coordenadas.
