import React, { useState } from 'react';
import { 
  X, Droplet, Clock, Flame, ShieldAlert, 
  FileText, CheckCircle2, Dumbbell, Sparkles, Plus, ArrowRight 
} from 'lucide-react';
import { Subject, TabType } from '../types';
import { playChime } from '../utils/sound';

interface QuickActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  waterMl: number;
  onAddWater: (amount: number) => void;
  subjects: Subject[];
  onStartQuickPomodoro: (minutes: number, subjectId?: string) => void;
  onAppendNote: (note: string) => void;
  onNavigateTab: (tab: TabType) => void;
  onOpenSos: () => void;
}

export const QuickActionModal: React.FC<QuickActionModalProps> = ({
  isOpen,
  onClose,
  waterMl,
  onAddWater,
  subjects,
  onStartQuickPomodoro,
  onAppendNote,
  onNavigateTab,
  onOpenSos
}) => {
  const [quickNote, setQuickNote] = useState('');
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>(subjects[0]?.id || '');
  const [successToast, setSuccessToast] = useState<string>('');

  if (!isOpen) return null;

  const showToast = (msg: string) => {
    setSuccessToast(msg);
    setTimeout(() => setSuccessToast(''), 2500);
  };

  const handleDrink = (ml: number) => {
    onAddWater(ml);
    playChime();
    showToast(`+${ml}ml de água registrados! Total: ${waterMl + ml}ml`);
  };

  const handleStartFocus = (mins: number) => {
    onStartQuickPomodoro(mins, selectedSubjectId);
    playChime();
    showToast(`Foco de ${mins} min iniciado!`);
    onClose();
  };

  const handleSaveNote = () => {
    if (!quickNote.trim()) return;
    const timestamp = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const formatted = `\n• [${timestamp}] ${quickNote.trim()}`;
    onAppendNote(formatted);
    playChime();
    setQuickNote('');
    showToast('Nota salva no Caderno Infinito!');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-150">
      <div 
        className="w-full sm:max-w-lg bg-neutral-950 border border-neutral-800 rounded-t-2xl sm:rounded-xl shadow-2xl p-5 sm:p-6 space-y-5 animate-in slide-in-from-bottom-6 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
          <div className="flex items-center space-x-2">
            <div className="w-2.5 h-2.5 bg-white rounded-full animate-ping" />
            <span className="font-mono text-xs uppercase tracking-widest font-bold text-white">
              Ações Rápidas // 1 Toque
            </span>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Toast */}
        {successToast && (
          <div className="bg-white text-black font-mono text-xs py-1.5 px-3 rounded flex items-center justify-between animate-in fade-in">
            <span className="font-bold">{successToast}</span>
            <CheckCircle2 className="w-4 h-4" />
          </div>
        )}

        {/* 1. Hidratação Imediata */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-400">
            <span className="flex items-center space-x-1.5 text-white">
              <Droplet className="w-3.5 h-3.5 text-neutral-300" />
              <span>Consumo de Água</span>
            </span>
            <span>{waterMl} / 3000 ml</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleDrink(250)}
              className="border border-neutral-800 hover:border-white bg-black hover:bg-neutral-900 p-2.5 rounded font-mono text-xs text-white flex items-center justify-center space-x-2 transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>+250ml (Copo)</span>
            </button>
            <button
              onClick={() => handleDrink(500)}
              className="border border-neutral-800 hover:border-white bg-black hover:bg-neutral-900 p-2.5 rounded font-mono text-xs text-white flex items-center justify-center space-x-2 transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>+500ml (Garrafa)</span>
            </button>
          </div>
        </div>

        {/* 2. Iniciar Foco / Pomodoro Imediato */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-400">
            <span className="flex items-center space-x-1.5 text-white">
              <Clock className="w-3.5 h-3.5 text-neutral-300" />
              <span>Iniciar Ciclo de Foco</span>
            </span>
            {subjects.length > 0 && (
              <select
                value={selectedSubjectId}
                onChange={(e) => setSelectedSubjectId(e.target.value)}
                className="bg-black border border-neutral-800 text-neutral-300 text-[11px] rounded px-2 py-0.5 focus:outline-none cursor-pointer max-w-[150px]"
              >
                {subjects.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleStartFocus(25)}
              className="bg-white text-black hover:bg-neutral-200 p-2.5 rounded font-mono text-xs font-bold flex items-center justify-center space-x-2 transition-all cursor-pointer"
            >
              <Clock className="w-3.5 h-3.5" />
              <span>25 min (Foco)</span>
            </button>
            <button
              onClick={() => handleStartFocus(5)}
              className="border border-neutral-800 hover:border-white bg-black hover:bg-neutral-900 p-2.5 rounded font-mono text-xs text-neutral-300 hover:text-white flex items-center justify-center space-x-2 transition-all cursor-pointer"
              title="Regra dos 5 minutos para vencer a procrastinação"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>5 min (Inércia)</span>
            </button>
          </div>
        </div>

        {/* 3. Captura Rápida de Pensamento / Ideia */}
        <div className="space-y-2">
          <span className="flex items-center space-x-1.5 text-xs font-mono text-white">
            <FileText className="w-3.5 h-3.5 text-neutral-300" />
            <span>Nota Rápida (Caderno Infinito)</span>
          </span>
          <div className="flex gap-2">
            <input
              type="text"
              value={quickNote}
              onChange={(e) => setQuickNote(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSaveNote()}
              placeholder="Insight, fórmula ou pensamento..."
              className="flex-1 bg-black border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-white placeholder-neutral-600 focus:outline-none focus:border-neutral-500"
            />
            <button
              onClick={handleSaveNote}
              disabled={!quickNote.trim()}
              className="bg-neutral-900 border border-neutral-800 hover:border-white text-white px-3 py-2 rounded text-xs font-mono disabled:opacity-40 transition-colors"
            >
              Salvar
            </button>
          </div>
        </div>

        {/* 4. Atalhos de Emergência e Navegação */}
        <div className="pt-2 border-t border-neutral-900 grid grid-cols-2 gap-2">
          <button
            onClick={() => {
              onClose();
              onOpenSos();
            }}
            className="p-2 border border-red-900/60 bg-red-950/20 hover:bg-red-950/40 text-red-400 rounded font-mono text-xs flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Pânico S.O.S</span>
          </button>

          <button
            onClick={() => {
              onClose();
              onNavigateTab('treino');
            }}
            className="p-2 border border-neutral-800 hover:border-white bg-black text-neutral-300 hover:text-white rounded font-mono text-xs flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
          >
            <Dumbbell className="w-3.5 h-3.5" />
            <span>Ir para Treino</span>
          </button>
        </div>
      </div>
    </div>
  );
};
