# Validação prática — 13/11/2026

## Conversas e controle de execução

Foram registradas 27 respostas reais na rodada de progresso/cancelamento, incluindo falhas e repetições; isso não significa 27 aprovações. A rodada final está em `scratch/capri-progress-retest-1794586716`.

- O agente confundia limites de execução com etapas restantes. O status agora expõe progresso observado e explica que o total de etapas é desconhecido.
- Consultas naturais de progresso agora têm `run_control` disponível no conjunto básico de ferramentas.
- Um pedido explícito de cancelar que recebia apenas uma consulta de status agora pode acionar a tentativa complementar limitada. Negação e cancelamento já tentado não repetem a ação.
- Na rodada final, o agente consultou a espera real, rejeitou a dedução de sete etapas restantes e cancelou a execução. O estado persistido confirmou `cancelled`.
- Houve dois erros de API em rodadas anteriores, cuja causa não foi determinada. Não são considerados resolvidos.

## Visão: qualidade ainda insuficiente

Configuração efetivamente observada: Groq, modelo `qwen/qwen3.8-27b`. Nenhuma troca do provedor padrão foi aplicada ao `.env`.

A mesma captura salva (`data/captures/screen_1794586761_e944.jpg`, Opera com YouTube) foi comparada diretamente:

- Groq reconheceu YouTube, mas chamou Opera de Chrome e inventou outros detalhes.
- Gemini `gemini-flash-latest` retornou HTTP 503 nas duas tentativas. Não foi possível comparar sua precisão.
- Evidências: `scratch/capri-vision-provider-comparison`.

Após a alteração de configuração, o endpoint real `/api/vision/analyze-frame` retornou o provedor/modelo corretos, mas a análise continuou inventando nomes e produziu texto contraditório sobre download. Uma conversa real chamou `vision` com sucesso, porém respondeu que desconhecia o provedor, apesar de ele constar nos dados técnicos. Evidências: `scratch/capri-vision-routing-validation`.

Correções implementadas:

- `VISION_PROVIDER` permite separar visão de chat (`gemini` ou `groq`; vazio acompanha chat compatível).
- `GEMINI_VISION_MODEL` seleciona o modelo Gemini; `GROQ_VISION_MODEL` continua selecionando o Groq.
- Inicialização compartilhada por ferramenta, orquestrador e endpoints de imagem.
- As credenciais Groq e Gemini ficam separadas, inclusive no fallback por modelo Groq indisponível.
- Provedor/modelo presentes nos resultados técnicos e no texto entregue ao agente. Esta última mudança foi verificada por teste automatizado, sem nova conversa após ela.
- Instruções visuais exigem evidência observável, mas os resultados reais demonstram que instruções sozinhas não eliminaram alucinações.

## Verificação

- Suíte combinada de execução, runs, economia de tokens, loop, espera e visão: **122 testes passaram**, com três avisos de depreciação de dependências.
- Após incluir provedor/modelo no texto da ferramenta: **17 testes de visão passaram**. Esses 17 estão contidos na suíte maior; não devem ser somados a ela.
- Smoke do frontend de cancelamento passou na etapa anterior, com APIs simuladas. Isso não substitui os testes reais descritos acima.

Não há aprovação geral de todas as ferramentas ou garantia de ausência de alucinações. A escolha de um substituto para visão permanece pendente de uma comparação bem-sucedida; Gemini indisponível não é evidência de qualidade inferior ou superior.
