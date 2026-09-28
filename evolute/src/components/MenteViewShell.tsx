import React, { useState } from 'react';
import { CheckSquare, BookMarked, Brain, ShieldAlert } from 'lucide-react';
import { TabType } from '../types';

interface MenteViewShellProps {
  defaultSubTab?: TabType;
  onSetActiveTab: (tab: TabType) => void;
  children: (subTab: TabType) => React.ReactNode;
}

const SUB_TABS: { id: TabType; label: string; icon: React.ReactNode }[] = [
  { id: 'habitos',   label: 'Hábitos',     icon: <CheckSquare className="w-4 h-4" /> },
  { id: 'leitura',  label: 'Leitura',     icon: <BookMarked  className="w-4 h-4" /> },
  { id: 'mental',   label: 'Mente',       icon: <Brain       className="w-4 h-4" /> },
  { id: 'antivicio',label: 'Anti-Vício',  icon: <ShieldAlert className="w-4 h-4" /> },
];

export const MenteViewShell: React.FC<MenteViewShellProps> = ({
  defaultSubTab = 'habitos',
  children,
}) => {
  const [subTab, setSubTab] = useState<TabType>(defaultSubTab);

  return (
    <div>
      {/* Sub-tab selector for Mente pillar */}
      <div className="sticky top-[57px] z-30 bg-black/95 border-b border-neutral-900 backdrop-blur-md px-4 md:px-8 py-2">
        <div className="max-w-6xl mx-auto flex items-center space-x-1 overflow-x-auto no-scrollbar">
          {SUB_TABS.map((tab) => {
            const isActive = subTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setSubTab(tab.id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded font-mono text-xs transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-white text-black font-bold'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-900'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Render the active sub-view */}
      <div className="px-4 md:px-8 pt-4 pb-32 max-w-6xl mx-auto">
        {children(subTab)}
      </div>
    </div>
  );
};
