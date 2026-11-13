# Testes práticos do Jarvis — 13/11/2026

## Implementado

- Bloqueio de abertura no desktop/painel: cadastro inicial de senha, opção de adiar, troca e desativação nas configurações. Senha com PBKDF2, sessões revogáveis e limitação de tentativas. API, WebSocket e execução de ações bloqueados; resposta em andamento deixa de ser entregue após bloqueio. Fechar a janela para a bandeja também bloqueia.
- Cadastro opcional de rosto/voz, com senha atual e consentimento explícito. Os motores locais existentes NÃO detectam apresentação de fotos/gravações. Não equivale a biometria segura do sistema operacional. Captura real e reconhecimento do proprietário ainda precisam ser validados com suas amostras. Sem criptografia dos arquivos locais. Android independente fora deste escopo.
- Lugares: buscar locais, mostrar e copiar coordenadas com um clique, abrir local ou rota no Google Maps. Dados podem vir de OpenStreetMap ou Google Places conforme configuração; não confundir pesquisa OSM com resultado Google.
- Correções verificadas: timer aceita unidades em inglês e português e informa duração; listas mostram nomes/estados; rotina não omite resultados; Home Assistant ausente é informado; visão não falha mais por variável de validação; plano inválido admite uma única nova tentativa antes de falhar; extração de URL navega antes de ler e não usa página antiga se a navegação falhar.
- Inventário sem alias duplicado; simulação de workflow disponível no modo geral. Ferramentas code_helper/dev_agent eram esboços que simulavam sucesso: agora falham explicitamente e continuam fora do modo geral. Não são agentes de desenvolvimento completos.
- Clipboard Intelligence passa a dizer que preparou texto, sem fingir que já o transformou quando o modelo não termina a síntese.
- Dependência ReportLab instalada e declarada; geração real de PDF repetida com sucesso.

## Execução e evidências

Foram enviados **60 pedidos reais** ao endpoint /api/chat, passando pelo orquestrador, provedor e ferramentas. **39 ferramentas distintas** aparecem em recibos. Não são respostas simuladas. Casos sem chamada também foram testados: saudação, premissa de exame não fornecido e descoberta de capacidades.

Artefatos completos, incluindo respostas e recibos, ficam em `scratch/live-20261113/` (ignorados pelo Git, contêm contexto pessoal). Não foram copiados dados pessoais para este relatório. Cada sucesso abaixo significa que a ferramenta retornou sucesso, não valida automaticamente a qualidade de toda a resposta.

Verificações adicionais: arquivo probe.txt contém QA-NOV13-FILE; espera real de 2 s registrada; PDF qa.pdf existe com cabeçalho PDF; timers registraram disparo. Interface Playwright confirmou cadastro, senha errada, desbloqueio, troca, desativação e cópia de coordenadas/links Maps. Amostras biométricas dos testes unitários são simuladas.

166 testes passaram na bateria principal; um caso adicional cobriu chunks Gemini sem candidates/parts (falha encontrada no log real); outros 6 casos confirmaram que ferramentas não implementadas não anunciam sucesso. Build web e smoke de popups passaram. Assets Android não foram regenerados.

## Limitações encontradas

- Groq apresenta limites de tokens/minuto e respostas incompletas, mesmo com autorização para gastar cota. Em alguns casos houve recibo correto, mas síntese ausente/curta. Isso continua sendo uma limitação operacional.
- Home Assistant não configurado; Spotify não estava aberto; nenhum Android conectado; quadro de estudos sem sessão ativa. Foram verificadas as respostas de indisponibilidade, não o controle dos dispositivos.
- code_helper/dev_agent não implementados; não prometem mais resultados inexistentes. A resposta geral do modelo ainda pode explicar código diretamente.
- Planejamento e resumo pessoal ainda podem retornar mensagem textual genérica, embora forneçam dados estruturados para a interface. Próxima melhoria útil: síntese determinística desses dados, sem depender de nova chamada ao modelo.
- Não testei envio de mensagens a terceiros, desligamento/reinício, instalação em dispositivos, organização dos arquivos reais ou limpeza do quadro do usuário. Essas operações não foram tratadas como necessárias para um teste de ferramentas.
- Não afirmo que todas as ferramentas ou todas as operações passaram. A tabela registra a cobertura exata. Ferramentas sem execução nesta rodada precisam de cenário próprio e, quando aplicável, credenciais/hardware.
- Nenhuma senha real foi criada. Configure-a em **Configurações → Senha e desbloqueio**, ou na tela de primeiro acesso.

