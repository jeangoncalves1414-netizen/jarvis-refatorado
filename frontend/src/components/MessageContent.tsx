import React, { useMemo, useState, useEffect, useRef, useId } from 'react'
import { Check, Copy, Maximize2, Code2 } from 'lucide-react'

interface Block {
  type: 'paragraph' | 'code' | 'bullet-list' | 'heading' | 'table' | 'math' | 'mermaid'
  content: string
  language?: string
  items?: string[]
  level?: number
  tableHeaders?: string[]
  tableRows?: string[][]
}

function parseBlocks(text: string): Block[] {
  if (!text) return []
  const lines = text.split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Code block ```lang ... ```
    if (line.trim().startsWith('```')) {
      const lang = line.trim().slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      const isMermaid = (lang || '').toLowerCase() === 'mermaid'
      blocks.push({
        type: isMermaid ? 'mermaid' : 'code',
        content: codeLines.join('\n'),
        language: lang || 'code',
      })
      i++ // Skip closing ```
      continue
    }

    // Math Block $$ ... $$
    if (line.trim().startsWith('$$')) {
      const mathLines: string[] = []
      let mathContent = line.trim().slice(2)
      if (mathContent.endsWith('$$') && mathContent.length > 2) {
        // Single line $$formula$$
        blocks.push({ type: 'math', content: mathContent.slice(0, -2).trim() })
        i++
        continue
      }
      if (mathContent) mathLines.push(mathContent)
      i++
      while (i < lines.length && !lines[i].trim().endsWith('$$')) {
        mathLines.push(lines[i])
        i++
      }
      if (i < lines.length && lines[i].trim().endsWith('$$')) {
        const last = lines[i].trim().replace(/\$\$$/, '')
        if (last) mathLines.push(last)
        i++
      }
      blocks.push({ type: 'math', content: mathLines.join('\n').trim() })
      continue
    }

    // Table block: starts with | ... |
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      const headerCells = line.split('|').map(c => c.trim()).filter(Boolean)
      if (headerCells.length > 0 && i + 1 < lines.length && lines[i + 1].includes('---')) {
        // Valid markdown table header followed by separator
        i += 2 // skip header and separator
        const rows: string[][] = []
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          const cells = lines[i].split('|').map(c => c.trim()).filter(Boolean)
          rows.push(cells)
          i++
        }
        blocks.push({
          type: 'table',
          content: '',
          tableHeaders: headerCells,
          tableRows: rows,
        })
        continue
      }
    }

    // Heading #, ##, ###
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/)
    if (headingMatch) {
      blocks.push({ type: 'heading', content: headingMatch[2], level: headingMatch[1].length })
      i++
      continue
    }

    // Bullet or numbered list item
    if (line.match(/^[-•*]\s+/) || line.match(/^\d+\.\s+/)) {
      const items: string[] = []
      while (i < lines.length && (lines[i].match(/^[-•*]\s+/) || lines[i].match(/^\d+\.\s+/))) {
        items.push(lines[i].replace(/^[-•*\d.]+\s+/, ''))
        i++
      }
      blocks.push({ type: 'bullet-list', content: '', items })
      continue
    }

    // Empty line — skip
    if (line.trim() === '') {
      i++
      continue
    }

    // Paragraph — collect lines until empty line or special token
    const paragraphLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].trim().startsWith('```') &&
      !lines[i].trim().startsWith('$$') &&
      !lines[i].match(/^#{1,3}\s/) &&
      !lines[i].match(/^[-•*\d]\s+/) &&
      !(lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|'))
    ) {
      paragraphLines.push(lines[i])
      i++
    }
    if (paragraphLines.length > 0) {
      blocks.push({ type: 'paragraph', content: paragraphLines.join('\n') })
    } else {
      // An incomplete table/heading or "1 text" may look special without
      // matching a block above. Always consume it, including during streaming.
      blocks.push({ type: 'paragraph', content: line })
      i++
    }
  }

  return blocks
}

function renderInline(text: string): React.ReactNode {
  // Regex for **bold**, *italic*, `code`, and $latex$
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\$[^$]+\$)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return <code key={i} className="msg-inline-code">{part.slice(1, -1)}</code>
    }
    if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
      return (
        <span key={i} className="msg-math-inline" title="Fórmula matemática">
          {part.slice(1, -1)}
        </span>
      )
    }
    return part
  })
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="msg-code-block">
      <div className="msg-code-header">
        <span className="msg-code-lang">{language}</span>
        <button
          type="button"
          className={`msg-code-copy ${copied ? 'copied' : ''}`}
          onClick={handleCopy}
          title={copied ? 'Copiado para a área de transferência' : 'Copiar código'}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? 'Copiado' : 'Copiar'}</span>
        </button>
      </div>
      <pre><code>{code}</code></pre>
    </div>
  )
}

