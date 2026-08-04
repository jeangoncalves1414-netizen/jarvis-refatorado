import React, { useMemo, useState } from 'react'

interface Block {
  type: 'paragraph' | 'code' | 'bullet-list' | 'heading'
  content: string
  language?: string
  items?: string[]
  level?: number
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
      blocks.push({ type: 'code', content: codeLines.join('\n'), language: lang || 'code' })
      i++ // Skip closing ```
      continue
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
      !lines[i].match(/^#{1,3}\s/) &&
      !lines[i].match(/^[-•*\d]\s+/)
    ) {
      paragraphLines.push(lines[i])
      i++
    }
    if (paragraphLines.length > 0) {
      blocks.push({ type: 'paragraph', content: paragraphLines.join('\n') })
    }
  }

  return blocks
}

function renderInline(text: string): React.ReactNode {
  // Regex for **bold**, *italic*, `code`
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g)
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
        <button type="button" className="msg-code-copy" onClick={handleCopy}>
          {copied ? '✓ Copiado' : 'Copiar'}
        </button>
      </div>
      <pre><code>{code}</code></pre>
    </div>
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
        if (block.type === 'code') {
          return <CodeBlock key={i} code={block.content} language={block.language || 'code'} />
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
