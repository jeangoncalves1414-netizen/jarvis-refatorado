import { useEffect, useRef } from 'react'
import { Reasoning, ReasoningContent, ReasoningTrigger } from '../Reasoning'
import { MessageContent } from '../MessageContent'
import { ProcessingState } from '../tools/ProcessingState'
import { SearchTool, type SearchPayload, type SearchResult, type SearchStep } from '../tools/SearchTool'
import { EditTool } from '../tools/EditTool'
import { PlanTool, type PlanStep } from '../tools/PlanTool'
import { QuestionTool, type QuestionOption } from '../tools/QuestionTool'
import { SubagentTool } from '../tools/SubagentTool'
import { TodoTool, type TodoItem } from '../tools/TodoTool'
import { ToolStatus } from '../tools/ToolStatus'
import { MediaCard, type MediaViewPayload } from './MediaCard'
import type { ScriptRequest } from '../../types'
import type { ChatMode } from '../ChatComposer'

type MessageRendererProps = {
  content: string
  isStreaming?: boolean
  liveText?: string
  defaultOpenReasoning?: boolean
  mode?: ChatMode
  pendingScript?: ScriptRequest | null
  onRunPendingScript?: () => void
  onSendText?: (text: string) => void
  onCinemaRequest?: (payload: { title?: string; detect_url?: string; discovery_results?: Array<{ title?: string; url?: string; source?: string; snippet?: string }>; catalog_results?: Array<{ id?: string; title?: string; year?: string | number; description?: string }> }) => void
  liveSearch?: SearchPayload | null
  compactSearch?: boolean
}

