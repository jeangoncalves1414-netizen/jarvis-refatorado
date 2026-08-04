import { useCallback, useEffect, useRef, useState } from 'react'
import type { WhiteboardElement } from '../../types'

type CanvasMenu = { clientX: number; clientY: number; x: number; y: number; targetId?: string }
type ResizeCorner = 'nw' | 'ne' | 'sw' | 'se'
type Interaction =
  | { kind: 'pan'; pointerId: number; startX: number; startY: number; panX: number; panY: number }
  | { kind: 'move'; pointerId: number; id: string; startX: number; startY: number; originX: number; originY: number; patch: Partial<WhiteboardElement> }
  | { kind: 'resize'; pointerId: number; id: string; corner: ResizeCorner; startX: number; startY: number; originX: number; originY: number; width: number; height: number; ratio: number; patch: Partial<WhiteboardElement> }

type StudyCanvasProps = {
  elements: WhiteboardElement[]
  sessionId: string
  onRefresh?: () => void
  onAddText?: (x: number, y: number, listStyle?: WhiteboardElement['listStyle']) => Promise<string | undefined>
  onAddImage?: (x: number, y: number) => void
  onAddPastedImage?: (x: number, y: number, base64: string) => Promise<string | undefined>
  onClearCanvas?: () => void
  onUpdateElement?: (id: string, patch: Partial<WhiteboardElement>, persist?: boolean) => void
  onDeleteElement?: (id: string) => void
  onDuplicateElement?: (id: string) => void
}

const elementWidth = (element: WhiteboardElement) => element.width || 280
const elementHeight = (element: WhiteboardElement) => element.height || (element.type === 'image' ? 210 : 90)
const elementId = (element: WhiteboardElement, index: number) => element.id || `element-${index}`