function TableBlock({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="msg-table-wrapper">
      <table className="msg-table">
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i}>{renderInline(h)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rIdx) => (
            <tr key={rIdx}>
              {row.map((cell, cIdx) => (
                <td key={cIdx}>{renderInline(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MathBlock({ formula }: { formula: string }) {
  return (
    <div className="msg-math-block">
      <div className="msg-math-content">
        <code>{formula}</code>
      </div>
      <span className="msg-math-tag">Equação</span>
    </div>
  )
}

function MermaidBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const [showRaw, setShowRaw] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const uid = useId().replace(/:/g, '')
  const diagramId = `mermaid-${uid}`

  useEffect(() => {
    if (showRaw || !containerRef.current) return
    let cancelled = false

    const render = async () => {
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          themeVariables: {
            primaryColor: '#00f5d4',
            primaryBorderColor: 'rgba(0,245,212,0.4)',
            primaryTextColor: '#e2e8f0',
            background: 'transparent',
            mainBkg: 'rgba(10,12,24,0.8)',
            nodeBorder: 'rgba(0,245,212,0.35)',
            lineColor: 'rgba(0,245,212,0.5)',
            clusterBkg: 'rgba(0,245,212,0.05)',
            titleColor: '#00f5d4',
            edgeLabelBackground: 'rgba(10,12,24,0.9)',
            fontFamily: 'Inter, system-ui, sans-serif',
          },
          securityLevel: 'loose',
        })
        const { svg } = await mermaid.render(diagramId, code)
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg
          setRenderError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setRenderError(String(err))
        }
      }
    }

    void render()
    return () => { cancelled = true }
  }, [code, showRaw, diagramId])

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      {fullscreen && (
        <div className="msg-mermaid-fullscreen-overlay" onClick={() => setFullscreen(false)}>
          <div className="msg-mermaid-fullscreen-inner" onClick={e => e.stopPropagation()}>
            <button type="button" className="msg-mermaid-btn" onClick={() => setFullscreen(false)} style={{ marginBottom: 12, alignSelf: 'flex-end' }}>✕ Fechar</button>
            <div className="msg-mermaid-fullscreen-diagram" dangerouslySetInnerHTML={{ __html: containerRef.current?.innerHTML ?? '' }} />
          </div>
        </div>
      )}
      <div className="msg-mermaid-card">
        <div className="msg-mermaid-header">
          <span className="msg-mermaid-title">📊 Diagram Copilot · Mermaid</span>
          <div className="msg-mermaid-actions">
            {!showRaw && !renderError && (
              <button type="button" onClick={() => setFullscreen(true)} className="msg-mermaid-btn" title="Abrir em tela cheia">
                <Maximize2 size={13} />
              </button>
            )}
            <button type="button" onClick={() => setShowRaw(!showRaw)} className="msg-mermaid-btn" title={showRaw ? 'Ver diagrama' : 'Ver código fonte'}>
              <Code2 size={13} />
              <span>{showRaw ? 'Diagrama' : 'Código'}</span>
            </button>
            <button type="button" onClick={handleCopy} className="msg-mermaid-btn">
              {copied ? <><Check size={13} /> <span>Copiado</span></> : <><Copy size={13} /> <span>Copiar</span></>}
            </button>
          </div>
        </div>
        {showRaw ? (
          <pre className="msg-mermaid-raw"><code>{code}</code></pre>
        ) : renderError ? (
          <div className="msg-mermaid-error">
            <p>⚠️ Falha ao renderizar diagrama</p>
            <pre><code>{code}</code></pre>
          </div>
        ) : (
          <div className="msg-mermaid-preview">
            <div ref={containerRef} className="msg-mermaid-svg-container" />
          </div>
        )}
      </div>
    </>
  )
}

export function MessageContent({ text, streaming }: { text: string; streaming?: boolean }) {
  const blocks = useMemo(() => parseBlocks(text), [text])

  if (!text && streaming) {
    return <span className="msg-cursor-only" />
  }

  return (
    <div className={`msg-content${streaming ? ' msg-streaming' : ''}`}>
      {blocks.map((block, i) => {
        if (block.type === 'mermaid') {
          return <MermaidBlock key={i} code={block.content} />
        }
        if (block.type === 'code') {
          return <CodeBlock key={i} code={block.content} language={block.language || 'code'} />
        }
        if (block.type === 'math') {
          return <MathBlock key={i} formula={block.content} />
        }
        if (block.type === 'table' && block.tableHeaders) {
          return <TableBlock key={i} headers={block.tableHeaders} rows={block.tableRows || []} />
        }
        if (block.type === 'heading') {
          const level = block.level || 2
          if (level === 1) return <h2 key={i} className="msg-heading msg-h1">{renderInline(block.content)}</h2>
          if (level === 2) return <h3 key={i} className="msg-heading msg-h2">{renderInline(block.content)}</h3>
          return <h4 key={i} className="msg-heading msg-h3">{renderInline(block.content)}</h4>
        }
        if (block.type === 'bullet-list') {
          return (
            <ul key={i} className="msg-list">
              {block.items?.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ul>
          )
        }
        return (
          <p key={i} className="msg-paragraph">
            {renderInline(block.content)}
          </p>
        )
      })}
      {streaming && <span className="msg-cursor" />}
    </div>
  )
}
