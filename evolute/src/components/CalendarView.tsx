import React, { useState } from 'react';
import { 
  Calendar as CalendarIcon, ChevronLeft, ChevronRight, 
  CheckCircle2, Clock, Dumbbell, ArrowRight 
} from 'lucide-react';
import { Habit, StudyLog, WorkoutExercise } from '../types';
import { playChime } from '../utils/sound';
import { formatDisplayDate } from '../utils/storage';

interface CalendarViewProps {
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  todayStr: string;
  habits: Habit[];
  studyLogs: StudyLog[];
  workouts: WorkoutExercise[];
  onNavigateToTab: (tab: any) => void;
}

export const CalendarView: React.FC<CalendarViewProps> = ({
  selectedDate,
  setSelectedDate,
  todayStr,
  habits,
  studyLogs,
  workouts,
  onNavigateToTab
}) => {
  // Calendar month state
  const [currentYear, setCurrentYear] = useState<number>(() => Number(selectedDate.split('-')[0]) || 2026);
  const [currentMonth, setCurrentMonth] = useState<number>(() => Number(selectedDate.split('-')[1]) || 9); // 1-indexed

  const monthNames = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  const handlePrevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(y => y - 1);
    } else {
      setCurrentMonth(m => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(y => y + 1);
    } else {
      setCurrentMonth(m => m + 1);
    }
  };

  // Days in current month
  const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
  const firstDayIndex = new Date(currentYear, currentMonth - 1, 1).getDay(); // 0 = Sunday

  // Inspect data for selectedDate
  const inspectedStudies = studyLogs.filter(s => s.date === selectedDate);
  const inspectedWorkouts = workouts.filter(w => w.date === selectedDate);
  const totalStudyMin = inspectedStudies.reduce((acc, curr) => acc + curr.minutes, 0);
  const totalWorkoutVol = inspectedWorkouts.reduce((acc, curr) => acc + curr.totalVolume, 0);

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER */}
      <div className="border-b border-neutral-900 pb-4">
        <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
          <CalendarIcon className="w-4 h-4 text-white" />
          <span>Histórico & Linha do Tempo Mensal</span>
        </h2>
        <p className="text-xs text-neutral-500 font-mono mt-0.5">
          Navegue por qualquer dia do ano, confira o desempenho e edite retroativamente
        </p>
      </div>

      {/* MONTH SELECTOR */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex items-center justify-between">
          <button
            onClick={handlePrevMonth}
            className="p-1.5 border border-neutral-800 hover:border-white text-neutral-400 hover:text-white rounded"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <span className="font-mono text-base font-bold text-white tracking-wider">
            {monthNames[currentMonth - 1]} {currentYear}
          </span>

          <button
            onClick={handleNextMonth}
            className="p-1.5 border border-neutral-800 hover:border-white text-neutral-400 hover:text-white rounded"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7 text-center font-mono text-[11px] text-neutral-500 uppercase">
          <div>Dom</div>
          <div>Seg</div>
          <div>Ter</div>
          <div>Qua</div>
          <div>Qui</div>
          <div>Sex</div>
          <div>Sáb</div>
        </div>

        {/* Days grid */}
        <div className="grid grid-cols-7 gap-1.5 pt-1">
          {/* Empty padding before month starts */}
          {Array.from({ length: firstDayIndex }).map((_, i) => (
            <div key={`empty-${i}`} className="h-12 border border-transparent" />
          ))}

          {/* Actual days */}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const dayNum = i + 1;
            const dateStr = `${currentYear}-${currentMonth.toString().padStart(2, '0')}-${dayNum.toString().padStart(2, '0')}`;
            const isSelected = dateStr === selectedDate;
            const isToday = dateStr === todayStr;

            // Check if study or workout exists
            const hasStudy = studyLogs.some(s => s.date === dateStr);
            const hasWorkout = workouts.some(w => w.date === dateStr);

            return (
              <button
                key={dateStr}
                onClick={() => {
                  setSelectedDate(dateStr);
                  playChime();
                }}
                className={`h-14 border rounded p-1 flex flex-col justify-between text-left transition-all ${
                  isSelected 
                    ? 'bg-white text-black border-white font-bold scale-105 z-10' 
                    : isToday 
                    ? 'bg-neutral-900 border-neutral-600 text-white' 
                    : 'bg-black border-neutral-900 hover:border-neutral-700 text-neutral-400'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-mono text-xs">{dayNum}</span>
                  {isToday && (
                    <span className="text-[8px] font-mono px-1 rounded bg-white text-black uppercase">
                      Hoje
                    </span>
                  )}
                </div>

                <div className="flex space-x-1">
                  {hasStudy && (
                    <div className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-black' : 'bg-neutral-300'}`} title="Estudo registrado" />
                  )}
                  {hasWorkout && (
                    <div className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-black' : 'bg-neutral-400'}`} title="Treino registrado" />
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* INSPEÇÃO DO DIA SELECIONADO */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
          <span className="font-mono text-xs uppercase tracking-wider font-bold text-white">
            Resumo Registrado no Dia: {selectedDate}
          </span>
          <span className="text-[10px] font-mono text-neutral-500">
            {selectedDate === todayStr ? 'Dia Atual' : 'Registro Histórico'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs">
          {/* Estudo */}
          <div className="bg-black border border-neutral-900 p-4 rounded space-y-2">
            <div className="flex items-center justify-between text-neutral-400">
              <span className="flex items-center space-x-1.5 font-bold text-white">
                <Clock className="w-3.5 h-3.5" />
                <span>Estudo no Dia</span>
              </span>
              <span>{totalStudyMin} minutos</span>
            </div>
            {inspectedStudies.length === 0 ? (
              <p className="text-[11px] text-neutral-600 italic">Nenhuma sessão registrada nesta data.</p>
            ) : (
              inspectedStudies.map(s => (
                <div key={s.id} className="text-[11px] text-neutral-300">
                  • {s.subjectName} ({s.minutes}m) {s.notes && `- ${s.notes}`}
                </div>
              ))
            )}
            <button
              onClick={() => onNavigateToTab('estudo')}
              className="text-[10px] text-white hover:underline block pt-2"
            >
              Editar ou Adicionar Estudos neste Dia &rarr;
            </button>
          </div>

          {/* Treino */}
          <div className="bg-black border border-neutral-900 p-4 rounded space-y-2">
            <div className="flex items-center justify-between text-neutral-400">
              <span className="flex items-center space-x-1.5 font-bold text-white">
                <Dumbbell className="w-3.5 h-3.5" />
                <span>Treino no Dia</span>
              </span>
              <span>{totalWorkoutVol.toLocaleString('pt-BR')} kg</span>
            </div>
            {inspectedWorkouts.length === 0 ? (
              <p className="text-[11px] text-neutral-600 italic">Nenhum exercício registrado nesta data.</p>
            ) : (
              inspectedWorkouts.map(w => (
                <div key={w.id} className="text-[11px] text-neutral-300">
                  • {w.exerciseName} ({w.totalVolume}kg vol)
                </div>
              ))
            )}
            <button
              onClick={() => onNavigateToTab('treino')}
              className="text-[10px] text-white hover:underline block pt-2"
            >
              Editar ou Adicionar Treinos neste Dia &rarr;
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
