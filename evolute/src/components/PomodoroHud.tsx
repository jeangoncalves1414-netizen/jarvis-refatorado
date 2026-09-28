import React from 'react';
import { Play, Pause, RotateCcw, BookOpen, Volume2, VolumeX, Maximize2 } from 'lucide-react';
import { PomodoroSessionState } from '../types';

interface PomodoroHudProps {
  pomodoro: PomodoroSessionState;
  onToggleTimer: () => void;
  onResetTimer: () => void;
  onNavigateToStudy: () => void;
}

export const PomodoroHud: React.FC<PomodoroHudProps> = ({
  pomodoro,
  onToggleTimer,
  onResetTimer,
  onNavigateToStudy,
}) => {
  // Only show HUD if timer is running or has been started/paused
  const isStarted = pomodoro.timeLeftSeconds < pomodoro.durationMinutes * 60 || pomodoro.isRunning;
  if (!isStarted) return null;

  const minutes = Math.floor(pomodoro.timeLeftSeconds / 60);
  const seconds = pomodoro.timeLeftSeconds % 60;
  const timeFormatted = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

  const totalSeconds = pomodoro.durationMinutes * 60;
  const progressPct = totalSeconds > 0 ? Math.round(((totalSeconds - pomodoro.timeLeftSeconds) / totalSeconds) * 100) : 0;

  return (
    <div className="fixed top-16 sm:top-auto sm:bottom-20 left-1/2 -translate-x-1/2 z-50 w-[92%] max-w-md pointer-events-auto transition-all animate-in fade-in slide-in-from-bottom-2 duration-200">
      <div className="bg-black/95 border border-neutral-700/80 rounded-full shadow-2xl backdrop-blur-xl px-4 py-2.5 flex items-center justify-between gap-3">
        {/* Progress pill & display time */}
        <div 
          onClick={onNavigateToStudy} 
          className="flex items-center space-x-3 cursor-pointer group"
          title="Clique para ir até a aba de Estudos"
        >
          <div className="relative w-8 h-8 rounded-full border border-neutral-700 flex items-center justify-center bg-neutral-950">
            <span className={`w-2 h-2 rounded-full ${pomodoro.isRunning ? 'bg-white animate-pulse' : 'bg-neutral-600'}`} />
            <svg className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none" viewBox="0 0 36 36">
              <path
                className="text-white"
                strokeDasharray={`${progressPct}, 100`}
                strokeWidth="2.5"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
          </div>

          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-mono text-sm font-bold text-white tracking-widest leading-none">
                {timeFormatted}
              </span>
              <span className="text-[9px] font-mono uppercase px-1 py-0.2 rounded bg-neutral-900 border border-neutral-800 text-neutral-400">
                {pomodoro.isRunning ? 'Foco' : 'Pausa'}
              </span>
            </div>
            <p className="text-[10px] font-mono text-neutral-400 truncate max-w-[140px] sm:max-w-[180px]">
              {pomodoro.subjectName || 'Sessão de Foco'}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-1.5">
          <button
            onClick={onToggleTimer}
            className="w-8 h-8 rounded-full bg-white text-black hover:bg-neutral-200 flex items-center justify-center transition-all cursor-pointer shadow-sm"
            title={pomodoro.isRunning ? 'Pausar Pomodoro' : 'Retomar Pomodoro'}
          >
            {pomodoro.isRunning ? (
              <Pause className="w-3.5 h-3.5 fill-current" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
            )}
          </button>

          <button
            onClick={onResetTimer}
            className="w-8 h-8 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-600 flex items-center justify-center transition-colors cursor-pointer"
            title="Resetar Pomodoro"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onNavigateToStudy}
            className="w-8 h-8 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-600 flex items-center justify-center transition-colors cursor-pointer"
            title="Expandir tela de foco"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