export function MessageRenderer({
  content,
  isStreaming = false,
  liveText = '',
  defaultOpenReasoning = false,
  mode = 'general',
  pendingScript,
  onRunPendingScript,
  onSendText,
  onCinemaRequest,
  liveSearch = null,
  compactSearch = false,
}: MessageRendererProps) {
  let reasoning = ''
  let text = content
  let scriptPayload: { code?: string; oldCode?: string; filename?: string; title?: string } | null = null
  let searchPayload: { query: string; results: SearchResult[]; steps?: SearchStep[]; workflow?: 'search' | 'research' } | null = null
  let planPayload: { title?: string; steps: PlanStep[] } | null = null
  let subagentPayload: { description?: string; elapsedTime?: string; state?: 'pending' | 'completed' } | null = null
  let todoPayload: { title?: string; todos: TodoItem[] } | null = null
  let questionPayload: { question: string; options: QuestionOption[]; multiSelect?: boolean } | null = null
  let toolStatusPayload: { toolName: string; status?: 'pending' | 'completed' | 'error'; detail?: string; icon?: string } | null = null
  let cinemaPayload: { title?: string; detect_url?: string; discovery_results?: Array<{ title?: string; url?: string; source?: string; snippet?: string }>; catalog_results?: Array<{ id?: string; title?: string; year?: string | number; description?: string }> } | null = null
  let mediaPayload: MediaViewPayload | null = null

  const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/i)
  if (thinkMatch) {
    reasoning = thinkMatch[1].trim()
    text = text.replace(thinkMatch[0], '').trim()
  }
  const visibleReasoning = liveText || reasoning

  const parseMarker = <T,>(marker: string): T | null => {
    if (!text.includes(marker)) return null
    const jsonStart = text.indexOf(marker) + marker.length
    try {
      const payload = JSON.parse(text.substring(jsonStart).trim()) as T
      text = text.substring(0, text.indexOf(marker)).trim()
      return payload
    } catch (error) {
      console.warn(`Failed to parse JSON for marker ${marker}:`, error)
      return null
    }
  }

  scriptPayload = parseMarker('__SCRIPT_CONFIRM__')
  searchPayload = parseMarker('__SEARCH__')
  if (!searchPayload && liveSearch) searchPayload = liveSearch
  planPayload = parseMarker('__PLAN__')
  subagentPayload = parseMarker('__SUBAGENT__')
  todoPayload = parseMarker('__TODO__')
  questionPayload = parseMarker('__QUESTION__')
  toolStatusPayload = parseMarker('__TOOL_STATUS__')
  cinemaPayload = parseMarker('__CINEMA_PLAY__')
  mediaPayload = parseMarker<MediaViewPayload>('__MEDIA_VIEW__')

  const handledCinemaRef = useRef('')
  const cinemaSignature = cinemaPayload ? JSON.stringify(cinemaPayload) : ''
  useEffect(() => {
    if (!cinemaSignature || !cinemaPayload || !onCinemaRequest || handledCinemaRef.current === cinemaSignature) return
    handledCinemaRef.current = cinemaSignature
    onCinemaRequest(cinemaPayload)
  }, [cinemaPayload, cinemaSignature, onCinemaRequest])

  const isThinkingSentinel = isStreaming && text === 'Pensando…'
  const thinkingMode = mode === 'planning' || mode === 'thinking'
  const showReasoning = thinkingMode && visibleReasoning

  return (
    <div className="message-body">
      {isThinkingSentinel && thinkingMode && (
        <span className="ws-thinking" role="status">{mode === 'planning' ? 'Planejando…' : 'Pensando…'}</span>
      )}

      {isThinkingSentinel && !thinkingMode && (
        <span className="ws-response-pending" role="status" aria-label="Aguardando resposta"><span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" /></span>
      )}

      {!isThinkingSentinel && showReasoning && (
        <Reasoning isStreaming={isStreaming || !!liveText} defaultOpen={defaultOpenReasoning}>
          <ReasoningTrigger label="Raciocínio & Planejamento" />
          <ReasoningContent>{visibleReasoning}</ReasoningContent>
        </Reasoning>
      )}

      {!isThinkingSentinel && text ? (
        <MessageContent
          text={text}
          streaming={isStreaming && !searchPayload && !planPayload && !subagentPayload && !todoPayload && !questionPayload && !toolStatusPayload && !mediaPayload}
        />
      ) : null}

      {mediaPayload && (
        <MediaCard media={mediaPayload} />
      )}

      {toolStatusPayload && (
        <ToolStatus
          toolName={toolStatusPayload.toolName}
          status={toolStatusPayload.status || (isStreaming ? 'pending' : 'completed')}
          detail={toolStatusPayload.detail}
          icon={toolStatusPayload.icon}
        />
      )}
      {subagentPayload && (
        <SubagentTool
          state={subagentPayload.state || (isStreaming ? 'pending' : 'completed')}
          description={subagentPayload.description}
          elapsedTime={subagentPayload.elapsedTime}
        />
      )}
      {todoPayload && (
        <TodoTool
          state={isStreaming ? 'streaming' : 'idle'}
          title={todoPayload.title}
          todos={todoPayload.todos}
        />
      )}
      {questionPayload && (
        <QuestionTool
          question={questionPayload.question}
          options={questionPayload.options}
          multiSelect={questionPayload.multiSelect}
          onAnswer={(selectedIds) => {
            onSendText?.(`Selecionei: ${selectedIds.join(', ')}`)
          }}
        />
      )}
      {searchPayload && !compactSearch && (
        <SearchTool
          state={isStreaming ? 'searching' : 'done'}
          query={searchPayload.query}
          results={searchPayload.results}
          steps={searchPayload.steps}
          workflow={searchPayload.workflow}
        />
      )}
      {planPayload && (
        <PlanTool
          title={planPayload.title}
          steps={planPayload.steps}
        />
      )}
      {(scriptPayload || pendingScript) && (
        <EditTool
          filename={scriptPayload?.filename || pendingScript?.description || 'script.py'}
          oldCode={scriptPayload?.oldCode || ''}
          newCode={scriptPayload?.code || pendingScript?.code || ''}
          title={scriptPayload?.title || 'Proposta de Execução de Código'}
          onApprove={() => onRunPendingScript?.()}
        />
      )}
      {isStreaming && !isThinkingSentinel && !text && !visibleReasoning && !subagentPayload && !todoPayload && !questionPayload && !toolStatusPayload && !mediaPayload && (
        <ProcessingState label="Gerando resposta…" showLine={false} />
      )}
    </div>
  )
}
