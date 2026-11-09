import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Check,
  CheckSquare,
  Square,
  Plus,
  Trash2,
  Calendar,
  Flame,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronRight,
  ListChecks,
  Dumbbell,
  BookOpen,
  RefreshCw,
  Zap,
  Info,
} from 'lucide-react'
import { panelRequest } from '../utils/panelApi'
import type { LifeOSWindowParams, WindowComponentProps } from './registry'

// Tipos para Checklists
export type ChecklistItem = {
  id: string
  list_id: string
  text: string
  quantity?: string
  condition_note?: string
  completed: boolean
  position: number
  created_at: number
  updated_at: number
}

export type Checklist = {
  id: string
  title: string
  archived: boolean
  created_at: number
  updated_at: number
  items?: ChecklistItem[]
  pending_count?: number
  completed_count?: number
  total_count?: number
}

// Tipos para Hábitos Modulares
export type Habit = {
  id: string
  name: string
  category: string
  routine_block: string
  frequency_type: string
  days_of_week: string[]
  start_time: string
  time_exceptions: Record<string, string>
  items_list: string[]
  day_slots?: Record<string, any>
  today_slot?: any
  effective_title?: string
  muscle_group?: string
  current_streak: number
  best_streak: number
  completed_today: boolean
}

const WEEK_DAYS = [
  { code: 'mon', label: 'Seg', full: 'Segunda-feira', index: 0 },
  { code: 'tue', label: 'Ter', full: 'Terça-feira', index: 1 },
  { code: 'wed', label: 'Qua', full: 'Quarta-feira', index: 2 },
  { code: 'thu', label: 'Qui', full: 'Quinta-feira', index: 3 },
  { code: 'fri', label: 'Sex', full: 'Sexta-feira', index: 4 },
  { code: 'sat', label: 'Sáb', full: 'Sábado', index: 5 },
  { code: 'sun', label: 'Dom', full: 'Domingo', index: 6 },
]

