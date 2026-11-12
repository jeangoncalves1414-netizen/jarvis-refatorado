# Memória multilíngue local

O modelo solicitado é `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
revisão fixa `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, ONNX em CPU.
Instale uma vez com `python scripts/setup_memory_embeddings.py`.
Depois a inferência só lê `data/models/multilingual-minilm`, sem baixar arquivos.
Faltando os pesos, a memória vetorial registra indisponibilidade; não mistura
silenciosamente embeddings ingleses com multilíngues.

Fonte dos pesos e arquitetura:
https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
O adaptador aplica mean pooling com attention mask e normalização L2.
Coleções existentes precisam ser limpas ou reindexadas antes da troca.

## Comparação executada

Frases: `o usuário gosta de pizza` e `qual comida eu gosto?`.
Distância cosseno (menor é melhor), executada localmente em 11/11/2026:

| Modelo | Distância |
| --- | ---: |
| all-MiniLM-L6-v2 | 0,465793 |
| paraphrase-multilingual-MiniLM-L12-v2 | 0,637529 |

Este caso **não confirma a melhora esperada**. O teste registra a comparação,
mas não afirma superioridade. O limite de recuperação 0,45 permanece: essa
pergunta não recuperará esse fato pela busca vetorial isolada. Ajustar o limite
exige avaliar mais consultas e falsos positivos; não foi alterado para forçar
este exemplo a passar. Os testes de integração usam um índice temporário e
validam recuperação, exclusão e a ausência de expiração dos fatos duradouros.
