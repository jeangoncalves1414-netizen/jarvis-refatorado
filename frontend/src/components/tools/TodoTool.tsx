import React from 'react'

export type TodoItem = {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

export type TodoToolProps = {
  state?: 'idle' | 'streaming'
  title?: string
  todos?: TodoItem[]
}

export function TodoTool({
  state = 'idle',
  title = 'Lista de Tarefas',
  todos = [],
}: TodoToolProps) {
  const isStreaming = state === 'streaming'

  return (
    <div className="todo-tool-card">
      <div className="todo-tool-header">
        <span className="todo-tool-icon">📋</span>
        <strong className="todo-tool-title">{title}</strong>
        {isStreaming && <span className="todo-tool-badge">Atualizando…</span>}
      </div>
      <div className="todo-tool-list">
        {todos.map((item, idx) => (
          <div key={idx} className={`todo-tool-item todo-${item.status}`}>
            <span className="todo-checkbox">
              {item.status === 'completed' ? '✓' : item.status === 'in_progress' ? '➔' : '○'}
            </span>
            <span className="todo-text">{item.content}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
