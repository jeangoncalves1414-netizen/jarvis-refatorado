export type StudyMode = 'learn' | 'questions' | 'review' | 'feynman' | 'quiz' | 'progress' | null

const MODES: { id: StudyMode; label: string; icon: string }[] = [
  { id: 'learn', label: 'Aprender', icon: '◎' },
  { id: 'questions', label: 'Questões', icon: '?' },
  { id: 'review', label: 'Revisar', icon: '↻' },
  { id: 'feynman', label: 'Feynman', icon: '✎' },
  { id: 'quiz', label: 'Quiz', icon: '★' },
  { id: 'progress', label: 'Progresso', icon: '◉' },
]

type StudyToolbarProps = {
  activeMode: StudyMode
  onModeChange: (mode: StudyMode) => void
}

export function StudyToolbar({ activeMode, onModeChange }: StudyToolbarProps) {
  return (
    <nav className="study-toolbar" aria-label="Modos de estudo">
      {MODES.map(mode => (
        <button
          key={mode.id}
          type="button"
          className={activeMode === mode.id ? 'study-mode-active' : ''}
          onClick={() => onModeChange(activeMode === mode.id ? null : mode.id)}
          title={mode.label}
        >
          <span>{mode.icon}</span>
          {mode.label}
        </button>
      ))}
    </nav>
  )
}