## Cobertura por ferramenta registrada

| Ferramenta | Última evidência observada | Arquivo local de evidência |
|---|---|---|
| browser | sucesso retornado | round4-00-browser4.json |
| browser_agent | Não executada nesta rodada | — |
| calendar | sucesso retornado | round2-01-calendar.json |
| checklist_tool | sucesso retornado | 09-checklist.json |
| cinema | sucesso retornado | round4-06-cinema4.json |
| clipboard | Não executada nesta rodada | — |
| clipboard_intelligence | sucesso retornado | round4-10-clipboard4.json |
| code_helper | sucesso retornado | round4-01-code4.json |
| desktop_search | Não executada nesta rodada | — |
| dev_agent | Não executada nesta rodada | — |
| document_generator | sucesso retornado | pdf-retry.json |
| file_manager | succeeded | round3-06-files3.json |
| finance_tool | sucesso retornado | round2-04-finance.json |
| habit_tool | sucesso retornado | round3-02-habits3.json |
| hacker_mode | Não executada nesta rodada | — |
| home | falha informada | round3-04-home3.json |
| image_generator | Não executada nesta rodada | — |
| jarvis_mode | Não executada nesta rodada | — |
| kasa_control | Não executada nesta rodada | — |
| lifeos_tool | sucesso retornado | round2-05-lifeos.json |
| mcp | Não executada nesta rodada | — |
| media_tool | sucesso retornado | round3-16-media3.json |
| memory | sucesso retornado | round2-07-memory.json |
| mobile_adb | sucesso retornado | round3-10-adb3.json |
| news_reader | Não executada nesta rodada | — |
| notification | sucesso retornado | round4-09-notify4.json |
| open_screen | Não executada nesta rodada | — |
| open_window | sucesso retornado | round2-18-window.json |
| open_windows_app | sucesso retornado | round2-12-apps.json |
| persona_tool | sucesso retornado | round2-08-persona.json |
| personal_records | sucesso retornado | round4-08-personal4.json |
| phantom_typer | Não executada nesta rodada | — |
| places_search | sucesso retornado | round2-14-places2.json |
| planning_workspace | sucesso retornado | round3-11-planning3.json |
| proactive_agent | sucesso retornado | round3-13-proactive3.json |
| qr_reader | sucesso retornado | round4-05-qr4.json |
| realtime | sucesso retornado | round3-17-weather3.json |
| routine | sucesso retornado | round3-03-routines3.json |
| screen_peeler | Não executada nesta rodada | — |
| script_runner | Não executada nesta rodada | — |
| show_popup | Não executada nesta rodada | — |
| smart_drop_zone | Não executada nesta rodada | — |
| spotify | falha informada | round4-07-spotify4.json |
| system_control | sucesso retornado | round2-09-processes.json |
| system_tray | sucesso retornado | round3-14-tray3.json |
| task_tool | sucesso retornado | round3-01-tasks3.json |
| telegram_bot | sucesso retornado | round2-10-telegram.json |
| timer | sucesso retornado | round3-00-timer3.json |
| vault_daily_log | Não executada nesta rodada | — |
| vault_save_note | Não executada nesta rodada | — |
| vault_search | sucesso retornado | round4-04-vault4.json |
| vault_update_profile | Não executada nesta rodada | — |
| video_analyst | Não executada nesta rodada | — |
| vision | sucesso retornado | round3-05-vision3.json |
| wait | succeeded | round3-06-files3.json |
| wallpaper_engine | Não executada nesta rodada | — |
| web_search | sucesso retornado | round2-15-web.json |
| whatsapp | Não executada nesta rodada | — |
| whiteboard_add_image | Não executada nesta rodada | — |
| whiteboard_add_text | Não executada nesta rodada | — |
| whiteboard_clear | Não executada nesta rodada | — |
| whiteboard_edit | falha informada | round4-11-board4.json |
| workflow | sucesso retornado | round4-02-workflow4.json |
| wormhole | sucesso retornado | round3-15-wormhole3.json |

Os casos anteriores com falha foram preservados para comparação. code_helper aparece com sucesso antigo no recibo; o teste revelou saída vazia e originou a correção para falha explícita, coberta pelos testes unitários.
