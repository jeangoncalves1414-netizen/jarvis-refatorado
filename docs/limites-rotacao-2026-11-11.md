# Limites e rotação — 11/11/2026

## Comportamento
- A chave que recebe 429 fica em espera pelo maior prazo válido de Retry-After (segundos/data HTTP) e do texto do provedor, com margem de segurança. Sem prazo válido, usa a espera padrão. Uma falha posterior não encurta a espera existente.
- A rotação procura outra chave disponível. Só a chave que falhou é bloqueada; não se presume que todas pertencem à mesma organização.
- O aviso informa provedor, motivo conhecido, quantidade de chaves em espera e prazo aproximado. O prazo é informado no momento da resposta, não é um contador animado.
- Em Groq, falha de cota na síntese após ferramentas preserva os resultados sem reiniciar as ações. Erro de tamanho permite apenas uma tentativa com menos histórico antigo, mantendo instruções e pedido recente.
- O chat diferencia erro de cota de conexão, recupera o rascunho quando o pedido falhou e mantém como resposta o resultado de ações já executadas que contém um aviso de cota.
- A verificação de disponibilidade não sugere configurar chaves novamente quando estão apenas em espera.

## Evidência anterior
O log de 10/11 mostrou quatro chaves distintas recebendo 429 e a rotação entre elas. Só a última falha trouxe o detalhamento preservado: limite diário de 200.000 tokens, 198.675 utilizados e pedido de 2.721. Não é possível deduzir desse log que todas pertencem à mesma organização ou atingiram o mesmo limite.

## Validação e limites
32 testes Python passaram, abrangendo rotação com chave alternativa disponível, todas indisponíveis, prazo de retorno, preservação dos resultados das ferramentas e orçamento de contexto. As chamadas são simuladas e não consomem cota real.
O estado de espera é mantido em memória e reinicia junto com o backend. Esta mudança não representa um painel de saldo de todas as contas nem uma reserva de cota por modelo.

Três testes Playwright passaram: aviso de cota em eventos error/complete com recuperação do rascunho e resultado de ação concluída sem preparar reenvio.