export function StudyCanvas({ elements, sessionId, onRefresh, onAddText, onAddPastedImage, onAddImage, onClearCanvas, onUpdateElement, onDeleteElement, onDuplicateElement }: StudyCanvasProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  const interactionRef = useRef<Interaction | null>(null)
  const [scale, setScale] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [menu, setMenu] = useState<CanvasMenu | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [editingId, setEditingId] = useState('')
  const [draft, setDraft] = useState('')
  const [snap, setSnap] = useState(false)
  const [gridVisible, setGridVisible] = useState(true)
  const [pendingEditId, setPendingEditId] = useState('')

  const selected = elements.find((element, index) => elementId(element, index) === selectedId)
  const selectedIndex = selected ? elements.indexOf(selected) : -1

  useEffect(() => {
    if (!sessionId || !onRefresh) return
    const id = window.setInterval(onRefresh, 5000)
    return () => window.clearInterval(id)
  }, [sessionId, onRefresh])

  useEffect(() => {
    if (!editingId) return
    const timer = window.setTimeout(() => {
      const editor = editorRef.current
      if (!editor) return
      const active = elements.find((element, index) => elementId(element, index) === editingId)
      editor.textContent = active?.content || draft
      editor.style.height = 'auto'
      editor.style.height = `${Math.max(70, editor.scrollHeight + 20)}px`
      editor.focus()
      const range = document.createRange()
      range.selectNodeContents(editor)
      range.collapse(false)
      const selection = window.getSelection()
      selection?.removeAllRanges()
      selection?.addRange(range)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [editingId])

  useEffect(() => {
    if (!pendingEditId) return
    const item = elements.find((element, index) => elementId(element, index) === pendingEditId)
    if (item) { startEditing(item, pendingEditId); setPendingEditId('') }
  }, [elements, pendingEditId])

  const addTextAndEdit = async (x: number, y: number, listStyle: WhiteboardElement['listStyle']) => {
    const created = await onAddText?.(x, y, listStyle)
    if (typeof created === 'string') setPendingEditId(created)
  }

  const handlePaste = (event: React.ClipboardEvent<HTMLDivElement>) => {
    if (editingId || !sessionId || !onAddPastedImage) return
    const image = Array.from(event.clipboardData.items).find(item => item.type.startsWith('image/'))
    if (!image) return
    const file = image.getAsFile()
    if (!file) return
    event.preventDefault()
    const reader = new FileReader()
    reader.onload = async () => {
      const base64 = typeof reader.result === 'string' ? reader.result : ''
      if (!base64) return
      const point = canvasPoint(260, 190)
      await onAddPastedImage(point.x, point.y, base64)
    }
    reader.readAsDataURL(file)
  }

  const canvasPoint = useCallback((clientX: number, clientY: number) => {
    const rect = viewportRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return { x: (clientX - rect.left - pan.x) / scale, y: (clientY - rect.top - pan.y) / scale }
  }, [pan, scale])

  const update = useCallback((id: string, patch: Partial<WhiteboardElement>, persist = false) => {
    if (id && onUpdateElement) onUpdateElement(id, patch, persist)
  }, [onUpdateElement])

  const commitText = () => {
    if (!editingId) return
    const content = editorRef.current?.textContent ?? draft
    const height = editorRef.current ? Math.max(70, editorRef.current.scrollHeight + 20) : undefined
    update(editingId, { content, ...(height ? { height } : {}) }, true)
    setEditingId('')
  }

  const handleEditorInput = (event: React.FormEvent<HTMLDivElement>) => {
    const editor = event.currentTarget
    const content = editor.textContent || ''
    editor.style.height = 'auto'
    const height = Math.max(70, editor.scrollHeight + 20)
    editor.style.height = `${height}px`
    setDraft(content)
    update(editingId, { content, height }, false)
  }

  function startEditing(element: WhiteboardElement, id: string) {
    if (element.type === 'image' || element.locked) return
    setSelectedId(id)
    setDraft(element.content || '')
    setEditingId(id)
    setMenu(null)
  }

  const onWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.scrollTop = 0
    event.currentTarget.scrollLeft = 0
    const rect = viewportRef.current?.getBoundingClientRect()
    if (!rect) return
    const mouseX = event.clientX - rect.left
    const mouseY = event.clientY - rect.top
    const nextScale = Math.min(2.8, Math.max(0.3, scale * (event.deltaY > 0 ? 0.9 : 1.1)))
    setPan(current => ({ x: mouseX - (mouseX - current.x) * (nextScale / scale), y: mouseY - (mouseY - current.y) * (nextScale / scale) }))
    setScale(nextScale)
  }

  const resizePatch = (interaction: Extract<Interaction, { kind: 'resize' }>, event: React.PointerEvent<HTMLDivElement>) => {
    let dx = (event.clientX - interaction.startX) / scale
    let dy = (event.clientY - interaction.startY) / scale
    let x = interaction.originX
    let y = interaction.originY
    let width = interaction.width
    let height = interaction.height
    if (interaction.corner.includes('e')) width = Math.max(120, interaction.width + dx)
    if (interaction.corner.includes('s')) height = Math.max(64, interaction.height + dy)
    if (interaction.corner.includes('w')) { width = Math.max(120, interaction.width - dx); x = interaction.originX + dx }
    if (interaction.corner.includes('n')) { height = Math.max(64, interaction.height - dy); y = interaction.originY + dy }
    if (event.shiftKey) {
      const nextHeight = Math.max(64, width / interaction.ratio)
      if (interaction.corner.includes('n')) y = interaction.originY + interaction.height - nextHeight
      height = nextHeight
    }
    if (snap) { x = Math.round(x / 8) * 8; y = Math.round(y / 8) * 8; width = Math.round(width / 8) * 8; height = Math.round(height / 8) * 8 }
    return { x, y, width, height }
  }

  const finishInteraction = (event: React.PointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (interaction?.pointerId === event.pointerId && interaction.kind !== 'pan') update(interaction.id, interaction.patch, true)
    if (viewportRef.current?.hasPointerCapture(event.pointerId)) viewportRef.current.releasePointerCapture(event.pointerId)
    interactionRef.current = null
  }

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (!interaction || interaction.pointerId !== event.pointerId) return
    if (interaction.kind === 'pan') {
      setPan({ x: interaction.panX + event.clientX - interaction.startX, y: interaction.panY + event.clientY - interaction.startY })
      return
    }
    if (interaction.kind === 'move') {
      let x = interaction.originX + (event.clientX - interaction.startX) / scale
      let y = interaction.originY + (event.clientY - interaction.startY) / scale
      if (snap) { x = Math.round(x / 8) * 8; y = Math.round(y / 8) * 8 }
      interaction.patch = { x, y }
    } else interaction.patch = resizePatch(interaction, event)
    update(interaction.id, interaction.patch, false)
  }

  const openMenu = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault()
    const point = canvasPoint(event.clientX, event.clientY)
    const target = (event.target as HTMLElement).closest('[data-study-element]')?.getAttribute('data-study-element') || undefined
    if (target) setSelectedId(target)
    setMenu({ clientX: event.clientX, clientY: event.clientY, ...point, targetId: target })
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const modifier = event.ctrlKey || event.metaKey
      if (event.key === 'Escape') { setMenu(null); setEditingId(''); return }
      if (editingId) {
        if (modifier && event.key.toLowerCase() === 'enter') { event.preventDefault(); commitText() }
        return
      }
      if (!selected || !selectedId) return
      if ((event.key === 'Delete' || event.key === 'Backspace') && onDeleteElement) { event.preventDefault(); onDeleteElement(selectedId); setSelectedId(''); return }
      if (modifier && event.key.toLowerCase() === 'd') { event.preventDefault(); onDuplicateElement?.(selectedId); return }
      if (event.altKey && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key) && !selected.locked) {
        event.preventDefault()
        const step = event.shiftKey ? 10 : 2
        const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0
        const dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0
        update(selectedId, { x: (selected.x || 0) + dx, y: (selected.y || 0) + dy }, true)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [editingId, selected, selectedId, draft, onDeleteElement, onDuplicateElement, update])

  const renderContent = (element: WhiteboardElement, id: string) => {
    if (element.type === 'image') return <img src={element.content} alt={element.caption || 'Elemento visual'} className="study-element-image" style={{ objectFit: element.objectFit || 'contain' }} draggable={false} />
    if (editingId === id) return <div ref={editorRef} className="study-inline-editor" contentEditable suppressContentEditableWarning onInput={handleEditorInput} onBlur={commitText} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); commitText() } if (event.key === 'Escape') { event.preventDefault(); setEditingId('') } }} />
    const lines = String(element.content || '').split('\n')
    const className = `study-text-${element.variant || 'paragraph'}`
    if (element.listStyle === 'bullets') return <ul className={`study-element-list ${className}`}>{lines.map((line, index) => <li key={index}>{line || ' '}</li>)}</ul>
    if (element.listStyle === 'ordered') return <ol className={`study-element-list ${className}`}>{lines.map((line, index) => <li key={index}>{line || ' '}</li>)}</ol>
    if ((element.listStyle as string) === 'tasks') return <ul className={`study-element-list study-task-list ${className}`}>{lines.map((line, index) => <li key={index}><input type="checkbox" checked={Boolean(element.checked?.[index])} onChange={event => { const checked = [...(element.checked || [])]; checked[index] = event.target.checked; update(id, { checked }, true) }} onPointerDown={event => event.stopPropagation()} />{line || 'Tarefa'}</li>)}</ul>
    if (element.listStyle === 'tasks') return <ul className={`study-element-list study-task-list ${className}`}>{lines.map((line, index) => <li key={index}><span aria-hidden="true">□</span>{line || ' '}</li>)}</ul>
    return <div className={className}>{element.content}</div>
  }

  const resizeHandles: ResizeCorner[] = ['nw', 'ne', 'sw', 'se']
  const sortedElements = elements.map((element, index) => ({ element, index })).sort((a, b) => (a.element.zIndex || 0) - (b.element.zIndex || 0))

  return <div id="study-canvas-shell" className="study-canvas-shell">
    <div className="study-canvas-commandbar">
      <button type="button" onClick={() => { const point = canvasPoint(240, 180); addTextAndEdit(point.x, point.y, 'plain') }}>+ Texto</button>
      <button type="button" onClick={() => { const point = canvasPoint(240, 180); addTextAndEdit(point.x, point.y, 'bullets') }}>+ Lista</button>
      <button type="button" onClick={() => { const point = canvasPoint(240, 180); addTextAndEdit(point.x, point.y, 'ordered') }}>+ Ordenada</button>
      <button type="button" onClick={() => { const point = canvasPoint(240, 180); addTextAndEdit(point.x, point.y, 'tasks') }}>+ Tarefas</button>
      <button type="button" onClick={() => { const point = canvasPoint(240, 180); onAddImage?.(point.x, point.y) }}>+ Imagem</button>
      <span className="study-commandbar-divider" />
      <button type="button" onClick={() => { setGridVisible(value => !value); setSnap(value => !value) }} className={gridVisible ? 'active' : ''}>Grade</button>
      <button type="button" onClick={() => { setPan({ x: 0, y: 0 }); setScale(1) }}>Centralizar</button>
      <span className="study-zoom-label">{Math.round(scale * 100)}%</span>
      <button type="button" onClick={() => setScale(value => Math.max(.3, value - .1))}>−</button><button type="button" onClick={() => setScale(value => Math.min(2.8, value + .1))}>+</button>
    </div>
    {selected && <div className="study-selection-toolbar" onPointerDown={event => event.stopPropagation()}>
      <span className="study-selection-type">{selected.type === 'image' ? 'Imagem' : selected.variant === 'heading' ? 'Título' : 'Texto'}</span>
      {selected.type !== 'image' && <><button type="button" className={selected.fontWeight === 'bold' ? 'active' : ''} onClick={() => update(selectedId, { fontWeight: selected.fontWeight === 'bold' ? 'normal' : 'bold' }, true)}>B</button><button type="button" className={selected.fontStyle === 'italic' ? 'active' : ''} onClick={() => update(selectedId, { fontStyle: selected.fontStyle === 'italic' ? 'normal' : 'italic' }, true)}>I</button><button type="button" className={selected.textDecoration === 'underline' ? 'active' : ''} onClick={() => update(selectedId, { textDecoration: selected.textDecoration === 'underline' ? 'none' : 'underline' }, true)}>U</button><input aria-label="Cor do texto" type="color" value={selected.color || '#f5f7fa'} onChange={event => update(selectedId, { color: event.target.value }, true)} /><select value={selected.variant || 'paragraph'} onChange={event => update(selectedId, { variant: event.target.value as WhiteboardElement['variant'] }, true)}><option value="paragraph">Parágrafo</option><option value="heading">Título</option><option value="quote">Citação</option><option value="code">Código</option><option value="callout">Destaque</option></select><select value={selected.listStyle || 'plain'} onChange={event => update(selectedId, { listStyle: event.target.value as WhiteboardElement['listStyle'] }, true)}><option value="plain">Texto</option><option value="bullets">Bolinhas</option><option value="tasks">Tarefas</option></select></>}
      {selected.type === 'image' && <><select value={selected.objectFit || 'contain'} onChange={event => update(selectedId, { objectFit: event.target.value as WhiteboardElement['objectFit'] }, true)}><option value="contain">Conter</option><option value="cover">Preencher</option><option value="fill">Esticar</option></select><label className="study-opacity">Opacidade <input type="range" min="0.2" max="1" step=".05" value={selected.opacity ?? 1} onChange={event => update(selectedId, { opacity: Number(event.target.value) }, true)} /></label></>}
      <button type="button" onClick={() => startEditing(selected, selectedId)} disabled={selected.type === 'image'}>Editar</button><button type="button" onClick={() => onDuplicateElement?.(selectedId)}>Duplicar</button><button type="button" className={selected.locked ? 'active' : ''} onClick={() => update(selectedId, { locked: !selected.locked }, true)}>{selected.locked ? 'Desbloquear' : 'Fixar'}</button><button type="button" className="danger" onClick={() => { onDeleteElement?.(selectedId); setSelectedId('') }}>Excluir</button>
    </div>}
    <div ref={viewportRef} tabIndex={0} className={`study-canvas-viewport${gridVisible ? ' has-grid' : ''}`} onPaste={handlePaste} onWheel={onWheel} onPointerMove={onPointerMove} onPointerUp={finishInteraction} onPointerCancel={finishInteraction} onPointerDown={event => { if (event.button !== 0) return; event.currentTarget.focus(); setMenu(null); setSelectedId(''); viewportRef.current?.setPointerCapture(event.pointerId); interactionRef.current = { kind: 'pan', pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: pan.x, panY: pan.y } }} onContextMenu={openMenu}>
      <div className="study-canvas-world" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }}>
        {!sessionId ? <p className="study-canvas-empty">Crie ou selecione uma sessão para começar.</p> : elements.length === 0 ? <p className="study-canvas-empty">Use o botão direito ou a barra acima para adicionar conteúdo.</p> : sortedElements.map(({ element, index }) => {
          const id = elementId(element, index)
          const isSelected = id === selectedId
          const locked = Boolean(element.locked)
          return <div key={id} data-study-element={id} className={`study-element${element.type === 'image' ? ' study-element-image-wrap' : ' study-element-text'}${isSelected ? ' is-selected' : ''}${locked ? ' is-locked' : ''}`} style={{ left: element.x || 0, top: element.y || 0, width: elementWidth(element), height: elementHeight(element), zIndex: element.zIndex || 0, color: element.color || '#f5f7fa', fontSize: element.size || 16, backgroundColor: element.backgroundColor || undefined, fontWeight: element.fontWeight || 'normal', fontStyle: element.fontStyle || 'normal', textAlign: element.textAlign || 'left', fontFamily: element.fontFamily || undefined, textDecoration: element.textDecoration || 'none', opacity: element.opacity ?? 1, transform: `rotate(${element.rotation || 0}deg)` }} onPointerDown={event => { if (event.button !== 0) return; event.stopPropagation(); setSelectedId(id); setMenu(null); if (locked || editingId === id) return; viewportRef.current?.setPointerCapture(event.pointerId); interactionRef.current = { kind: 'move', pointerId: event.pointerId, id, startX: event.clientX, startY: event.clientY, originX: element.x || 0, originY: element.y || 0, patch: {} } }} onDoubleClick={event => { event.stopPropagation(); startEditing(element, id) }} onContextMenu={event => { event.stopPropagation(); openMenu(event) }}>
            {renderContent(element, id)}
            {isSelected && !locked && resizeHandles.map(corner => <button key={corner} type="button" aria-label={`Redimensionar ${corner}`} className={`study-element-resize study-resize-${corner}`} onPointerDown={event => { event.stopPropagation(); viewportRef.current?.setPointerCapture(event.pointerId); interactionRef.current = { kind: 'resize', pointerId: event.pointerId, id, corner, startX: event.clientX, startY: event.clientY, originX: element.x || 0, originY: element.y || 0, width: elementWidth(element), height: elementHeight(element), ratio: elementWidth(element) / elementHeight(element), patch: {} } }} />)}
          </div>
        })}
      </div>
    </div>
    {menu && <div className="study-context-menu" style={{ left: Math.min(menu.clientX, window.innerWidth - 250), top: Math.min(menu.clientY, window.innerHeight - 300) }} role="menu" onPointerDown={event => event.stopPropagation()}>
      {menu.targetId && <><button type="button" onClick={() => { const item = elements.find((element, index) => elementId(element, index) === menu.targetId); if (item) startEditing(item, menu.targetId || ''); setMenu(null) }}>Editar com dois cliques</button><button type="button" onClick={() => { onDuplicateElement?.(menu.targetId || ''); setMenu(null) }}>Duplicar elemento</button><button type="button" onClick={() => { update(menu.targetId || '', { locked: !(elements.find((element, index) => elementId(element, index) === menu.targetId)?.locked) }, true); setMenu(null) }}>Fixar/desbloquear</button><button type="button" className="study-context-danger" onClick={() => { onDeleteElement?.(menu.targetId || ''); setSelectedId(''); setMenu(null) }}>Excluir elemento</button><div className="study-context-separator" /></>}
      <button type="button" onClick={() => { addTextAndEdit(menu.x, menu.y, 'plain'); setMenu(null) }}>Adicionar texto</button><button type="button" onClick={() => { addTextAndEdit(menu.x, menu.y, 'bullets'); setMenu(null) }}>Lista com bolinhas</button><button type="button" onClick={() => { addTextAndEdit(menu.x, menu.y, 'ordered'); setMenu(null) }}>Lista ordenada</button><button type="button" onClick={() => { addTextAndEdit(menu.x, menu.y, 'tasks'); setMenu(null) }}>Lista de tarefas</button><button type="button" onClick={() => { onAddImage?.(menu.x, menu.y); setMenu(null) }}>Adicionar imagem</button><div className="study-context-separator" /><button type="button" onClick={() => { setMenu(null); onRefresh?.() }}>Atualizar quadro</button>{onClearCanvas && <button type="button" className="study-context-danger" onClick={() => { onClearCanvas(); setMenu(null) }}>Limpar quadro</button>}
    </div>}
  </div>
}
