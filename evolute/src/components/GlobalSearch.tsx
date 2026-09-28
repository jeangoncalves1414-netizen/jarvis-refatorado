import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, X, Dumbbell, CheckSquare, GraduationCap, 
  BookOpen, ShieldAlert, Brain, Calendar, Settings,
  ArrowRight, CornerDownLeft, Sparkles
} from 'lucide-react';
import { TabType, Habit, Subject, Book, BookQuote, WorkoutExercise, ViceItem } from '../types';

interface GlobalSearchProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: TabType, date?: string) => void;
  habits: Habit[];
  subjects: Subject[];
  books: Book[];
  quotes: BookQuote[];
  workouts: WorkoutExercise[];
  vices: ViceItem[];
}

interface SearchResultItem {
  id: string;
  category: 'módulo' | 'treino' | 'hábito' | 'estudo' | 'leitura' | 'vício';
  title: string;
  subtitle?: string;
  tab: TabType;
  date?: string;
  icon: React.ReactNode;
}

const STATIC_MODULES: SearchResultItem[] = [
  { id: 'mod-inicio', category: 'módulo', title: 'Início / Dashboard Geral', subtitle: 'Visão unificada do dia, métricas e vitórias', tab: 'inicio', icon: <Sparkles className="w-4 h-4" /> },
  { id: 'mod-treino', category: 'módulo', title: 'Treino, Cargas & Shape', subtitle: 'Volume de séries, PRs, álbum de evolução e divisão', tab: 'treino', icon: <Dumbbell className="w-4 h-4" /> },
  { id: 'mod-habitos', category: 'módulo', title: 'Hábitos & Disciplina', subtitle: 'Check diário, heatmap 90D e consistência', tab: 'habitos', icon: <CheckSquare className="w-4 h-4" /> },
  { id: 'mod-estudo', category: 'módulo', title: 'Estudos & Pomodoro', subtitle: 'Matérias, simulados, flashcards e notas', tab: 'estudo', icon: <GraduationCap className="w-4 h-4" /> },
  { id: 'mod-leitura', category: 'módulo', title: 'Leitura Ativa & Citações', subtitle: 'Livros, páginas diárias, resumos e citações', tab: 'leitura', icon: <BookOpen className="w-4 h-4" /> },
  { id: 'mod-mental', category: 'módulo', title: 'Mente & Diário Estoico', subtitle: 'Humor, reflexões diárias e conexões sociais', tab: 'mental', icon: <Brain className="w-4 h-4" /> },
  { id: 'mod-antivicio', category: 'módulo', title: 'Anti-Vício & Gatilhos', subtitle: 'Streaks de abstinência, prevenção e SOS', tab: 'antivicio', icon: <ShieldAlert className="w-4 h-4" /> },
  { id: 'mod-calendario', category: 'módulo', title: 'Calendário & Histórico', subtitle: 'Evolução ao longo do tempo e navegação retroativa', tab: 'calendario', icon: <Calendar className="w-4 h-4" /> },
  { id: 'mod-config', category: 'módulo', title: 'Configurações & Backup', subtitle: 'Chaves de API, exportação e dados do sistema', tab: 'config', icon: <Settings className="w-4 h-4" /> },
];

