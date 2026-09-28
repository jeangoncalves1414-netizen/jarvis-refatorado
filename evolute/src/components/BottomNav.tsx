import React from 'react';
import { 
  Flame, BookOpen, Dumbbell, Brain, Plus
} from 'lucide-react';
import { TabType } from '../types';
import { isJarvisShell } from '../utils/shell';

interface BottomNavProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  onOpenQuickAction: () => void;
}

// The 4 main pillars. "Mente" aggregates: hábitos, leitura, mental, antivicio
const MAIN_TABS: { id: TabType; label: string; icon: React.ReactNode }[] = [
  { id: 'inicio',  label: 'Início',  icon: <Flame   className="w-5 h-5" /> },
  { id: 'estudo',  label: 'Estudo',  icon: <BookOpen className="w-5 h-5" /> },
  { id: 'treino',  label: 'Treino',  icon: <Dumbbell className="w-5 h-5" /> },
  { id: 'mente',   label: 'Mente',   icon: <Brain    className="w-5 h-5" /> },
];

// Sub-tabs that belong to the "Mente" pillar
const MENTE_SUB_TABS: TabType[] = ['habitos', 'leitura', 'mental', 'antivicio'];

export const BottomNav: React.FC<BottomNavProps> = ({ activeTab, setActiveTab, onOpenQuickAction }) => {
  const inJarvis = isJarvisShell();
  // Determine which "pillar" is active (for highlighting)
  const activePillar: TabType | null =
    MENTE_SUB_TABS.includes(activeTab)
      ? 'mente'
      : MAIN_TABS.some((t) => t.id === activeTab)
      ? activeTab
      : null;

  return (
    <div className={`evolute-bottom-nav ${inJarvis ? 'relative mt-auto flex-shrink-0' : 'fixed bottom-0 left-0 right-0'} z-40 bg-black/95 border-t border-neutral-900 backdrop-blur-xl`}>
      <nav className="max-w-lg mx-auto flex items-center justify-between px-2 py-2 gap-1">
        {/* Left 2 tabs */}
        {MAIN_TABS.slice(0, 2).map((tab) => {
          const isActive = activePillar === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex flex-col items-center justify-center py-2 px-1 rounded-xl transition-all duration-150 ${
                isActive
                  ? 'text-white bg-neutral-900 border border-neutral-700'
                  : 'text-neutral-500 hover:text-neutral-300'
              }`}
            >
              <div className={isActive ? 'scale-105 transition-transform' : ''}>{tab.icon}</div>
              <span className={`text-[10px] font-mono mt-1 whitespace-nowrap ${isActive ? 'font-bold text-white' : ''}`}>
                {tab.label}
              </span>
            </button>
          );
        })}

        {/* Center Quick Action "+" Button */}
        <div className="flex-shrink-0 flex items-center justify-center px-1">
          <button
            onClick={onOpenQuickAction}
            className="w-14 h-14 rounded-full bg-white text-black shadow-2xl flex items-center justify-center transition-all duration-150 hover:scale-110 active:scale-95 hover:bg-neutral-100 cursor-pointer -mt-4 border-4 border-black"
            title="Ação Rápida"
          >
            <Plus className="w-7 h-7 stroke-[2.5]" />
          </button>
        </div>

        {/* Right 2 tabs */}
        {MAIN_TABS.slice(2, 4).map((tab) => {
          const isActive = activePillar === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id === 'mente' ? 'habitos' : tab.id)}
              className={`flex-1 flex flex-col items-center justify-center py-2 px-1 rounded-xl transition-all duration-150 ${
                isActive
                  ? 'text-white bg-neutral-900 border border-neutral-700'
                  : 'text-neutral-500 hover:text-neutral-300'
              }`}
            >
              <div className={isActive ? 'scale-105 transition-transform' : ''}>{tab.icon}</div>
              <span className={`text-[10px] font-mono mt-1 whitespace-nowrap ${isActive ? 'font-bold text-white' : ''}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};
