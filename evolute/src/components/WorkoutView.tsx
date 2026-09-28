import React, { useState, useMemo } from 'react';
import { 
  Dumbbell, Plus, Trash2, Droplet, Flame, 
  Calendar, Scale, TrendingUp, AlertCircle, CheckCircle2,
  BarChart2, Activity, Zap, Trophy, ChevronDown
} from 'lucide-react';
import { 
  ResponsiveContainer, BarChart, Bar, LineChart, Line, 
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid 
} from 'recharts';
import { 
  WorkoutExercise, WorkoutSplitDay, BodyWeightLog, 
  ExerciseSet, BodyPhoto 
} from '../types';
import { playChime } from '../utils/sound';
import { parseLocalDate, formatDisplayDate } from '../utils/storage';
import { EvolutionAlbumView } from './EvolutionAlbumView';

interface WorkoutViewProps {
  selectedDate: string;
  workouts: WorkoutExercise[];
  onAddWorkout: (workout: Omit<WorkoutExercise, 'id' | 'timestamp'>) => void;
  onDeleteWorkout: (id: string) => void;
  workoutSplit: WorkoutSplitDay[];
  onUpdateSplitDay: (dayOfWeek: number, split: Partial<WorkoutSplitDay>) => void;
  weightLogs: BodyWeightLog[];
  onAddWeightLog: (log: Omit<BodyWeightLog, 'id'>) => void;
  onDeleteWeightLog: (id: string) => void;
  waterMl: number;
  onAddWater: (ml: number) => void;
  bodyPhotos?: BodyPhoto[];
  onAddBodyPhoto?: (photo: Omit<BodyPhoto, 'id' | 'timestamp'>) => void;
  onDeleteBodyPhoto?: (id: string) => void;
}