export const GlobalSearch: React.FC<GlobalSearchProps> = ({
  isOpen,
  onClose,
  onNavigate,
  habits,
  subjects,
  books,
  quotes,
  workouts,
  vices
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Focus on input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Compute matching results across all entities
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      // Default: show modules as quick jump
      return STATIC_MODULES;
    }

    const list: SearchResultItem[] = [];

    // 1. Modules
    STATIC_MODULES.forEach(m => {
      if (m.title.toLowerCase().includes(q) || m.subtitle?.toLowerCase().includes(q)) {
        list.push(m);
      }
    });

    // 2. Habits
    habits.forEach(h => {
      if (h.title.toLowerCase().includes(q) || h.unit?.toLowerCase().includes(q)) {
        list.push({
          id: `h-${h.id}`,
          category: 'hábito',
          title: h.title,
          subtitle: `Meta: ${h.targetValue ? `${h.targetValue} ${h.unit || ''}` : 'Binário'} • Sequência: ${h.streak}d`,
          tab: 'habitos',
          icon: <CheckSquare className="w-4 h-4 text-neutral-300" />
        });
      }
    });

    // 3. Workouts (unique exercise names)
    const exerciseMap = new Map<string, { latestDate: string; maxLoad: number; count: number }>();
    workouts.forEach(w => {
      const name = w.exerciseName;
      const maxL = Math.max(...w.sets.map(s => s.load));
      const curr = exerciseMap.get(name) || { latestDate: w.date, maxLoad: 0, count: 0 };
      curr.count++;
      if (maxL > curr.maxLoad) curr.maxLoad = maxL;
      if (w.date > curr.latestDate) curr.latestDate = w.date;
      exerciseMap.set(name, curr);
    });

    exerciseMap.forEach((info, name) => {
      if (name.toLowerCase().includes(q)) {
        list.push({
          id: `ex-${name}`,
          category: 'treino',
          title: name,
          subtitle: `Recorde: ${info.maxLoad}kg • ${info.count} sessões registradas`,
          tab: 'treino',
          icon: <Dumbbell className="w-4 h-4 text-white" />
        });
      }
    });

    // 4. Study Subjects
    subjects.forEach(s => {
      if (s.name.toLowerCase().includes(q)) {
        list.push({
          id: `sub-${s.id}`,
          category: 'estudo',
          title: s.name,
          subtitle: `${s.totalMinutes} min estudados • ${s.points} pontos`,
          tab: 'estudo',
          icon: <GraduationCap className="w-4 h-4 text-neutral-300" />
        });
      }
    });

    // 5. Books
    books.forEach(b => {
      if (b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q)) {
        list.push({
          id: `book-${b.id}`,
          category: 'leitura',
          title: b.title,
          subtitle: `${b.author} • ${b.currentPage}/${b.totalPages} pág (${Math.round((b.currentPage / (b.totalPages || 1)) * 100)}%)`,
          tab: 'leitura',
          icon: <BookOpen className="w-4 h-4 text-neutral-300" />
        });
      }
    });

    // 6. Quotes
    quotes.forEach(quo => {
      if (quo.quote.toLowerCase().includes(q) || quo.bookTitle.toLowerCase().includes(q)) {
        list.push({
          id: `quo-${quo.id}`,
          category: 'leitura',
          title: `"${quo.quote.slice(0, 75)}${quo.quote.length > 75 ? '...' : ''}"`,
          subtitle: `Citação de ${quo.bookTitle}${quo.page ? ` (pág. ${quo.page})` : ''}`,
          tab: 'leitura',
          icon: <BookOpen className="w-4 h-4 text-neutral-400" />
        });
      }
    });

    // 7. Vices
    vices.forEach(v => {
      if (v.name.toLowerCase().includes(q) || v.letterToSelf?.toLowerCase().includes(q)) {
        list.push({
          id: `vice-${v.id}`,
          category: 'vício',
          title: v.name,
          subtitle: `Streak atual: ${v.streak}d • Recorde: ${v.longestStreak}d`,
          tab: 'antivicio',
          icon: <ShieldAlert className="w-4 h-4 text-red-400" />
        });
      }
    });

    return list.slice(0, 15);
  }, [query, habits, workouts, subjects, books, quotes, vices]);

  // Keep selected index within bounds
  useEffect(() => {
    setSelectedIndex(0);
  }, [results]);

  const handleSelect = (item: SearchResultItem) => {
    onNavigate(item.tab, item.date);
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[selectedIndex]) {
        handleSelect(results[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-start justify-center pt-16 sm:pt-24 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-neutral-950 border border-neutral-800 rounded-lg max-w-xl w-full shadow-2xl overflow-hidden flex flex-col font-mono"
        onClick={(e) => e.stopPropagation()}
      >
        {/* INPUT DE BUSCA */}
        <div className="flex items-center px-4 py-3.5 border-b border-neutral-900 gap-3">
          <Search className="w-4 h-4 text-neutral-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Buscar por módulos, exercícios, hábitos, livros, matérias..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full bg-transparent text-sm text-white focus:outline-none placeholder:text-neutral-600 font-mono"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="text-neutral-500 hover:text-white p-1 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <kbd className="hidden sm:inline bg-neutral-900 border border-neutral-800 text-[10px] px-1.5 py-0.5 rounded text-neutral-400">
            ESC
          </kbd>
        </div>

        {/* LISTA DE RESULTADOS */}
        <div 
          ref={listRef}
          className="max-h-[60vh] overflow-y-auto divide-y divide-neutral-900/60 p-1"
        >
          {results.length === 0 ? (
            <div className="p-8 text-center text-xs text-neutral-500">
              Nenhum resultado encontrado para "{query}".
            </div>
          ) : (
            results.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded cursor-pointer transition-colors ${
                    isSelected ? 'bg-neutral-900 text-white' : 'text-neutral-400 hover:bg-neutral-900/50 hover:text-neutral-200'
                  }`}
                >
                  <div className="flex items-center space-x-3 min-w-0 flex-1">
                    <div className={`p-1.5 rounded border ${
                      isSelected ? 'bg-black border-neutral-700 text-white' : 'bg-neutral-950 border-neutral-900 text-neutral-400'
                    }`}>
                      {item.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-xs truncate text-white">
                          {item.title}
                        </span>
                        <span className={`text-[9px] uppercase px-1.5 py-0.2 rounded border ${
                          item.category === 'módulo' ? 'bg-neutral-800 text-neutral-300 border-neutral-700' :
                          item.category === 'treino' ? 'bg-neutral-900 text-white border-neutral-800' :
                          item.category === 'vício' ? 'bg-red-950/40 text-red-400 border-red-900/50' :
                          'bg-neutral-950 text-neutral-400 border-neutral-900'
                        }`}>
                          {item.category}
                        </span>
                      </div>
                      {item.subtitle && (
                        <p className="text-[11px] text-neutral-500 truncate mt-0.5">
                          {item.subtitle}
                        </p>
                      )}
                    </div>
                  </div>

                  {isSelected && (
                    <div className="flex items-center space-x-1 text-neutral-400 pl-2 text-[10px]">
                      <span>Ir</span>
                      <CornerDownLeft className="w-3 h-3" />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* FOOTER DO MODAL */}
        <div className="border-t border-neutral-900 px-4 py-2 bg-neutral-950/90 text-[10px] text-neutral-500 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span><kbd className="bg-neutral-900 px-1 py-0.5 rounded border border-neutral-800 text-neutral-400">↑↓</kbd> navegar</span>
            <span><kbd className="bg-neutral-900 px-1 py-0.5 rounded border border-neutral-800 text-neutral-400">↵</kbd> selecionar</span>
            <span><kbd className="bg-neutral-900 px-1 py-0.5 rounded border border-neutral-800 text-neutral-400">esc</kbd> fechar</span>
          </div>
          <span className="text-neutral-600 font-mono">Global Life OS Search</span>
        </div>
      </div>
    </div>
  );
};
