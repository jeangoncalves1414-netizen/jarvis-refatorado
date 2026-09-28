import React from 'react';
import { ShieldAlert, ChevronLeft, ChevronRight, Calendar, Settings, Search } from 'lucide-react';
import { getLocalDateString, parseLocalDate, formatDisplayDate } from '../utils/storage';
import { TabType } from '../types';
import { isJarvisShell } from '../utils/shell';

interface NavbarProps {
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  todayStr: string;
  onOpenSos: () => void;
  onOpenSearch?: () => void;
  completedHabitsCount: number;
  totalHabitsCount: number;
  onNavigateTab: (tab: TabType) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  selectedDate,
  setSelectedDate,
  todayStr,
  onOpenSos,
  onOpenSearch,
  completedHabitsCount,
  totalHabitsCount,
  onNavigateTab,
}) => {
  const isToday = selectedDate === todayStr;
  const inJarvis = isJarvisShell();

  const changeDateByDays = (days: number) => {
    const current = parseLocalDate(selectedDate);
    current.setDate(current.getDate() + days);
    setSelectedDate(getLocalDateString(current));
  };

  return (
    <header className={`${inJarvis ? 'relative' : 'sticky top-0'} z-40 bg-black/90 backdrop-blur-md border-b border-neutral-900 px-3 md:px-6 py-2.5 flex-shrink-0`}>
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-2">

        {/* Brand + quick links */}
        <div className="flex items-center space-x-3 flex-shrink-0">
          <div className="w-3 h-3 bg-white border border-white flex-shrink-0" />
          <div className="hidden sm:block">
            <h1 className="font-mono text-sm font-bold tracking-widest uppercase leading-none text-white">
              LIFE // OS
            </h1>
            <span className="text-[9px] font-mono text-neutral-500 tracking-wider">
              EVOLUÇÃO PESSOAL
            </span>
          </div>

          {/* Desktop quick nav links */}
          <div className="hidden md:flex items-center space-x-1 ml-3 pl-3 border-l border-neutral-800">
            <button
              onClick={() => onNavigateTab('calendario')}
              className="p-1.5 rounded text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors cursor-pointer"
              title="Histórico / Calendário"
            >
              <Calendar className="w-3.5 h-3.5" />
            </button>
            {!inJarvis && (
              <button
                onClick={() => onNavigateTab('config')}
                className="p-1.5 rounded text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors cursor-pointer"
                title="Configurações"
              >
                <Settings className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Quick Global Search */}
        <button
          onClick={onOpenSearch}
          className="flex items-center space-x-2 bg-neutral-950 border border-neutral-800 hover:border-neutral-600 px-2.5 py-1.5 rounded text-neutral-400 hover:text-white transition-all cursor-pointer font-mono text-xs"
          title="Buscar no Life OS (Ctrl+K)"
        >
          <Search className="w-3.5 h-3.5 text-neutral-400" />
          <span className="hidden lg:inline text-neutral-500 text-[11px]">Buscar...</span>
          <kbd className="hidden sm:inline bg-neutral-900 border border-neutral-800 text-[9px] px-1 py-0.5 rounded text-neutral-400">
            Ctrl K
          </kbd>
        </button>

        {/* Retroactive Date Navigator */}
        <div className="flex items-center space-x-1 bg-neutral-950 border border-neutral-800 rounded px-1.5 py-1">
          <button
            onClick={() => changeDateByDays(-1)}
            title="Dia anterior"
            className="p-1 hover:text-white text-neutral-400 transition-colors cursor-pointer"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <div className="flex items-center space-x-1 px-0.5 font-mono text-xs">
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
              className="bg-transparent text-white font-mono text-xs focus:outline-none cursor-pointer w-[108px]"
            />
            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded hidden sm:inline ${isToday ? 'bg-white text-black' : 'bg-neutral-800 text-neutral-300'}`}>
              {formatDisplayDate(selectedDate)}
            </span>
          </div>

          <button
            onClick={() => changeDateByDays(1)}
            title="Próximo dia"
            className="p-1 hover:text-white text-neutral-400 transition-colors cursor-pointer"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>

          {!isToday && (
            <button
              onClick={() => setSelectedDate(todayStr)}
              className="text-[10px] font-mono border-l border-neutral-800 pl-2 ml-0.5 text-neutral-400 hover:text-white uppercase transition-colors whitespace-nowrap cursor-pointer"
            >
              Hoje
            </button>
          )}
        </div>

        {/* Right side: habits pill + SOS */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          <div className="hidden sm:flex items-center space-x-1.5 font-mono text-xs text-neutral-400 border border-neutral-800 px-2 py-1 rounded">
            <span className="text-neutral-500">Hábitos</span>
            <span className="text-white font-bold">{completedHabitsCount}/{totalHabitsCount}</span>
          </div>

          {/* Mobile: calendar + config icons */}
          <button
            onClick={() => onNavigateTab('calendario')}
            className="md:hidden p-1.5 rounded text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors cursor-pointer"
            title="Histórico"
          >
            <Calendar className="w-4 h-4" />
          </button>
          {!inJarvis && (
            <button
              onClick={() => onNavigateTab('config')}
              className="md:hidden p-1.5 rounded text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors cursor-pointer"
              title="Config"
            >
              <Settings className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={onOpenSos}
            className="flex items-center space-x-1.5 bg-neutral-950 border border-red-900/60 hover:border-red-500 hover:bg-red-950/40 text-red-400 px-2.5 py-1.5 rounded text-xs font-mono tracking-wider transition-all duration-200 cursor-pointer shadow-sm"
            title="Botão de Pânico Anti-Recaída"
          >
            <ShieldAlert className="w-3.5 h-3.5 animate-pulse" />
            <span className="font-bold hidden sm:inline">S.O.S</span>
          </button>
        </div>
      </div>
    </header>
  );
};
