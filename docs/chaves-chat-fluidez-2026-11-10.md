# Chaves, novas conversas e fluidez — 10/11/2026

## Implementação
- Campos individuais com adicionar/remover para Oxyy, Groq e Gemini, preservando o formato já aceito pelo motor de rotação e pelo snapshot Supabase. Chaves continuam ocultas.
- Salvar Chaves confirma separadamente sucesso local e envio à nuvem; falha de nuvem deixa uma mensagem de reenvio, sem apagar as chaves locais. Token expirado é renovado antes do envio.
- Sessão de conta já persistia no localStorage/perfil WebView, com refresh automático. Sincronização ao abrir agora também roda no desktop (mantém intervalo existente de uma hora).
- Nova conversa abre estado vazio sem POST/criação local de histórico; primeiro envio de texto, imagem ou turno de voz cria a conversa. Rascunho da conversa anterior é preservado no desktop.
- Divisória usa requestAnimationFrame para alterar a altura durante o arraste; React e localStorage só recebem o tamanho final. Teclado continua funcionando.

## Verificação
- TypeScript e build de produção aprovados.
- Cinco cenários Playwright aprovados: sessão persistente/recuperação de rede, nova conversa sem criação prematura, campos de chave + payload de nuvem, divisória por teclado/persistência e arraste sem gravação por movimento.
- O teste das chaves precisou de uma correção na simulação de /api/settings/ai: a resposta anterior omitia routes, provocando erro no componente de modelos antes de chegar às chaves.
- Backend: 22 passaram e 2 falharam em tests/test_backend_cloud_sync.py: round trip e exclusão entre dispositivos, ambos por tarefas extras retornadas. Nenhum código de tarefas/backend foi alterado nesta rodada; essas falhas ficam pendentes.
- Testes usam chaves e endpoint de conta fictícios. Não houve alteração de credenciais reais nem envio de snapshots à conta real.

## Limites
A compilação está pronta para a próxima abertura/recarregamento. Não foi medida a taxa de quadros da janela nativa nesta rodada; a redução de trabalho durante o arraste foi verificada no navegador automatizado. Não houve migração para Rust. O comportamento de rotação existente dos provedores foi reutilizado, sem chamadas reais pagas ou simulação de limites no provedor externo.

## Complemento: visibilidade e rolagem das chaves
- O olho agora alterna password/text nos campos dos provedores, inclusive na interface mobile. Os campos começam ocultos.
- Listas de rotação têm altura máxima de 180px e rolagem automática para o campo adicionado; o botão + permanece fora da área rolável.
- Playwright passou cobrindo revelar/ocultar, valor preservado, nove campos e rolagem até o último, além de salvar/sincronizar com conta simulada.
- Diagnóstico real do Groq: quatro chaves distintas configuradas, cada uma recebeu HTTP 200 em uma solicitação curta ao modelo configurado openai/gpt-oss-120b (max_tokens=8). Não estavam bloqueadas para esse pedido no momento da consulta. Isso não certifica cota suficiente para históricos longos, outros modelos ou chamadas futuras. Nenhuma chave foi registrada no relatório.
