# Indicador de contexto — 13/11/2026

As respostas do chat Groq agora podem exibir “Contexto usado” com estimativa de tokens de entrada da última chamada medida. Ao expandir, aparecem as chamadas medidas individualmente, o modelo, o orçamento local de 6.000 e eventual redução entre o contexto original e o preparado.

A estimativa usa a mesma função que controla o orçamento: tamanho do JSON dividido por 3,2. Inclui mensagens e declarações de ferramentas. Não mede tokens faturados, saída ou a capacidade máxima do modelo. Não se somam chamadas para representar ocupação da janela de contexto.

O backend devolve e persiste somente os metadados de medição; nenhum prompt é acrescentado ao histórico por esse recurso. A interface mantém compatibilidade com conversas antigas sem medição. O coletor limita o registro às primeiras 32 chamadas instrumentadas por turno.

Cobertura inicial: caminho de streaming do chat Groq, incluindo redução inicial do histórico e ajuste por chamada. Gemini, visão, chat direto e planejamento ReAct não têm medição completa por este recurso. O painel informa essa limitação. A redução existente não foi substituída por resumo gerado por modelo.

Validação:

- 35 testes passaram (orçamento de contexto, chamadas Groq e economia de tokens).
- Após adicionar persistência, 63 testes passaram (orçamento, runs e runtime de conversa). Há sobreposição; os números não devem ser somados.
- Build web concluído; avisos existentes sobre tamanho de bundles e importação mista. Assets Android não foram sincronizados.
- Smoke de interface passou: estimativa por chamada, aviso de redução, conversa antiga e largura de 360 px.
- Conversa real retornou 5.433 tokens estimados, orçamento 6.000, sem redução, com resposta correta. Evidência: `scratch/context-usage-live.json`.
- Nova conversa após reiniciar o backend retornou 5.289 tokens estimados; a consulta ao histórico confirmou a persistência exata da medição. Evidência: `scratch/context-usage-reload.json`.

Os testes automatizados verificam igualdade entre a estimativa publicada e o payload preparado, redução de histórico sem guardar o texto nos metadados, isolamento por turno e persistência diante de uma gravação atrasada do cliente.