export const WorkoutView: React.FC<WorkoutViewProps> = ({
  selectedDate,
  workouts,
  onAddWorkout,
  onDeleteWorkout,
  workoutSplit,
  onUpdateSplitDay,
  weightLogs,
  onAddWeightLog,
  onDeleteWeightLog,
  waterMl,
  onAddWater,
  bodyPhotos = [],
  onAddBodyPhoto,
  onDeleteBodyPhoto
}) => {
  const [workoutSubTab, setWorkoutSubTab] = useState<'treino' | 'divisao' | 'peso_saude' | 'graficos' | 'album'>('treino');

  // Exercise Form State
  const [exerciseName, setExerciseName] = useState('');
  const [muscleGroup, setMuscleGroup] = useState('Peito');
  const [notes, setNotes] = useState('');
  const [sets, setSets] = useState<ExerciseSet[]>([
    { reps: 10, load: 30 },
    { reps: 10, load: 30 },
    { reps: 8, load: 32 }
  ]);

  // Body weight and calories state
  const [currentWeight, setCurrentWeight] = useState('');
  const [currentCalories, setCurrentCalories] = useState('');
  const [healthNotes, setHealthNotes] = useState('');

  // Calculate day of week for selectedDate
  const dateObj = parseLocalDate(selectedDate);
  const dayOfWeek = dateObj.getDay(); // 0 = Sunday, 1 = Monday...
  const todayPlannedSplit = workoutSplit.find(s => s.dayOfWeek === dayOfWeek);

  // --- CHART DATA PREPARATION ---
  const sessionVolumeChartData = useMemo(() => {
    const mapByDate = new Map<string, { date: string; volume: number; count: number }>();
    workouts.forEach(w => {
      const existing = mapByDate.get(w.date) || { date: w.date, volume: 0, count: 0 };
      existing.volume += w.totalVolume;
      existing.count += 1;
      mapByDate.set(w.date, existing);
    });
    return Array.from(mapByDate.values())
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-14)
      .map(item => {
        const parts = item.date.split('-');
        return {
          ...item,
          name: parts.length === 3 ? `${parts[2]}/${parts[1]}` : item.date
        };
      });
  }, [workouts]);

  const muscleGroupVolumeChartData = useMemo(() => {
    const map = new Map<string, number>();
    workouts.forEach(w => {
      const group = w.muscleGroup || 'Outros';
      map.set(group, (map.get(group) || 0) + w.totalVolume);
    });
    return Array.from(map.entries())
      .map(([group, volume]) => ({ group, volume }))
      .sort((a, b) => b.volume - a.volume);
  }, [workouts]);

  const bodyWeightChartData = useMemo(() => {
    return [...weightLogs]
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-14)
      .map(w => {
        const parts = w.date.split('-');
        return {
          date: w.date,
          name: parts.length === 3 ? `${parts[2]}/${parts[1]}` : w.date,
          peso: w.weight,
          calorias: w.calories
        };
      });
  }, [weightLogs]);

  const totalAllTimeVolume = workouts.reduce((acc, curr) => acc + curr.totalVolume, 0);
  const maxSessionVolume = sessionVolumeChartData.reduce((max, curr) => Math.max(max, curr.volume), 0);
  const latestWeight = useMemo(() => {
    if (weightLogs.length === 0) return null;
    return [...weightLogs].sort((a, b) => b.date.localeCompare(a.date))[0].weight;
  }, [weightLogs]);

  // PR Tracker: unique exercise names
  const uniqueExerciseNames = useMemo(() => {
    const names = new Set<string>();
    workouts.forEach(w => names.add(w.exerciseName));
    return Array.from(names).sort();
  }, [workouts]);

  const [prSelectedExercise, setPrSelectedExercise] = useState<string>('');

  // PR Tracker: chart data for selected exercise (max load per session date)
  const prChartData = useMemo(() => {
    const target = prSelectedExercise || (uniqueExerciseNames[0] ?? '');
    if (!target) return [];
    const byDate = new Map<string, { date: string; maxLoad: number; maxVolume: number; sets: number }>();
    workouts
      .filter(w => w.exerciseName.toLowerCase() === target.toLowerCase())
      .forEach(w => {
        const maxLoad = Math.max(...w.sets.map(s => s.load));
        const existing = byDate.get(w.date);
        if (!existing || maxLoad > existing.maxLoad) {
          byDate.set(w.date, {
            date: w.date,
            maxLoad,
            maxVolume: w.totalVolume,
            sets: w.sets.length,
          });
        }
      });
    return Array.from(byDate.values())
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((item, idx, arr) => {
        const parts = item.date.split('-');
        const isPR = idx === arr.reduce((best, cur, i) =>
          cur.maxLoad > arr[best].maxLoad ? i : best, 0);
        return {
          ...item,
          name: parts.length === 3 ? `${parts[2]}/${parts[1]}` : item.date,
          isPR,
        };
      });
  }, [workouts, prSelectedExercise, uniqueExerciseNames]);

  const currentPRLoad = prChartData.length > 0
    ? Math.max(...prChartData.map(d => d.maxLoad))
    : 0;

  // Add/remove set in form
  const handleAddSet = () => {
    const lastSet = sets[sets.length - 1] || { reps: 10, load: 20 };
    setSets([...sets, { reps: lastSet.reps, load: lastSet.load }]);
  };

  const handleRemoveSet = (index: number) => {
    if (sets.length <= 1) return;
    setSets(sets.filter((_, i) => i !== index));
  };

  const handleUpdateSet = (index: number, field: 'reps' | 'load', value: number) => {
    const next = [...sets];
    next[index] = { ...next[index], [field]: value };
    setSets(next);
  };

  // Progressive Overload Suggestion based on previous workouts with same name (latest past session)
  const previousSameExercise = useMemo(() => {
    if (!exerciseName.trim()) return undefined;
    return workouts
      .filter(w => w.exerciseName.toLowerCase() === exerciseName.trim().toLowerCase() && w.date < selectedDate)
      .sort((a, b) => b.date.localeCompare(a.date))[0];
  }, [workouts, exerciseName, selectedDate]);

  let overloadSuggestion = '';
  if (previousSameExercise && previousSameExercise.sets.length > 0) {
    const lastSet = previousSameExercise.sets[0];
    overloadSuggestion = `No último treino: ${lastSet.load}kg x ${lastSet.reps} reps. Meta hoje: ${lastSet.load}kg para ${lastSet.reps + 1} reps ou ${lastSet.load + 2}kg para ${lastSet.reps} reps.`;
  }

  // Save Workout
  const handleSaveWorkout = () => {
    if (!exerciseName.trim()) return;
    const totalVolume = sets.reduce((acc, curr) => acc + (curr.reps * curr.load), 0);

    onAddWorkout({
      date: selectedDate,
      exerciseName: exerciseName.trim(),
      muscleGroup,
      sets,
      notes,
      totalVolume
    });

    setExerciseName('');
    setNotes('');
    playChime();
  };

  // Save Weight & Health Log
  const handleSaveHealthLog = () => {
    const w = Number(currentWeight);
    if (!w) return;
    onAddWeightLog({
      date: selectedDate,
      weight: w,
      calories: Number(currentCalories) || undefined,
      notes: healthNotes
    });
    setCurrentWeight('');
    setCurrentCalories('');
    setHealthNotes('');
    playChime();
  };

  // Workouts on the selected date
  const dayWorkouts = workouts.filter(w => w.date === selectedDate);
  const dayTotalVolume = dayWorkouts.reduce((acc, curr) => acc + curr.totalVolume, 0);

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER & SUB-TABS */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-4">
        <div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
            <Dumbbell className="w-4 h-4 text-white" />
            <span>Treino, Sobrecarga & Saúde Física</span>
          </h2>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Cálculo de volume (kg), divisão diária, peso corporal e hidratação
          </p>
        </div>

        <div className="flex items-center space-x-1 bg-neutral-950 p-1 rounded border border-neutral-800">
          {[
            { id: 'treino', label: 'Treino & Cargas' },
            { id: 'divisao', label: 'Divisão Semanal' },
            { id: 'peso_saude', label: 'Peso & Saúde' },
            { id: 'album', label: 'Álbum Shape' },
            { id: 'graficos', label: 'Gráficos & Sobrecarga' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setWorkoutSubTab(tab.id as any)}
              className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                workoutSubTab === tab.id 
                  ? 'bg-white text-black font-bold' 
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* AVISO DO TREINO DO DIA (DIVISÃO AUTOMÁTICA) */}
      <div className="bg-neutral-950 border border-neutral-800 rounded p-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Calendar className="w-5 h-5 text-white" />
          <div>
            <span className="text-[10px] font-mono text-neutral-500 uppercase block">
              Programação de {todayPlannedSplit?.dayName || 'Hoje'}
            </span>
            <span className="font-mono text-sm font-bold text-white">
              {todayPlannedSplit?.isRestDay 
                ? 'Dia de Descanso Ativo / Recuperação' 
                : `Foco: ${todayPlannedSplit?.muscleGroups}`}
            </span>
          </div>
        </div>

        <div className="text-right font-mono text-xs text-neutral-400">
          <span className="block text-[10px] text-neutral-500 uppercase">Volume Hoje</span>
          <span className="text-white font-bold text-base">{dayTotalVolume.toLocaleString('pt-BR')} kg</span>
        </div>
      </div>

      {/* 1. ABA: TREINO & SOBRECARGA PROGRESSIVA */}
      {workoutSubTab === 'treino' && (
        <div className="space-y-6">
          {/* Formulário de Registro de Exercício */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Registrar Exercício com Sobrecarga ({selectedDate})
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Exercício</label>
                <input
                  type="text"
                  placeholder="Ex: Supino Reto, Agachamento..."
                  value={exerciseName}
                  onChange={(e) => setExerciseName(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-white"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Grupo Muscular</label>
                <select
                  value={muscleGroup}
                  onChange={(e) => setMuscleGroup(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  <option value="Peito">Peito</option>
                  <option value="Costas">Costas</option>
                  <option value="Pernas">Pernas (Quadríceps/Posterior)</option>
                  <option value="Ombros">Ombros</option>
                  <option value="Bíceps">Bíceps</option>
                  <option value="Tríceps">Tríceps</option>
                  <option value="Abdômen">Abdômen / Core</option>
                  <option value="Cardio">Cardio / Condicionamento</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Observações de Execução</label>
                <input
                  type="text"
                  placeholder="Ex: Pausa de 2s na descida..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            </div>

            {/* Auto-sugestão de Sobrecarga Progressiva */}
            {overloadSuggestion && (
              <div className="bg-neutral-900/60 border border-neutral-800 p-3 rounded text-xs font-mono text-neutral-300 flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-white shrink-0" />
                <span>{overloadSuggestion}</span>
              </div>
            )}

            {/* Tabela de Séries (Reps x Carga) */}
            <div className="space-y-2 pt-2">
              <div className="flex items-center justify-between text-[10px] font-mono text-neutral-500 uppercase">
                <span>Séries Programadas ({sets.length} séries)</span>
                <button
                  onClick={handleAddSet}
                  className="text-white hover:underline flex items-center space-x-1"
                >
                  <Plus className="w-3 h-3" />
                  <span>Adicionar Série</span>
                </button>
              </div>

              <div className="space-y-2">
                {sets.map((set, idx) => (
                  <div key={idx} className="flex items-center space-x-3 bg-black p-2 rounded border border-neutral-800">
                    <span className="font-mono text-xs text-neutral-500 w-8">#{idx + 1}</span>
                    
                    <div className="flex-1 flex items-center space-x-2">
                      <span className="text-[10px] font-mono text-neutral-500">Carga:</span>
                      <input
                        type="number"
                        value={set.load}
                        onChange={(e) => handleUpdateSet(idx, 'load', Number(e.target.value))}
                        className="w-20 bg-neutral-950 border border-neutral-800 rounded px-2 py-1 text-xs text-white font-mono text-center"
                      />
                      <span className="text-xs font-mono text-neutral-400">kg</span>
                    </div>

                    <div className="flex-1 flex items-center space-x-2">
                      <span className="text-[10px] font-mono text-neutral-500">Reps:</span>
                      <input
                        type="number"
                        value={set.reps}
                        onChange={(e) => handleUpdateSet(idx, 'reps', Number(e.target.value))}
                        className="w-20 bg-neutral-950 border border-neutral-800 rounded px-2 py-1 text-xs text-white font-mono text-center"
                      />
                    </div>

                    <span className="font-mono text-xs text-neutral-400 w-24 text-right">
                      {set.reps * set.load} kg vol
                    </span>

                    {sets.length > 1 && (
                      <button
                        onClick={() => handleRemoveSet(idx)}
                        className="text-neutral-600 hover:text-red-400 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleSaveWorkout}
              className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-200 transition-colors"
            >
              + Salvar Exercício no Treino do Dia
            </button>
          </div>

          {/* Exercícios Realizados no Dia */}
          <div className="space-y-3">
            <h4 className="font-mono text-xs text-neutral-500 uppercase tracking-wider">
              Exercícios Registrados em {selectedDate}
            </h4>
            {dayWorkouts.length === 0 ? (
              <p className="text-xs font-mono text-neutral-600 italic bg-black border border-neutral-900 p-4 rounded">
                Nenhum exercício registrado nesta data. Registre seu treino acima.
              </p>
            ) : (
              dayWorkouts.map((w) => (
                <div key={w.id} className="bg-black border border-neutral-900 p-4 rounded flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-sm font-bold text-white">{w.exerciseName}</span>
                      <span className="bg-neutral-900 text-neutral-300 text-[10px] font-mono px-2 py-0.5 rounded">
                        {w.muscleGroup}
                      </span>
                    </div>

                    <div className="text-xs font-mono text-neutral-400 mt-1.5 flex flex-wrap gap-2">
                      {w.sets.map((s, i) => (
                        <span key={i} className="bg-neutral-950 border border-neutral-800 px-1.5 py-0.5 rounded text-[11px]">
                          Série {i + 1}: {s.load}kg × {s.reps}
                        </span>
                      ))}
                    </div>

                    {w.notes && (
                      <p className="text-[11px] font-mono text-neutral-500 mt-1 italic">
                        Obs: {w.notes}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-xs border border-neutral-800 px-2 py-1 rounded text-white">
                      {w.totalVolume} kg
                    </span>
                    <button
                      onClick={() => onDeleteWorkout(w.id)}
                      className="text-neutral-600 hover:text-red-400 p-1"
                      title="Excluir"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 2. ABA: DIVISÃO SEMANAL (SPLIT CUSTOMIZÁVEL) */}
      {workoutSubTab === 'divisao' && (
        <div className="space-y-4">
          <div className="bg-neutral-900/40 border border-neutral-800 p-3 rounded text-xs font-mono text-neutral-400">
            Defina sua rotina para cada dia da semana. O app detectará o dia da semana automaticamente e alertará seu treino do dia.
          </div>

          <div className="space-y-2.5">
            {workoutSplit.map((split) => (
              <div key={split.dayOfWeek} className="bg-black border border-neutral-800 p-3.5 rounded flex items-center justify-between gap-4">
                <div className="w-32">
                  <span className="font-mono text-xs font-bold text-white block">{split.dayName}</span>
                  <span className="text-[10px] font-mono text-neutral-500">
                    {split.isRestDay ? 'Descanso' : 'Treino de Força'}
                  </span>
                </div>

                <div className="flex-1">
                  <input
                    type="text"
                    value={split.muscleGroups}
                    onChange={(e) => onUpdateSplitDay(split.dayOfWeek, { muscleGroups: e.target.value })}
                    placeholder="Grupos musculares (ex: Peito e Tríceps)..."
                    disabled={split.isRestDay}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded px-3 py-1.5 text-xs text-white font-mono disabled:opacity-30"
                  />
                </div>

                <div>
                  <button
                    onClick={() => onUpdateSplitDay(split.dayOfWeek, { isRestDay: !split.isRestDay })}
                    className={`px-3 py-1 text-xs font-mono rounded border transition-colors ${
                      split.isRestDay 
                        ? 'bg-white text-black font-bold border-white' 
                        : 'border-neutral-800 text-neutral-400 hover:border-white'
                    }`}
                  >
                    {split.isRestDay ? 'Descanso' : 'Ativo'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. ABA: PESO, CALORIAS & HIDRATAÇÃO */}
      {workoutSubTab === 'peso_saude' && (
        <div className="space-y-6">
          {/* Hidratação Rápida */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-wider font-bold text-white flex items-center space-x-2">
                <Droplet className="w-4 h-4 text-white" />
                <span>Consumo de Água ({selectedDate})</span>
              </span>
              <span className="font-mono text-xl font-bold text-white">
                {waterMl} <span className="text-xs font-normal text-neutral-500">/ 3000 ml</span>
              </span>
            </div>

            <div className="w-full bg-neutral-900 h-2 rounded-full overflow-hidden">
              <div 
                className="bg-white h-full transition-all duration-300"
                style={{ width: `${Math.min(100, (waterMl / 3000) * 100)}%` }}
              />
            </div>

            <div className="flex space-x-2 pt-1">
              <button
                onClick={() => onAddWater(250)}
                className="flex-1 border border-neutral-800 hover:border-white py-2 rounded text-xs font-mono uppercase"
              >
                +250ml
              </button>
              <button
                onClick={() => onAddWater(500)}
                className="flex-1 border border-neutral-800 hover:border-white py-2 rounded text-xs font-mono uppercase"
              >
                +500ml
              </button>
              <button
                onClick={() => onAddWater(-waterMl)}
                className="border border-neutral-900 hover:border-red-500 text-neutral-600 hover:text-red-400 px-3 py-2 rounded text-xs font-mono"
              >
                Reset
              </button>
            </div>
          </div>

          {/* Registro de Peso & Nutrição */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Registrar Peso Corporal & Nutrição ({selectedDate})
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Peso Corporal (kg)</label>
                <input
                  type="number"
                  step="0.1"
                  placeholder="Ex: 78.4"
                  value={currentWeight}
                  onChange={(e) => setCurrentWeight(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Calorias Estimadas (kcal)</label>
                <input
                  type="number"
                  placeholder="Ex: 2400"
                  value={currentCalories}
                  onChange={(e) => setCurrentCalories(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Observações de Saúde</label>
                <input
                  type="text"
                  placeholder="Ex: Jejum de 16h, pós-treino com 40g proteína..."
                  value={healthNotes}
                  onChange={(e) => setHealthNotes(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            </div>

            <button
              onClick={handleSaveHealthLog}
              className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-200 transition-colors"
            >
              Salvar Registro de Saúde
            </button>
          </div>

          {/* Histórico de Peso */}
          <div className="space-y-2">
            <h4 className="font-mono text-xs text-neutral-500 uppercase tracking-wider">
              Histórico de Pesagens
            </h4>
            {weightLogs.map((wl) => (
              <div key={wl.id} className="bg-black border border-neutral-900 p-3 rounded flex items-center justify-between font-mono text-xs">
                <div>
                  <span className="font-bold text-white">{wl.weight} kg</span>
                  <span className="text-neutral-500 ml-2">({wl.date})</span>
                  {wl.calories && <span className="text-neutral-400 ml-2">• {wl.calories} kcal</span>}
                  {wl.notes && <p className="text-[11px] text-neutral-500 mt-0.5">{wl.notes}</p>}
                </div>
                <button
                  onClick={() => onDeleteWeightLog(wl.id)}
                  className="text-neutral-600 hover:text-red-400 p-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. ABA: GRÁFICOS DE SOBRECARGA & PROGRESSÃO */}
      {workoutSubTab === 'graficos' && (
        <div className="space-y-6">
          {/* Métricas Resumo */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono">
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Tonelagem Acumulada</span>
              <span className="text-xl font-bold text-white">{totalAllTimeVolume.toLocaleString('pt-BR')} kg</span>
              <span className="text-[10px] text-neutral-500 block">volume total levantado</span>
            </div>
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Pico de Volume (Sessão)</span>
              <span className="text-xl font-bold text-white">{maxSessionVolume.toLocaleString('pt-BR')} kg</span>
              <span className="text-[10px] text-neutral-500 block">recorde em 1 treino</span>
            </div>
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Peso Corporal Atual</span>
              <span className="text-xl font-bold text-white">{latestWeight ? `${latestWeight} kg` : '—'}</span>
              <span className="text-[10px] text-neutral-500 block">{weightLogs.length} pesagens</span>
            </div>
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Exercícios Feitos</span>
              <span className="text-xl font-bold text-white">{workouts.length}</span>
              <span className="text-[10px] text-neutral-500 block">registros no total</span>
            </div>
          </div>

          {/* PR TRACKER: Evolução de Carga por Exercício */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-3">
              <div className="flex items-center space-x-2">
                <Trophy className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  PR Tracker — Evolução de Carga por Exercício
                </h3>
              </div>
              <div className="flex items-center space-x-2">
                {currentPRLoad > 0 && (
                  <span className="flex items-center space-x-1 bg-white text-black px-2.5 py-1 rounded font-mono text-[10px] font-bold uppercase">
                    <Trophy className="w-3 h-3" />
                    <span>PR: {currentPRLoad} kg</span>
                  </span>
                )}
                <div className="relative">
                  <select
                    value={prSelectedExercise || (uniqueExerciseNames[0] ?? '')}
                    onChange={e => setPrSelectedExercise(e.target.value)}
                    className="appearance-none bg-black border border-neutral-800 rounded px-3 py-1.5 pr-8 text-xs text-white font-mono focus:outline-none focus:border-neutral-600"
                  >
                    {uniqueExerciseNames.length === 0 ? (
                      <option value="">Nenhum exercício</option>
                    ) : (
                      uniqueExerciseNames.map(name => (
                        <option key={name} value={name}>{name}</option>
                      ))
                    )}
                  </select>
                  <ChevronDown className="w-3 h-3 text-neutral-500 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              </div>
            </div>

            {prChartData.length > 0 ? (
              <>
                <div className="w-full h-56 pt-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={prChartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                      <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
                      <YAxis stroke="#666" fontSize={11} tickLine={false} unit="kg" />
                      <Tooltip
                        content={({ active, payload }: any) => {
                          if (active && payload && payload.length) {
                            const d = payload[0].payload;
                            return (
                              <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl space-y-1">
                                <p className="text-white font-bold">{d.date}</p>
                                <p className="text-neutral-300">Carga Máx: <strong className="text-white">{d.maxLoad} kg</strong></p>
                                <p className="text-neutral-400">Volume: {d.maxVolume.toLocaleString('pt-BR')} kg</p>
                                <p className="text-neutral-400">{d.sets} séries</p>
                                {d.isPR && (
                                  <p className="text-white font-bold flex items-center space-x-1 border-t border-neutral-800 pt-1">
                                    <span>🏆 Personal Record!</span>
                                  </p>
                                )}
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="maxLoad"
                        name="Carga Máx (kg)"
                        stroke="#ffffff"
                        strokeWidth={2}
                        dot={(props: any) => {
                          const { cx, cy, payload } = props;
                          if (payload.isPR) {
                            return (
                              <g key={`pr-dot-${cx}-${cy}`}>
                                <circle cx={cx} cy={cy} r={7} fill="#fff" />
                                <text x={cx} y={cy - 12} textAnchor="middle" fontSize={10} fill="#fff" fontWeight="bold">PR</text>
                              </g>
                            );
                          }
                          return <circle key={`dot-${cx}-${cy}`} cx={cx} cy={cy} r={4} fill="#fff" stroke="#fff" />;
                        }}
                        activeDot={{ r: 6, fill: '#fff' }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                {/* Mini-tabela de histórico */}
                <div className="space-y-1 border-t border-neutral-900 pt-3">
                  <p className="text-[10px] font-mono text-neutral-500 uppercase mb-2">Histórico de Sessões</p>
                  {[...prChartData].reverse().slice(0, 6).map((d, i) => (
                    <div key={i} className="flex items-center justify-between font-mono text-xs py-1 border-b border-neutral-900/50">
                      <span className="text-neutral-400">{d.date}</span>
                      <div className="flex items-center space-x-3">
                        <span className="text-neutral-300">{d.sets} séries</span>
                        <span className="text-white font-bold">{d.maxLoad} kg</span>
                        {d.isPR && <span className="text-[10px] bg-white text-black px-1.5 py-0.5 rounded font-bold">🏆 PR</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-xs font-mono text-neutral-500 italic py-6 text-center">
                Registre exercícios na aba "Treino & Cargas" para rastrear seu PR.
              </p>
            )}
          </div>

          {/* Gráfico 1: Sobrecarga Progressiva por Sessão */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  Sobrecarga Progressiva (Volume Total em kg por Sessão)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">
                Série × Repetições × Carga
              </span>
            </div>

            {sessionVolumeChartData.length > 0 ? (
              <div className="w-full h-64 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sessionVolumeChartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorWorkout" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ffffff" stopOpacity={0.4}/>
                        <stop offset="95%" stopColor="#ffffff" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                    <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
                    <YAxis stroke="#666" fontSize={11} tickLine={false} unit="kg" />
                    <Tooltip 
                      content={({ active, payload }: any) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl space-y-1">
                              <p className="text-white font-bold">{data.date}</p>
                              <p className="text-neutral-300">Volume Total: <strong className="text-white">{data.volume.toLocaleString('pt-BR')} kg</strong></p>
                              <p className="text-neutral-400">Exercícios: {data.count}</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="volume" 
                      name="Volume (kg)" 
                      stroke="#ffffff" 
                      strokeWidth={2}
                      fillOpacity={1} 
                      fill="url(#colorWorkout)" 
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs font-mono text-neutral-500 italic py-6 text-center">
                Cadastre exercícios para visualizar a curva de sobrecarga progressiva.
              </p>
            )}
          </div>

          {/* Gráfico 2: Volume por Grupo Muscular */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
              <div className="flex items-center space-x-2">
                <BarChart2 className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  Distribuição de Volume por Grupo Muscular (kg)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">
                Equilíbrio anatômico
              </span>
            </div>

            {muscleGroupVolumeChartData.length > 0 ? (
              <div className="w-full h-64 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={muscleGroupVolumeChartData} margin={{ top: 10, right: 10, left: -10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                    <XAxis dataKey="group" stroke="#666" fontSize={11} tickLine={false} />
                    <YAxis stroke="#666" fontSize={11} tickLine={false} />
                    <Tooltip 
                      content={({ active, payload }: any) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl space-y-1">
                              <p className="text-white font-bold">{data.group}</p>
                              <p className="text-neutral-300">Volume Total: <strong className="text-white">{data.volume.toLocaleString('pt-BR')} kg</strong></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="volume" name="Volume (kg)" fill="#ffffff" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs font-mono text-neutral-500 italic py-6 text-center">
                Nenhum treino cadastrado ainda.
              </p>
            )}
          </div>

          {/* Gráfico 3: Evolução de Peso Corporal (kg) */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
              <div className="flex items-center space-x-2">
                <Scale className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  Evolução do Peso Corporal (kg)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">
                Tendência ponderal
              </span>
            </div>

            {bodyWeightChartData.length > 0 ? (
              <div className="w-full h-56 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={bodyWeightChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                    <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
                    <YAxis stroke="#666" fontSize={11} tickLine={false} domain={['dataMin - 2', 'dataMax + 2']} unit="kg" />
                    <Tooltip 
                      content={({ active, payload }: any) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl">
                              <p className="text-white font-bold">{data.date}</p>
                              <p className="text-neutral-300">Peso: <strong className="text-white">{data.peso} kg</strong></p>
                              {data.calorias && <p className="text-neutral-400">Calorias: {data.calorias} kcal</p>}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="peso" 
                      name="Peso (kg)" 
                      stroke="#ffffff" 
                      strokeWidth={2}
                      dot={{ r: 4, fill: '#fff' }}
                      activeDot={{ r: 6, fill: '#fff' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs font-mono text-neutral-500 italic py-6 text-center">
                Registre seu peso na aba "Peso & Saúde" para traçar a evolução na balança.
              </p>
            )}
          </div>
        </div>
      )}

      {/* 5. ABA: ÁLBUM DE EVOLUÇÃO FÍSICA & SHAPE */}
      {workoutSubTab === 'album' && (
        <EvolutionAlbumView
          photos={bodyPhotos}
          onAddPhoto={onAddBodyPhoto || (() => {})}
          onDeletePhoto={onDeleteBodyPhoto || (() => {})}
          selectedDate={selectedDate}
          defaultWeight={latestWeight}
        />
      )}
    </div>
  );
};