export function LifeOSWindow({ params }: WindowComponentProps<LifeOSWindowParams>) {
  const [activeTab, setActiveTab] = useState<'checklists' | 'habitos'>(
    params.tab === 'habitos' ? 'habitos' : 'checklists'
  )

  // ── ESTADO DE CHECKLISTS ────────────────────────────────────────────────
  const [checklists, setChecklists] = useState<Checklist[]>([])
  const [activeListId, setActiveListId] = useState<string>(params.list_id || '')
  const [currentList, setCurrentList] = useState<Checklist | null>(null)
  const [spokenInput, setSpokenInput] = useState('')
  const [newListTitle, setNewListTitle] = useState('')
  const [showNewListInput, setShowNewListInput] = useState(false)
  const [completedExpanded, setCompletedExpanded] = useState(true)
  const [listsLoading, setListsLoading] = useState(false)

  // ── ESTADO DE HÁBITOS ──────────────────────────────────────────────────
  const [habits, setHabits] = useState<Habit[]>([])
  const [habitsLoading, setHabitsLoading] = useState(false)
  const todayDayIndex = (new Date().getDay() + 6) % 7 // 0 = seg, 6 = dom
  const todayCode = WEEK_DAYS[todayDayIndex].code
  const [selectedDayCode, setSelectedDayCode] = useState<string>(todayCode)

  // Edição de slot
  const [editingSlotHabit, setEditingSlotHabit] = useState<Habit | null>(null)
  const [slotValue, setSlotValue] = useState('')
  const [slotMuscleGroup, setSlotMuscleGroup] = useState('')

  // ── CARREGAMENTO DE CHECKLISTS ─────────────────────────────────────────
  const fetchChecklists = useCallback(async () => {
    try {
      setListsLoading(true)
      const data = await panelRequest<{ ok: boolean; checklists: Checklist[] }>('/api/checklists')
      if (data.ok && Array.isArray(data.checklists)) {
        setChecklists(data.checklists)
        if (data.checklists.length > 0 && !activeListId) {
          setActiveListId(data.checklists[0].id)
        }
      }
    } catch (err) {
      console.error('Erro ao carregar checklists:', err)
    } finally {
      setListsLoading(false)
    }
  }, [activeListId])

  const fetchActiveList = useCallback(async (listId: string) => {
    if (!listId) return
    try {
      const data = await panelRequest<{ ok: boolean; checklist: Checklist }>(`/api/checklists/${listId}`)
      if (data.ok && data.checklist) {
        setCurrentList(data.checklist)
      }
    } catch (err) {
      console.error(`Erro ao carregar checklist ${listId}:`, err)
    }
  }, [])

  useEffect(() => {
    fetchChecklists()
  }, [fetchChecklists])

  useEffect(() => {
    if (activeListId) {
      fetchActiveList(activeListId)
    } else {
      setCurrentList(null)
    }
  }, [activeListId, fetchActiveList])

  // ── AÇÕES DE CHECKLISTS ────────────────────────────────────────────────
  const handleCreateList = async () => {
    if (!newListTitle.trim()) return
    try {
      const data = await panelRequest<{ ok: boolean; checklist: Checklist }>('/api/checklists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newListTitle.trim() }),
      })
      if (data.ok && data.checklist) {
        setNewListTitle('')
        setShowNewListInput(false)
        await fetchChecklists()
        setActiveListId(data.checklist.id)
      }
    } catch (err) {
      alert(`Falha ao criar lista: ${err}`)
    }
  }

  const handleDeleteList = async (listId: string) => {
    if (!confirm('Deseja realmente excluir esta lista?')) return
    try {
      await panelRequest(`/api/checklists/${listId}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const remaining = checklists.filter((l) => l.id !== listId)
      setChecklists(remaining)
      setActiveListId(remaining.length > 0 ? remaining[0].id : '')
    } catch (err) {
      alert(`Falha ao excluir lista: ${err}`)
    }
  }

  const handleAddSpokenItems = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!spokenInput.trim() || !activeListId) return
    try {
      const text = spokenInput
      setSpokenInput('')
      const data = await panelRequest<{ ok: boolean; checklist: Checklist }>(
        `/api/checklists/${activeListId}/items`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        }
      )
      if (data.ok && data.checklist) {
        setCurrentList(data.checklist)
        fetchChecklists()
      }
    } catch (err) {
      alert(`Falha ao adicionar itens: ${err}`)
    }
  }

  const handleToggleItem = async (itemId: string, currentCompleted: boolean) => {
    if (!currentList) return
    // Atualização otimista com afundamento (sink)
    const newCompleted = !currentCompleted
    const updatedItems = (currentList.items || []).map((it) =>
      it.id === itemId ? { ...it, completed: newCompleted } : it
    )
    // Ordena otimisticamente: pendentes primeiro, concluídos ao final
    updatedItems.sort((a, b) => Number(a.completed) - Number(b.completed))
    setCurrentList({ ...currentList, items: updatedItems })

    try {
      const data = await panelRequest<{ ok: boolean; checklist: Checklist }>(
        `/api/checklists/${currentList.id}/toggle`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_id: itemId, completed: newCompleted }),
        }
      )
      if (data.ok && data.checklist) {
        setCurrentList(data.checklist)
        fetchChecklists()
      }
    } catch (err) {
      console.error('Falha ao alternar item:', err)
      fetchActiveList(currentList.id)
    }
  }

  const handleDeleteItem = async (itemId: string) => {
    if (!currentList) return
    try {
      await panelRequest(`/api/checklists/items/${itemId}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const updatedItems = (currentList.items || []).filter((it) => it.id !== itemId)
      setCurrentList({ ...currentList, items: updatedItems })
      fetchChecklists()
    } catch (err) {
      alert(`Falha ao remover item: ${err}`)
    }
  }

  // ── CARREGAMENTO DE HÁBITOS ───────────────────────────────────────────
  const fetchHabits = useCallback(async () => {
    try {
      setHabitsLoading(true)
      const data = await panelRequest<{ ok: boolean; habits: Habit[] }>('/api/lifeos/habits')
      if (data.ok && Array.isArray(data.habits)) {
        setHabits(data.habits)
      }
    } catch (err) {
      console.error('Erro ao carregar hábitos:', err)
    } finally {
      setHabitsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'habitos') {
      fetchHabits()
    }
  }, [activeTab, fetchHabits])

  const handleToggleHabitToday = async (habitId: string) => {
    try {
      const target = habits.find((h) => h.id === habitId)
      const nextCompleted = !target?.completed_today
      setHabits((prev) =>
        prev.map((h) => (h.id === habitId ? { ...h, completed_today: nextCompleted } : h))
      )
      const data = await panelRequest<{ ok: boolean; habit: Habit }>(
        `/api/lifeos/habits/${habitId}/toggle`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ completed: nextCompleted }),
        }
      )
      if (data.ok && data.habit) {
        setHabits((prev) => prev.map((h) => (h.id === habitId ? data.habit : h)))
      }
    } catch (err) {
      console.error('Falha ao alternar hábito:', err)
      fetchHabits()
    }
  }

  const handleSaveSlot = async () => {
    if (!editingSlotHabit) return
    try {
      const payload: any = slotMuscleGroup.trim()
        ? { title: slotValue.trim(), muscle_group: slotMuscleGroup.trim() }
        : slotValue.trim()

      await panelRequest(`/api/lifeos/habits/${editingSlotHabit.id}/slot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day: selectedDayCode, slot: payload }),
      })
      setEditingSlotHabit(null)
      setSlotValue('')
      setSlotMuscleGroup('')
      fetchHabits()
    } catch (err) {
      alert(`Falha ao salvar slot: ${err}`)
    }
  }

  const handleContextualAutoCheck = async () => {
    try {
      const text = prompt('Digite uma mensagem contextual para testar o auto-check (ex.: "Bom dia, Jarvis" ou "Bebi água"):', 'Bom dia, Jarvis')
      if (!text) return
      const data = await panelRequest<{ ok: boolean; checked: any[]; count: number }>('/api/lifeos/habits/auto-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (data.ok) {
        alert(
          data.count > 0
            ? `${data.count} hábito(s) marcado(s) automaticamente!`
            : 'Nenhum hábito foi marcado para o texto fornecido.'
        )
        fetchHabits()
      }
    } catch (err) {
      alert(`Erro no auto-check: ${err}`)
    }
  }

  // Separação de itens pendentes e concluídos (Sink behavior)
  const pendingItems = useMemo(
    () => (currentList?.items || []).filter((it) => !it.completed),
    [currentList]
  )
  const completedItems = useMemo(
    () => (currentList?.items || []).filter((it) => it.completed),
    [currentList]
  )

  // Hábitos filtrados pelo dia selecionado
  const filteredHabits = useMemo(() => {
    return habits.filter((h) => {
      const days = h.days_of_week || []
      return days.includes(selectedDayCode)
    })
  }, [habits, selectedDayCode])

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        backgroundColor: 'var(--ws-bg)',
        color: 'var(--ws-text)',
        fontFamily: 'inherit',
      }}
    >
      {/* ── BARRA SUPERIOR / NAVEGAÇÃO ─────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 18px',
          borderBottom: '1px solid var(--ws-border)',
          backgroundColor: 'var(--ws-panel)',
          gap: '12px',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Zap size={20} color="var(--ws-accent)" />
          <span style={{ fontWeight: 600, fontSize: '15px', letterSpacing: '-0.3px' }}>
            Life OS 2.0
          </span>
        </div>

        {/* Abas */}
        <div
          style={{
            display: 'flex',
            backgroundColor: 'var(--ws-bg)',
            border: '1px solid var(--ws-border)',
            borderRadius: '8px',
            padding: '3px',
            gap: '4px',
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab('checklists')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '6px',
              border: 0,
              cursor: 'pointer',
              backgroundColor: activeTab === 'checklists' ? 'var(--ws-accent)' : 'transparent',
              color: activeTab === 'checklists' ? '#141e18' : 'var(--ws-muted)',
              transition: 'all 0.15s ease',
            }}
          >
            <ListChecks size={14} />
            Checklists Inteligentes
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('habitos')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '6px',
              border: 0,
              cursor: 'pointer',
              backgroundColor: activeTab === 'habitos' ? 'var(--ws-accent)' : 'transparent',
              color: activeTab === 'habitos' ? '#141e18' : 'var(--ws-muted)',
              transition: 'all 0.15s ease',
            }}
          >
            <Calendar size={14} />
            Hábitos Modulares
          </button>
        </div>

        <button
          type="button"
          onClick={() => (activeTab === 'checklists' ? fetchChecklists() : fetchHabits())}
          title="Recarregar dados"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            border: '1px solid var(--ws-border)',
            backgroundColor: 'var(--ws-field)',
            color: 'var(--ws-muted)',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} className={listsLoading || habitsLoading ? 'spin' : ''} />
        </button>
      </div>

      {/* ── CONTEÚDO PRINCIPAL ──────────────────────────────────────────── */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex' }}>
        {activeTab === 'checklists' && (
          <div style={{ display: 'flex', width: '100%', height: '100%' }}>
            {/* Sidebar das Listas */}
            <div
              style={{
                width: '240px',
                borderRight: '1px solid var(--ws-border)',
                backgroundColor: 'var(--ws-panel)',
                padding: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                overflowY: 'auto',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '4px',
                }}
              >
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    color: 'var(--ws-muted)',
                    letterSpacing: '0.05em',
                  }}
                >
                  Minhas Listas
                </span>
                <button
                  type="button"
                  onClick={() => setShowNewListInput(true)}
                  style={{
                    border: '1px solid var(--ws-border)',
                    borderRadius: '6px',
                    background: 'var(--ws-field)',
                    color: 'var(--ws-text)',
                    padding: '3px 8px',
                    fontSize: '11px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <Plus size={12} /> Nova
                </button>
              </div>

              {showNewListInput && (
                <div style={{ display: 'flex', gap: '4px', marginBottom: '6px' }}>
                  <input
                    type="text"
                    placeholder="Título da lista..."
                    value={newListTitle}
                    onChange={(e) => setNewListTitle(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateList()}
                    autoFocus
                    style={{
                      flex: 1,
                      padding: '5px 8px',
                      fontSize: '12px',
                      borderRadius: '5px',
                      border: '1px solid var(--ws-accent)',
                      background: 'var(--ws-bg)',
                      color: 'var(--ws-text)',
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleCreateList}
                    style={{
                      border: 0,
                      borderRadius: '5px',
                      backgroundColor: 'var(--ws-accent)',
                      color: '#141e18',
                      padding: '0 8px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    OK
                  </button>
                </div>
              )}

              {checklists.map((list) => {
                const isActive = list.id === activeListId
                return (
                  <button
                    key={list.id}
                    type="button"
                    onClick={() => setActiveListId(list.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '9px 12px',
                      borderRadius: '7px',
                      border: '1px solid',
                      borderColor: isActive ? 'var(--ws-accent)' : 'var(--ws-border)',
                      backgroundColor: isActive ? 'var(--ws-accent-soft)' : 'var(--ws-field)',
                      color: isActive ? 'var(--ws-accent)' : 'var(--ws-text)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: '13px',
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {list.title}
                    </span>
                    {(list.pending_count ?? 0) > 0 && (
                      <span
                        style={{
                          backgroundColor: isActive ? 'var(--ws-accent)' : 'var(--ws-border)',
                          color: isActive ? '#141e18' : 'var(--ws-muted)',
                          padding: '1px 6px',
                          borderRadius: '10px',
                          fontSize: '10px',
                          fontWeight: 600,
                        }}
                      >
                        {list.pending_count}
                      </span>
                    )}
                  </button>
                )
              })}

              {checklists.length === 0 && !listsLoading && (
                <div style={{ fontSize: '12px', color: 'var(--ws-muted)', fontStyle: 'italic', padding: '8px' }}>
                  Nenhuma lista criada ainda.
                </div>
              )}
            </div>

            {/* Painel da Lista Ativa (Google Keep style) */}
            <div
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
                backgroundColor: 'var(--ws-bg)',
              }}
            >
              {currentList ? (
                <>
                  {/* Cabeçalho da Lista */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '16px 24px',
                      borderBottom: '1px solid var(--ws-border)',
                    }}
                  >
                    <div>
                      <h2
                        style={{
                          margin: 0,
                          fontSize: '18px',
                          fontWeight: 600,
                          color: 'var(--ws-text)',
                        }}
                      >
                        {currentList.title}
                      </h2>
                      <div
                        style={{
                          fontSize: '12px',
                          color: 'var(--ws-muted)',
                          marginTop: '3px',
                          display: 'flex',
                          gap: '10px',
                        }}
                      >
                        <span>{pendingItems.length} pendente(s)</span>
                        <span>•</span>
                        <span>{completedItems.length} concluído(s)</span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDeleteList(currentList.id)}
                      title="Excluir lista"
                      style={{
                        background: 'transparent',
                        border: '1px solid var(--ws-border)',
                        color: 'var(--ws-muted)',
                        borderRadius: '6px',
                        padding: '6px 10px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px',
                        fontSize: '12px',
                      }}
                    >
                      <Trash2 size={13} />
                      Excluir Lista
                    </button>
                  </div>

                  {/* Input Rápido em Linguagem Natural */}
                  <form
                    onSubmit={handleAddSpokenItems}
                    style={{
                      padding: '14px 24px',
                      borderBottom: '1px solid var(--ws-border)',
                      backgroundColor: 'var(--ws-panel)',
                      display: 'flex',
                      gap: '8px',
                    }}
                  >
                    <input
                      type="text"
                      placeholder="Adicionar itens com voz ou texto (ex.: 1 saco de arroz, 10 batatas chips, 2 coca colas se abaixo de R$ 10)..."
                      value={spokenInput}
                      onChange={(e) => setSpokenInput(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '9px 12px',
                        fontSize: '13px',
                        borderRadius: '7px',
                        border: '1px solid var(--ws-border)',
                        backgroundColor: 'var(--ws-field)',
                        color: 'var(--ws-text)',
                      }}
                    />
                    <button
                      type="submit"
                      disabled={!spokenInput.trim()}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '9px 16px',
                        fontSize: '13px',
                        fontWeight: 600,
                        borderRadius: '7px',
                        border: 0,
                        backgroundColor: 'var(--ws-accent)',
                        color: '#141e18',
                        cursor: spokenInput.trim() ? 'pointer' : 'not-allowed',
                        opacity: spokenInput.trim() ? 1 : 0.5,
                      }}
                    >
                      <Plus size={15} />
                      Adicionar
                    </button>
                  </form>

                  {/* Lista de Itens com Afundamento (Sink) */}
                  <div
                    style={{
                      flex: 1,
                      overflowY: 'auto',
                      padding: '16px 24px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    {/* Itens Pendentes */}
                    {pendingItems.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          backgroundColor: 'var(--ws-panel)',
                          border: '1px solid var(--ws-border)',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => handleToggleItem(item.id, false)}
                          style={{
                            background: 'transparent',
                            border: 0,
                            padding: 0,
                            cursor: 'pointer',
                            color: 'var(--ws-muted)',
                            display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          <Square size={18} />
                        </button>

                        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '14px', color: 'var(--ws-text)' }}>{item.text}</span>

                          {item.quantity && (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                padding: '2px 8px',
                                borderRadius: '999px',
                                backgroundColor: 'var(--ws-accent-soft)',
                                color: 'var(--ws-accent)',
                                fontSize: '11px',
                                fontWeight: 600,
                              }}
                            >
                              {item.quantity}
                            </span>
                          )}

                          {item.condition_note && (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '2px 8px',
                                borderRadius: '999px',
                                backgroundColor: 'rgba(234, 179, 8, 0.1)',
                                color: '#eab308',
                                fontSize: '11px',
                              }}
                            >
                              <Info size={11} />
                              {item.condition_note}
                            </span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleDeleteItem(item.id)}
                          style={{
                            background: 'transparent',
                            border: 0,
                            color: 'var(--ws-muted)',
                            cursor: 'pointer',
                            padding: '4px',
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}

                    {pendingItems.length === 0 && completedItems.length === 0 && (
                      <div
                        style={{
                          textAlign: 'center',
                          padding: '40px 20px',
                          color: 'var(--ws-muted)',
                          fontSize: '13px',
                        }}
                      >
                        Nenhum item nesta lista. Use a barra acima para ditar ou digitar itens!
                      </div>
                    )}

                    {/* Seção Afundada: Concluídos (Sink) */}
                    {completedItems.length > 0 && (
                      <div style={{ marginTop: '16px' }}>
                        <button
                          type="button"
                          onClick={() => setCompletedExpanded(!completedExpanded)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: 'transparent',
                            border: 0,
                            padding: '6px 0',
                            fontSize: '12px',
                            fontWeight: 600,
                            color: 'var(--ws-muted)',
                            cursor: 'pointer',
                          }}
                        >
                          {completedExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          Concluídos ({completedItems.length})
                        </button>

                        {completedExpanded && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                            {completedItems.map((item) => (
                              <div
                                key={item.id}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '12px',
                                  padding: '8px 14px',
                                  borderRadius: '8px',
                                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                                  border: '1px solid var(--ws-border)',
                                  opacity: 0.65,
                                }}
                              >
                                <button
                                  type="button"
                                  onClick={() => handleToggleItem(item.id, true)}
                                  style={{
                                    background: 'transparent',
                                    border: 0,
                                    padding: 0,
                                    cursor: 'pointer',
                                    color: 'var(--ws-accent)',
                                    display: 'flex',
                                    alignItems: 'center',
                                  }}
                                >
                                  <CheckSquare size={18} />
                                </button>

                                <div
                                  style={{
                                    flex: 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    textDecoration: 'line-through',
                                    color: 'var(--ws-muted)',
                                    fontSize: '13px',
                                  }}
                                >
                                  <span>{item.text}</span>
                                  {item.quantity && <span>({item.quantity})</span>}
                                </div>

                                <button
                                  type="button"
                                  onClick={() => handleDeleteItem(item.id)}
                                  style={{
                                    background: 'transparent',
                                    border: 0,
                                    color: 'var(--ws-muted)',
                                    cursor: 'pointer',
                                    padding: '4px',
                                  }}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    color: 'var(--ws-muted)',
                    gap: '12px',
                  }}
                >
                  <ListChecks size={36} />
                  <span>Selecione uma lista ou crie uma nova para começar.</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── ABA DE HÁBITOS MODULARES ──────────────────────────────────── */}
        {activeTab === 'habitos' && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              width: '100%',
              height: '100%',
              overflowY: 'auto',
              padding: '20px 24px',
              gap: '20px',
            }}
          >
            {/* Seletor de Dia da Semana */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', gap: '6px' }}>
                {WEEK_DAYS.map((day) => {
                  const isSelected = day.code === selectedDayCode
                  const isToday = day.code === todayCode
                  return (
                    <button
                      key={day.code}
                      type="button"
                      onClick={() => setSelectedDayCode(day.code)}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        minWidth: '54px',
                        padding: '8px 10px',
                        borderRadius: '8px',
                        border: '1px solid',
                        borderColor: isSelected ? 'var(--ws-accent)' : 'var(--ws-border)',
                        backgroundColor: isSelected ? 'var(--ws-accent-soft)' : 'var(--ws-panel)',
                        color: isSelected ? 'var(--ws-accent)' : 'var(--ws-text)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span style={{ fontSize: '13px', fontWeight: 600 }}>{day.label}</span>
                      {isToday && (
                        <span
                          style={{
                            fontSize: '9px',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            marginTop: '2px',
                            color: isSelected ? 'var(--ws-accent)' : 'var(--ws-info)',
                          }}
                        >
                          Hoje
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>

              <button
                type="button"
                onClick={handleContextualAutoCheck}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 12px',
                  borderRadius: '7px',
                  border: '1px solid var(--ws-border)',
                  backgroundColor: 'var(--ws-panel)',
                  color: 'var(--ws-accent)',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <Sparkles size={14} />
                Testar Auto-Check Contextual
              </button>
            </div>

            {/* Lista de Hábitos do Dia */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ws-muted)', textTransform: 'uppercase' }}>
                  Hábitos programados para {WEEK_DAYS.find((d) => d.code === selectedDayCode)?.full}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--ws-muted)' }}>
                  {filteredHabits.length} hábito(s)
                </span>
              </div>

              {filteredHabits.map((habit) => {
                const daySlot = (habit.day_slots || {})[selectedDayCode]
                const slotTitle = typeof daySlot === 'string' ? daySlot : daySlot?.title || daySlot?.activity
                const slotMuscle = typeof daySlot === 'object' ? daySlot?.muscle_group : ''

                return (
                  <div
                    key={habit.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '14px 18px',
                      borderRadius: '10px',
                      border: '1px solid',
                      borderColor: habit.completed_today ? 'var(--ws-accent-line)' : 'var(--ws-border)',
                      backgroundColor: 'var(--ws-panel)',
                      gap: '16px',
                    }}
                  >
                    {/* Botão de Check-in para Hoje */}
                    <button
                      type="button"
                      onClick={() => handleToggleHabitToday(habit.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '26px',
                        height: '26px',
                        borderRadius: '7px',
                        border: '1px solid',
                        borderColor: habit.completed_today ? 'var(--ws-accent)' : 'var(--ws-border)',
                        backgroundColor: habit.completed_today ? 'var(--ws-accent)' : 'transparent',
                        color: habit.completed_today ? '#141e18' : 'transparent',
                        cursor: 'pointer',
                        flexShrink: 0,
                      }}
                    >
                      <Check size={16} strokeWidth={3} />
                    </button>

                    {/* Informações do Hábito */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ws-text)' }}>
                          {habit.name}
                        </span>

                        {habit.category && (
                          <span
                            style={{
                              fontSize: '11px',
                              padding: '2px 7px',
                              borderRadius: '4px',
                              backgroundColor: 'var(--ws-field)',
                              color: 'var(--ws-muted)',
                            }}
                          >
                            {habit.category}
                          </span>
                        )}

                        <span
                          style={{
                            fontSize: '11px',
                            color: 'var(--ws-muted)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '3px',
                          }}
                        >
                          <Clock size={11} /> {habit.start_time || '15:00'}
                        </span>
                      </div>

                      {/* Substituição modular do dia (Slot) */}
                      {slotTitle && (
                        <div
                          style={{
                            marginTop: '6px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '3px 10px',
                            borderRadius: '6px',
                            backgroundColor: 'var(--ws-accent-soft)',
                            border: '1px solid var(--ws-accent-line)',
                            color: 'var(--ws-accent)',
                            fontSize: '12px',
                            fontWeight: 500,
                          }}
                        >
                          {slotMuscle ? <Dumbbell size={13} /> : <BookOpen size={13} />}
                          <span>
                            Slot {WEEK_DAYS.find((d) => d.code === selectedDayCode)?.label}:{' '}
                            <strong>{slotTitle}</strong>
                            {slotMuscle ? ` (${slotMuscle})` : ''}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Streak & Botão de Configurar Slot */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '12px',
                          color: habit.current_streak > 0 ? '#f97316' : 'var(--ws-muted)',
                          fontWeight: 600,
                        }}
                      >
                        <Flame size={15} />
                        <span>{habit.current_streak}d</span>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          setEditingSlotHabit(habit)
                          setSlotValue(slotTitle || '')
                          setSlotMuscleGroup(slotMuscle || '')
                        }}
                        style={{
                          padding: '5px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--ws-border)',
                          backgroundColor: 'var(--ws-field)',
                          color: 'var(--ws-text)',
                          fontSize: '11px',
                          cursor: 'pointer',
                        }}
                      >
                        Configurar Slot
                      </button>
                    </div>
                  </div>
                )
              })}

              {filteredHabits.length === 0 && !habitsLoading && (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '40px',
                    color: 'var(--ws-muted)',
                    fontSize: '13px',
                  }}
                >
                  Nenhum hábito configurado para este dia da semana.
                </div>
              )}
            </div>

            {/* Modal simples de Edição de Slot */}
            {editingSlotHabit && (
              <div
                style={{
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  backgroundColor: 'rgba(0, 0, 0, 0.6)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 1000,
                }}
              >
                <div
                  style={{
                    backgroundColor: 'var(--ws-panel)',
                    border: '1px solid var(--ws-border)',
                    borderRadius: '10px',
                    padding: '20px',
                    width: '380px',
                    maxWidth: '90%',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '14px',
                  }}
                >
                  <h3 style={{ margin: 0, fontSize: '15px', color: 'var(--ws-text)' }}>
                    Slot de {WEEK_DAYS.find((d) => d.code === selectedDayCode)?.full}: {editingSlotHabit.name}
                  </h3>

                  <div>
                    <label style={{ display: 'block', fontSize: '11px', color: 'var(--ws-muted)', marginBottom: '4px' }}>
                      Atividade / Substituição do Dia
                    </label>
                    <input
                      type="text"
                      placeholder="Ex: 20min de inglês, Treino A, 30min xadrez..."
                      value={slotValue}
                      onChange={(e) => setSlotValue(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        fontSize: '13px',
                        borderRadius: '6px',
                        border: '1px solid var(--ws-border)',
                        backgroundColor: 'var(--ws-field)',
                        color: 'var(--ws-text)',
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '11px', color: 'var(--ws-muted)', marginBottom: '4px' }}>
                      Grupo Muscular / Foco (opcional)
                    </label>
                    <input
                      type="text"
                      placeholder="Ex: Peito e Tríceps, Conversação, Táticas..."
                      value={slotMuscleGroup}
                      onChange={(e) => setSlotMuscleGroup(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        fontSize: '13px',
                        borderRadius: '6px',
                        border: '1px solid var(--ws-border)',
                        backgroundColor: 'var(--ws-field)',
                        color: 'var(--ws-text)',
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                    <button
                      type="button"
                      onClick={() => setEditingSlotHabit(null)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--ws-border)',
                        backgroundColor: 'transparent',
                        color: 'var(--ws-muted)',
                        fontSize: '12px',
                        cursor: 'pointer',
                      }}
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveSlot}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '6px',
                        border: 0,
                        backgroundColor: 'var(--ws-accent)',
                        color: '#141e18',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Salvar Slot
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

