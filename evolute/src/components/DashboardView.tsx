import React, { useState, useEffect, useMemo } from 'react';
import { 
  Flame, Sparkles, Play, Pause, RotateCcw, Droplet, 
  Dumbbell, BookOpen, Brain, CheckCircle2, Circle, 
  ArrowRight, ShieldCheck, Quote, ChevronRight, BarChart2,
  TrendingUp, Activity, Calendar, ShieldAlert, Target, Award, Crown
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  Tooltip, CartesianGrid 
} from 'recharts';
import { 
  Habit, HabitLog, Subject, StudyLog, ExamSimulation, 
  WorkoutExercise, BookQuote, DayVictory, ApiSettings, 
  EvolutionHistoryItem, MentalLog, ViceLog, BodyWeightLog 
} from '../types';
import { askAiCoach } from '../utils/ai';
import { playChime } from '../utils/sound';
import { formatDisplayDate, parseLocalDate, getLocalDateString } from '../utils/storage';

interface DashboardViewProps {
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  todayStr: string;
  habits: Habit[];
  habitLogs: HabitLog;
  onToggleHabit: (habitId: string) => void;
  onTogglePriority?: (habitId: string) => void;
  waterMl: number;
  onAddWater: (amount: number) => void;
  workouts: WorkoutExercise[];
  studyLogs: StudyLog[];
  simulations?: ExamSimulation[];
  victories?: DayVictory[];
  onUpdateVictories?: (victories: DayVictory[]) => void;
  quotes: BookQuote[];
  apiSettings: ApiSettings;
  allDatesHeatmap: { date: string; ratio: number; count: number; total: number }[];
  evolutionHistory: EvolutionHistoryItem[];
  mentalLog?: MentalLog;
  viceLogs?: ViceLog[];
  weightLogs?: BodyWeightLog[];
  onNavigateTab: (tab: any) => void;
}

// Day of week formatter in Portuguese
function getDayOfWeekName(dateStr: string): string {
  try {
    const d = parseLocalDate(dateStr);
    const names = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
    return names[d.getDay()] || '';
  } catch {
    return '';
  }
}

// Custom monochrome HUD tooltip with rich multidimensional day data
const CustomMonochromeTooltip = ({ active, payload, label, selectedDate, todayStr }: any) => {
  if (active && payload && payload.length) {
    const data: EvolutionHistoryItem = payload[0]?.payload;
    if (!data) return null;

    const dateStr = data.date;
    const dayOfWeek = getDayOfWeekName(dateStr);
    const isToday = dateStr === todayStr;
    const isSelected = dateStr === selectedDate;

    return (
      <div className="bg-black/95 border border-neutral-600 p-4 rounded shadow-2xl font-mono text-xs space-y-3 z-50 min-w-[290px] max-w-[340px] backdrop-blur select-none">
        {/* Header */}
        <div className="border-b border-neutral-800 pb-2">
          <div className="flex items-center justify-between">
            <span className="text-white font-bold text-sm tracking-wide">
              {dayOfWeek ? `${dayOfWeek}, ` : ''}{formatDisplayDate(dateStr, todayStr)}
            </span>
            <div className="flex items-center space-x-1">
              {isToday && (
                <span className="bg-white text-black font-bold text-[9px] px-1.5 py-0.5 rounded uppercase">
                  Hoje
                </span>
              )}
              {isSelected && (
                <span className="bg-neutral-800 text-neutral-300 text-[9px] px-1.5 py-0.5 rounded uppercase">
                  Ativo
                </span>
              )}
            </div>
          </div>
          <span className="text-[10px] text-neutral-500 block">{dateStr}</span>

          {/* Performance Index */}
          <div className="mt-2 pt-1.5 border-t border-neutral-900 flex items-center justify-between">
            <span className="text-[11px] text-neutral-400 font-bold flex items-center space-x-1">
              <Sparkles className="w-3 h-3 text-white" />
              <span>Score Life OS:</span>
            </span>
            <span className="text-white font-bold text-xs">{data.performanceScore}%</span>
          </div>
          <div className="w-full bg-neutral-900 h-1 rounded-full overflow-hidden mt-1">
            <div 
              className="bg-white h-full transition-all duration-300"
              style={{ width: `${data.performanceScore}%` }}
            />
          </div>
        </div>

        {/* Detailed Breakdown Sections */}
        <div className="space-y-2 text-[11px]">
          {/* Estudo */}
          <div className="bg-neutral-950 p-2 rounded border border-neutral-900">
            <div className="flex items-center justify-between text-neutral-300">
              <span className="flex items-center space-x-1.5 font-bold text-white">
                <BookOpen className="w-3 h-3" />
                <span>Estudo no Dia:</span>
              </span>
              <span className="font-bold text-white">{data.dailyStudy} min</span>
            </div>
            {data.subjectsStudied && data.subjectsStudied.length > 0 ? (
              <p className="text-[10px] text-neutral-400 mt-1 truncate">
                • {data.subjectsStudied.join(', ')}
              </p>
            ) : (
              <p className="text-[10px] text-neutral-600 mt-0.5 italic">Nenhuma sessão registrada</p>
            )}
            {data.simulationsCount > 0 && (
              <p className="text-[10px] text-neutral-400 mt-0.5">
                • Simulados: <strong className="text-white">{data.simulationsAccuracy}% de acerto</strong> ({data.simulationsCount} feitos)
              </p>
            )}
          </div>

          {/* Treino */}
          <div className="bg-neutral-950 p-2 rounded border border-neutral-900">
            <div className="flex items-center justify-between text-neutral-300">
              <span className="flex items-center space-x-1.5 font-bold text-white">
                <Dumbbell className="w-3 h-3" />
                <span>Corpo & Treino:</span>
              </span>
              <span className="font-bold text-white">{data.dailyWorkout.toLocaleString('pt-BR')} kg vol</span>
            </div>
            {data.exercisesDone && data.exercisesDone.length > 0 ? (
              <p className="text-[10px] text-neutral-400 mt-1 truncate">
                • {data.exercisesDone.join(', ')}
              </p>
            ) : (
              <p className="text-[10px] text-neutral-600 mt-0.5 italic">Nenhum exercício registrado</p>
            )}
            {data.weightKg && (
              <p className="text-[10px] text-neutral-400 mt-0.5">
                • Peso corporal: <strong className="text-white">{data.weightKg} kg</strong>
              </p>
            )}
          </div>

          {/* Hábitos & Água */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-neutral-950 p-2 rounded border border-neutral-900">
              <span className="text-[10px] text-neutral-500 uppercase block mb-0.5">Hábitos</span>
              <span className="text-white font-bold">{data.habitsDone} de {data.habitsTotal}</span>
              <span className="text-[10px] text-neutral-400 block font-normal">({data.habitsRate}%)</span>
            </div>
            <div className="bg-neutral-950 p-2 rounded border border-neutral-900">
              <span className="text-[10px] text-neutral-500 uppercase block mb-0.5">Água</span>
              <span className="text-white font-bold">{data.waterMl} ml</span>
              <span className="text-[10px] text-neutral-400 block font-normal">({data.waterPct}% da meta)</span>
            </div>
          </div>

          {/* Saúde Mental & Anti-Vício */}
          <div className="bg-neutral-950 p-2 rounded border border-neutral-900 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-neutral-400 flex items-center space-x-1">
                <Brain className="w-3 h-3 text-white" />
                <span>Humor:</span>
              </span>
              <span className="text-white font-bold">
                {data.moodScore ? `${data.moodLabel} (${data.moodScore}/5)` : 'Não avaliado'}
              </span>
            </div>
            {data.moodTags && data.moodTags.length > 0 && (
              <p className="text-[10px] text-neutral-500 truncate">
                Tags: {data.moodTags.join(', ')}
              </p>
            )}
            <div className="flex items-center justify-between text-[10px] text-neutral-400 pt-1 border-t border-neutral-900">
              <span>Anti-Vício:</span>
              <span className={data.vicesClean ? 'text-white font-bold' : 'text-red-400 font-bold'}>
                {data.vicesClean ? '✓ 100% Sóbrio' : `⚠️ Recaída`}
              </span>
            </div>
          </div>

          {/* Missões Inegociáveis */}
          {data.victoriesTotal !== undefined && data.victoriesTotal > 0 && (
            <div className="flex items-center justify-between text-[10px] text-neutral-400 px-1">
              <span>Missões Inegociáveis:</span>
              <span className="text-white font-bold">{data.victoriesDone} de {data.victoriesTotal} concluídas</span>
            </div>
          )}
        </div>

        {/* Action prompt */}
        <div className="border-t border-neutral-800 pt-2 text-[10px] text-neutral-300 text-center font-mono font-bold bg-neutral-950/80 py-1 rounded">
          {isSelected ? '• Dia selecionado no aplicativo' : '⚡ Clique para abrir os registros deste dia'}
        </div>
      </div>
    );
  }
  return null;
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  selectedDate,
  setSelectedDate,
  todayStr,
  habits,
  habitLogs,
  onToggleHabit,
  onTogglePriority,
  waterMl,
  onAddWater,
  workouts,
  studyLogs,
  simulations = [],
  victories = [],
  onUpdateVictories,
  quotes,
  apiSettings,
  allDatesHeatmap,
  evolutionHistory,
  mentalLog,
  viceLogs = [],
  weightLogs = [],
  onNavigateTab
}) => {
  // Chart state
  const [chartDays, setChartDays] = useState<7 | 14 | 30>(7);
  const [chartMetric, setChartMetric] = useState<'geral' | 'estudo' | 'treino' | 'habitos' | 'agua' | 'mental'>('estudo');
  const [navToast, setNavToast] = useState<string>('');

  // Timelapse animation state
  const [isPlayingTimelapse, setIsPlayingTimelapse] = useState(false);
  const [timelapseIndex, setTimelapseIndex] = useState(evolutionHistory.length - 1);

  // Stoic AI Coaching state
  const [aiAnalysis, setAiAnalysis] = useState<string>('');
  const [loadingAi, setLoadingAi] = useState(false);

  // Random quote of the day
  const dailyQuote = quotes.length > 0 ? quotes[0] : {
    quote: 'Você tem poder sobre a sua mente, não sobre os acontecimentos externos. Perceba isso e você encontrará força.',
    bookTitle: 'Marco Aurélio - Meditações'
  };

  // Keep timelapse index synchronized
  useEffect(() => {
    setTimelapseIndex(evolutionHistory.length - 1);
  }, [evolutionHistory.length]);

  // Timelapse timer effect
  useEffect(() => {
    let interval: any = null;
    if (isPlayingTimelapse) {
      interval = setInterval(() => {
        setTimelapseIndex((prev) => {
          if (prev >= evolutionHistory.length - 1) {
            setIsPlayingTimelapse(false);
            return prev;
          }
          return prev + 1;
        });
      }, 500);
    }
    return () => clearInterval(interval);
  }, [isPlayingTimelapse, evolutionHistory.length]);

  const startTimelapse = () => {
    setTimelapseIndex(0);
    setIsPlayingTimelapse(true);
  };

  // Day's stats calculation
  const currentWorkouts = workouts.filter(w => w.date === selectedDate);
  const currentStudies = studyLogs.filter(s => s.date === selectedDate);
  const totalVolumeToday = currentWorkouts.reduce((acc, curr) => acc + curr.totalVolume, 0);
  const totalStudyMinutesToday = currentStudies.reduce((acc, curr) => acc + curr.minutes, 0);

  // Active habits on the selected date
  const activeHabitsToday = habits.filter(h => !h.createdAt || h.createdAt <= selectedDate);
  const completedHabitsCount = activeHabitsToday.filter(h => habitLogs[h.id]?.completed).length;

  // Hábitos Inegociáveis (Prioritários - marcados com coroa)
  const priorityHabits = useMemo(() => {
    return activeHabitsToday.filter(h => h.isPriority);
  }, [activeHabitsToday]);
  const completedPriorityHabitsCount = priorityHabits.filter(h => habitLogs[h.id]?.completed).length;

  const handleVictoryTextChange = (id: string, text: string) => {
    if (!onUpdateVictories) return;
    const next = victories.map(v => v.id === id ? { ...v, text } : v);
    onUpdateVictories(next);
  };

  const handleVictoryToggle = (id: string) => {
    if (!onUpdateVictories) return;
    playChime();
    const next = victories.map(v => v.id === id ? { ...v, completed: !v.completed } : v);
    onUpdateVictories(next);
  };

  const handleRequestAudit = async () => {
    setLoadingAi(true);
    const summary = `
      Data avaliada: ${selectedDate}
      Água consumida: ${waterMl}ml
      Hábitos cumpridos: ${completedHabitsCount}/${activeHabitsToday.length}
      Treino: ${currentWorkouts.length} exercícios registrados, volume total de ${totalVolumeToday}kg
      Estudo: ${totalStudyMinutesToday} minutos registrados
      Saúde Mental: Humor ${mentalLog?.moodScore || 3}/5, Tags: ${mentalLog?.moodTags?.join(', ') || 'nenhuma'}
      Hábitos inegociáveis (coroa): ${completedPriorityHabitsCount}/${priorityHabits.length} cumpridos
    `;

    const prompt = `Analise objetivamente minha rotina e disciplina no dia com base nos dados:\n${summary}\nForneça uma avaliação estóica curta: 1 ponto forte, 1 ponto crítico para melhorar e 1 conselho direto para o próximo dia.`;

    const result = await askAiCoach(prompt, apiSettings);
    setAiAnalysis(result.text);
    setLoadingAi(false);
  };

  // Process chart data according to selected timeframe
  const chartData = useMemo(() => {
    const sliced = evolutionHistory.slice(-chartDays);
    return sliced.map(item => {
      const parts = item.date.split('-');
      const shortDate = item.displayDate || (parts.length === 3 ? `${parts[2]}/${parts[1]}` : item.date);

      // Select active value based on chosen metric
      let metricValue = item.dailyStudy;
      if (chartMetric === 'geral') metricValue = item.performanceScore;
      else if (chartMetric === 'treino') metricValue = item.dailyWorkout;
      else if (chartMetric === 'habitos') metricValue = item.habitsRate;
      else if (chartMetric === 'agua') metricValue = item.waterMl;
      else if (chartMetric === 'mental') metricValue = item.moodScore || 3;

      return {
        ...item,
        name: shortDate,
        displayValue: metricValue
      };
    });
  }, [evolutionHistory, chartDays, chartMetric]);

  // Aggregate stats in current chart timeframe
  const totalStudyInPeriod = chartData.reduce((acc, c) => acc + c.dailyStudy, 0);
  const totalWorkoutInPeriod = chartData.reduce((acc, c) => acc + c.dailyWorkout, 0);
  const avgHabitsRateInPeriod = Math.round(
    chartData.reduce((acc, c) => acc + c.habitsRate, 0) / (chartData.length || 1)
  );
  const avgPerformanceInPeriod = Math.round(
    chartData.reduce((acc, c) => acc + c.performanceScore, 0) / (chartData.length || 1)
  );

  // Peak in period for active metric
  const peakItem = chartData.reduce((prev, curr) => (curr.displayValue > prev.displayValue ? curr : prev), chartData[0] || {} as any);

  // Click handler on chart points
  const handleChartPointClick = (clickedDate: string) => {
    if (!clickedDate) return;
    setSelectedDate(clickedDate);
    playChime();
    setNavToast(`Data ativa alterada para ${formatDisplayDate(clickedDate, todayStr)} (${clickedDate})`);
    setTimeout(() => setNavToast(''), 3500);
  };

  // Evolution display point for timelapse
  const currentEvolutionPoint = evolutionHistory[timelapseIndex] || evolutionHistory[evolutionHistory.length - 1] || {
    date: selectedDate,
    studyMins: totalStudyMinutesToday,
    workoutVol: totalVolumeToday,
    habitsDone: completedHabitsCount,
    performanceScore: 80
  };

  // Weekly Comparison: This Week (days 0..6) vs Last Week (days 7..13)
  const weeklyComparison = useMemo(() => {
    const base = new Date();
    const getDateStr = (offsetDays: number) => {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - offsetDays, 12, 0, 0);
      return getLocalDateString(d);
    };

    const thisWeekDates = new Set<string>();
    for (let i = 0; i < 7; i++) thisWeekDates.add(getDateStr(i));

    const lastWeekDates = new Set<string>();
    for (let i = 7; i < 14; i++) lastWeekDates.add(getDateStr(i));

    let thisWeekStudyMins = 0;
    let thisWeekWorkoutVol = 0;
    let thisWeekHabitsDone = 0;
    let thisWeekHabitsTotal = 0;
    let thisWeekScoreSum = 0;
    let thisWeekCount = 0;

    let lastWeekStudyMins = 0;
    let lastWeekWorkoutVol = 0;
    let lastWeekHabitsDone = 0;
    let lastWeekHabitsTotal = 0;
    let lastWeekScoreSum = 0;
    let lastWeekCount = 0;

    evolutionHistory.forEach(item => {
      if (thisWeekDates.has(item.date)) {
        thisWeekStudyMins += item.studyMins;
        thisWeekWorkoutVol += item.workoutVol;
        thisWeekHabitsDone += item.habitsDone;
        thisWeekHabitsTotal += item.habitsTotal;
        thisWeekScoreSum += item.performanceScore;
        thisWeekCount++;
      } else if (lastWeekDates.has(item.date)) {
        lastWeekStudyMins += item.studyMins;
        lastWeekWorkoutVol += item.workoutVol;
        lastWeekHabitsDone += item.habitsDone;
        lastWeekHabitsTotal += item.habitsTotal;
        lastWeekScoreSum += item.performanceScore;
        lastWeekCount++;
      }
    });

    const thisWeekHabitRate = thisWeekHabitsTotal > 0 ? Math.round((thisWeekHabitsDone / thisWeekHabitsTotal) * 100) : 0;
    const lastWeekHabitRate = lastWeekHabitsTotal > 0 ? Math.round((lastWeekHabitsDone / lastWeekHabitsTotal) * 100) : 0;
    const habitDelta = thisWeekHabitRate - lastWeekHabitRate;

    const studyDelta = thisWeekStudyMins - lastWeekStudyMins;
    const studyDeltaPct = lastWeekStudyMins > 0 ? Math.round((studyDelta / lastWeekStudyMins) * 100) : 0;

    const workoutDelta = thisWeekWorkoutVol - lastWeekWorkoutVol;
    const workoutDeltaPct = lastWeekWorkoutVol > 0 ? Math.round((workoutDelta / lastWeekWorkoutVol) * 100) : 0;

    const thisWeekAvgScore = thisWeekCount > 0 ? Math.round(thisWeekScoreSum / thisWeekCount) : 0;
    const lastWeekAvgScore = lastWeekCount > 0 ? Math.round(lastWeekScoreSum / lastWeekCount) : 0;
    const scoreDelta = thisWeekAvgScore - lastWeekAvgScore;

    return {
      thisWeek: {
        studyMins: thisWeekStudyMins,
        workoutVol: thisWeekWorkoutVol,
        habitRate: thisWeekHabitRate,
        avgScore: thisWeekAvgScore
      },
      lastWeek: {
        studyMins: lastWeekStudyMins,
        workoutVol: lastWeekWorkoutVol,
        habitRate: lastWeekHabitRate,
        avgScore: lastWeekAvgScore
      },
      deltas: {
        habitRate: habitDelta,
        studyMins: studyDelta,
        studyPct: studyDeltaPct,
        workoutVol: workoutDelta,
        workoutPct: workoutDeltaPct,
        avgScore: scoreDelta
      }
    };
  }, [evolutionHistory]);

  return (
    <div className="space-y-6 pb-20">
      {/* 1. HERO STATUS CARDS */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {/* Hábitos */}
        <div 
          onClick={() => onNavigateTab('habitos')}
          className="bg-neutral-950 border border-neutral-900 hover:border-neutral-700 p-4 rounded cursor-pointer transition-all"
        >
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-[11px] font-mono uppercase tracking-wider">Hábitos</span>
            <CheckCircle2 className="w-3.5 h-3.5" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-mono font-bold text-white">{completedHabitsCount}</span>
            <span className="text-xs font-mono text-neutral-500">/ {activeHabitsToday.length}</span>
          </div>
          <div className="mt-2 w-full bg-neutral-900 h-1 rounded-full overflow-hidden">
            <div 
              className="bg-white h-full transition-all duration-300"
              style={{ width: `${activeHabitsToday.length > 0 ? (completedHabitsCount / activeHabitsToday.length) * 100 : 0}%` }}
            />
          </div>
        </div>

        {/* Foco & Estudo */}
        <div 
          onClick={() => onNavigateTab('estudo')}
          className="bg-neutral-950 border border-neutral-900 hover:border-neutral-700 p-4 rounded cursor-pointer transition-all"
        >
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-[11px] font-mono uppercase tracking-wider">Estudo</span>
            <BookOpen className="w-3.5 h-3.5" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-mono font-bold text-white">{totalStudyMinutesToday}</span>
            <span className="text-xs font-mono text-neutral-500">minutos</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-neutral-500">
            <span>{currentStudies.length} sessões</span>
            <span className="text-white hover:underline">Abrir &rarr;</span>
          </div>
        </div>

        {/* Treino & Carga */}
        <div 
          onClick={() => onNavigateTab('treino')}
          className="bg-neutral-950 border border-neutral-900 hover:border-neutral-700 p-4 rounded cursor-pointer transition-all"
        >
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-[11px] font-mono uppercase tracking-wider">Corpo & Carga</span>
            <Dumbbell className="w-3.5 h-3.5" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-mono font-bold text-white">{totalVolumeToday.toLocaleString('pt-BR')}</span>
            <span className="text-xs font-mono text-neutral-500">kg vol</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-neutral-500">
            <span>{currentWorkouts.length} exercícios</span>
            <span className="text-white hover:underline">Registrar &rarr;</span>
          </div>
        </div>

        {/* Água & Saúde */}
        <div className="bg-neutral-950 border border-neutral-900 p-4 rounded flex flex-col justify-between">
          <div className="flex items-center justify-between text-neutral-500 mb-1">
            <span className="text-[11px] font-mono uppercase tracking-wider">Hidratação</span>
            <Droplet className="w-3.5 h-3.5 text-neutral-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-mono font-bold text-white">{waterMl}</span>
            <span className="text-xs font-mono text-neutral-500">/ 3000 ml</span>
          </div>
          <div className="mt-2 flex space-x-1.5">
            <button 
              onClick={() => onAddWater(250)}
              className="flex-1 bg-neutral-900 hover:bg-white hover:text-black py-1 text-[10px] font-mono uppercase rounded transition-colors cursor-pointer"
            >
              +250ml
            </button>
            <button 
              onClick={() => onAddWater(500)}
              className="flex-1 bg-neutral-900 hover:bg-white hover:text-black py-1 text-[10px] font-mono uppercase rounded transition-colors cursor-pointer"
            >
              +500ml
            </button>
          </div>
        </div>

        {/* Saúde Mental & Estoicismo (Card Integrado) */}
        <div 
          onClick={() => onNavigateTab('mental')}
          className="col-span-2 md:col-span-1 bg-neutral-950 border border-neutral-900 hover:border-neutral-700 p-4 rounded cursor-pointer transition-all flex flex-col justify-between"
        >
          <div className="flex items-center justify-between text-neutral-500 mb-1">
            <span className="text-[11px] font-mono uppercase tracking-wider">Saúde Mental</span>
            <Brain className="w-3.5 h-3.5 text-white" />
          </div>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-2xl font-mono font-bold text-white">
              {mentalLog?.moodScore || 3}
            </span>
            <span className="text-xs font-mono text-neutral-500">
              / 5 ({['Crítico', 'Baixo', 'Neutro', 'Focado', 'Pleno'][(mentalLog?.moodScore || 3) - 1]})
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between text-[10px] font-mono">
            <span className={mentalLog?.journalText ? 'text-neutral-400' : 'text-neutral-500 italic'}>
              {mentalLog?.journalText ? '✓ Diário Salvo' : 'Pendente'}
            </span>
            <span className="text-white hover:underline">Ver &rarr;</span>
          </div>
        </div>
      </div>

      {/* COMPARATIVO SEMANAL (ESTA SEMANA VS. SEMANA ANTERIOR) */}
      <section className="bg-neutral-950 border border-neutral-900 rounded p-4 sm:p-5 space-y-3 font-mono">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-neutral-900 pb-2.5">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-white" />
            <h3 className="text-xs uppercase font-bold tracking-wider text-white">
              Comparativo Semanal: Últimos 7 Dias vs. Semana Anterior
            </h3>
          </div>
          <span className="text-[10px] text-neutral-500">
            Deltas calculados automaticamente
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-1">
          {/* Hábitos */}
          <div className="bg-black border border-neutral-900 rounded p-3 space-y-1">
            <div className="flex items-center justify-between text-neutral-500 text-[10px] uppercase">
              <span>Hábitos (Média)</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold border ${
                weeklyComparison.deltas.habitRate >= 0 
                  ? 'bg-neutral-900 text-white border-neutral-700' 
                  : 'bg-neutral-900 text-neutral-400 border-neutral-800'
              }`}>
                {weeklyComparison.deltas.habitRate >= 0 ? `+${weeklyComparison.deltas.habitRate}%` : `${weeklyComparison.deltas.habitRate}%`}
              </span>
            </div>
            <div className="text-lg font-bold text-white">
              {weeklyComparison.thisWeek.habitRate}%
            </div>
            <p className="text-[10px] text-neutral-500">
              Ant: {weeklyComparison.lastWeek.habitRate}%
            </p>
          </div>

          {/* Volume de Treino */}
          <div className="bg-black border border-neutral-900 rounded p-3 space-y-1">
            <div className="flex items-center justify-between text-neutral-500 text-[10px] uppercase">
              <span>Volume Treino</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold border ${
                weeklyComparison.deltas.workoutVol >= 0 
                  ? 'bg-neutral-900 text-white border-neutral-700' 
                  : 'bg-neutral-900 text-neutral-400 border-neutral-800'
              }`}>
                {weeklyComparison.deltas.workoutPct >= 0 ? `+${weeklyComparison.deltas.workoutPct}%` : `${weeklyComparison.deltas.workoutPct}%`}
              </span>
            </div>
            <div className="text-lg font-bold text-white">
              {weeklyComparison.thisWeek.workoutVol.toLocaleString('pt-BR')} <span className="text-xs text-neutral-500 font-normal">kg</span>
            </div>
            <p className="text-[10px] text-neutral-500">
              Ant: {weeklyComparison.lastWeek.workoutVol.toLocaleString('pt-BR')} kg
            </p>
          </div>

          {/* Estudo & Foco */}
          <div className="bg-black border border-neutral-900 rounded p-3 space-y-1">
            <div className="flex items-center justify-between text-neutral-500 text-[10px] uppercase">
              <span>Foco & Estudo</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold border ${
                weeklyComparison.deltas.studyMins >= 0 
                  ? 'bg-neutral-900 text-white border-neutral-700' 
                  : 'bg-neutral-900 text-neutral-400 border-neutral-800'
              }`}>
                {weeklyComparison.deltas.studyMins >= 0 ? `+${weeklyComparison.deltas.studyMins}m` : `${weeklyComparison.deltas.studyMins}m`}
              </span>
            </div>
            <div className="text-lg font-bold text-white">
              {Math.floor(weeklyComparison.thisWeek.studyMins / 60)}h {weeklyComparison.thisWeek.studyMins % 60}m
            </div>
            <p className="text-[10px] text-neutral-500">
              Ant: {Math.floor(weeklyComparison.lastWeek.studyMins / 60)}h {weeklyComparison.lastWeek.studyMins % 60}m
            </p>
          </div>

          {/* Score Geral */}
          <div className="bg-black border border-neutral-900 rounded p-3 space-y-1">
            <div className="flex items-center justify-between text-neutral-500 text-[10px] uppercase">
              <span>Score Life OS</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold border ${
                weeklyComparison.deltas.avgScore >= 0 
                  ? 'bg-neutral-900 text-white border-neutral-700' 
                  : 'bg-neutral-900 text-neutral-400 border-neutral-800'
              }`}>
                {weeklyComparison.deltas.avgScore >= 0 ? `+${weeklyComparison.deltas.avgScore} pts` : `${weeklyComparison.deltas.avgScore} pts`}
              </span>
            </div>
            <div className="text-lg font-bold text-white">
              {weeklyComparison.thisWeek.avgScore}%
            </div>
            <p className="text-[10px] text-neutral-500">
              Ant: {weeklyComparison.lastWeek.avgScore}%
            </p>
          </div>
        </div>
      </section>

      {/* 2. HÁBITOS INEGOCIÁVEIS DO DIA (COM COROA) */}
      <section className="bg-neutral-950 border border-neutral-900 rounded p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Crown className="w-4 h-4 text-amber-400 fill-amber-400" />
            <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-white">
              Hábitos Inegociáveis do Dia ({formatDisplayDate(selectedDate)})
            </h2>
          </div>
          <span className="text-[11px] font-mono text-neutral-500">
            {completedPriorityHabitsCount} / {priorityHabits.length} cumpridos
          </span>
        </div>

        {priorityHabits.length === 0 ? (
          <div className="p-4 border border-dashed border-neutral-800/80 rounded text-center text-xs font-mono text-neutral-500 space-y-1.5 bg-black/40">
            <div className="flex items-center justify-center space-x-2 text-neutral-400">
              <Crown className="w-4 h-4 text-amber-400/60" />
              <span className="font-bold text-neutral-300">Nenhum hábito inegociável definido</span>
            </div>
            <p className="text-[11px] text-neutral-500">
              Seus hábitos normais podem se tornar inegociáveis! Acesse a aba{' '}
              <button 
                type="button"
                onClick={() => onNavigateTab('habitos')}
                className="text-amber-400 hover:text-amber-300 underline font-semibold cursor-pointer"
              >
                Hábitos
              </button>{' '}
              e clique no ícone de coroa 👑 para destacar as suas prioridades máximas.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {priorityHabits.map((habit) => {
              const log = habitLogs[habit.id] || { completed: false, currentValue: 0 };
              const isDone = log.completed;

              return (
                <div 
                  key={habit.id}
                  className={`flex items-center justify-between p-3.5 rounded border transition-all ${
                    isDone 
                      ? 'bg-black border-neutral-800 text-neutral-400' 
                      : 'bg-black/80 border-amber-500/20 hover:border-amber-500/40 text-white shadow-[0_0_15px_rgba(245,158,11,0.03)]'
                  }`}
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <button 
                      onClick={() => {
                        onToggleHabit(habit.id);
                        playChime();
                      }}
                      className="text-neutral-400 hover:text-white shrink-0 cursor-pointer"
                    >
                      {isDone ? (
                        <CheckCircle2 className="w-5 h-5 text-white" />
                      ) : (
                        <Circle className="w-5 h-5 text-amber-400" />
                      )}
                    </button>
                    
                    <div className="flex items-center space-x-2.5 min-w-0">
                      <Crown className={`w-4 h-4 shrink-0 text-amber-400 ${isDone ? 'opacity-40' : 'fill-amber-400 drop-shadow-[0_0_6px_rgba(251,191,36,0.5)]'}`} />
                      <span className={`font-mono text-xs font-bold truncate ${
                        isDone ? 'line-through text-neutral-500' : 'text-neutral-100'
                      }`}>
                        {habit.title}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 shrink-0 text-[11px] font-mono text-neutral-500">
                    <span className="flex items-center space-x-1 text-amber-400 font-bold">
                      <Flame className="w-3.5 h-3.5 text-amber-400" />
                      <span>{habit.streak}d</span>
                    </span>
                    {onTogglePriority && (
                      <button
                        type="button"
                        onClick={() => onTogglePriority(habit.id)}
                        title="Remover prioridade inegociável"
                        className="text-neutral-600 hover:text-neutral-300 p-1 text-xs cursor-pointer"
                      >
                        ×
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 3. GRÁFICOS DE EVOLUÇÃO E DESEMPENHO (PADRONIZADOS NO ESTILO DO GRÁFICO DE ESTUDO) */}
      <section className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-3">
          <div className="flex items-center space-x-2">
            <BarChart2 className="w-4 h-4 text-white" />
            <div>
              <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-white">
                Gráficos de Evolução e Desempenho
              </h2>
              <p className="text-[11px] text-neutral-500 font-mono mt-0.5">
                Área monocromática com marcadores clicáveis e raio-x detalhado de cada data
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Metric Selector Tabs */}
            <div className="flex flex-wrap items-center bg-black border border-neutral-800 rounded p-0.5 text-xs font-mono">
              {[
                { id: 'estudo', label: 'Estudo (min)' },
                { id: 'treino', label: 'Carga (kg)' },
                { id: 'habitos', label: 'Hábitos (%)' },
                { id: 'agua', label: 'Água (ml)' },
                { id: 'mental', label: 'Humor (1-5)' },
                { id: 'geral', label: 'Geral Life OS (%)' },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setChartMetric(tab.id as any)}
                  className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                    chartMetric === tab.id
                      ? 'bg-white text-black font-bold'
                      : 'text-neutral-400 hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Timeframe Selector */}
            <div className="flex items-center bg-black border border-neutral-800 rounded p-0.5 text-xs font-mono">
              {[
                { days: 7, label: '7D' },
                { days: 14, label: '14D' },
                { days: 30, label: '30D' },
              ].map(t => (
                <button
                  key={t.days}
                  onClick={() => setChartDays(t.days as any)}
                  className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                    chartDays === t.days
                      ? 'bg-neutral-800 text-white font-bold'
                      : 'text-neutral-500 hover:text-white'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Navigation Feedback Toast Banner */}
        {navToast && (
          <div className="bg-neutral-900 border border-white text-white px-4 py-2.5 rounded font-mono text-xs flex items-center justify-between animate-fadeIn">
            <span className="font-bold flex items-center space-x-1.5">
              <Calendar className="w-3.5 h-3.5" />
              <span>{navToast}</span>
            </span>
            <span className="text-[10px] text-neutral-400">Cards e dados atualizados</span>
          </div>
        )}

        {/* Resumo Rápido e Estatísticas do Período */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-black border border-neutral-900 p-3 rounded font-mono text-xs">
          <div>
            <span className="text-[10px] text-neutral-500 uppercase block">Estudo no Período</span>
            <span className="text-sm font-bold text-white">{totalStudyInPeriod} min</span>
            <span className="text-[10px] text-neutral-500 block">~{Math.round(totalStudyInPeriod / chartDays)} min/dia</span>
          </div>
          <div>
            <span className="text-[10px] text-neutral-500 uppercase block">Volume de Carga</span>
            <span className="text-sm font-bold text-white">{totalWorkoutInPeriod.toLocaleString('pt-BR')} kg</span>
            <span className="text-[10px] text-neutral-500 block">tonelagem total</span>
          </div>
          <div>
            <span className="text-[10px] text-neutral-500 uppercase block">Adesão a Hábitos</span>
            <span className="text-sm font-bold text-white">{avgHabitsRateInPeriod}%</span>
            <span className="text-[10px] text-neutral-500 block">média no período</span>
          </div>
          <div>
            <span className="text-[10px] text-neutral-500 uppercase block">Pico no Período</span>
            <span className="text-sm font-bold text-white truncate block">
              {peakItem?.name ? `${peakItem.name}: ${peakItem.displayValue}` : '-'}
            </span>
            <span className="text-[10px] text-neutral-400 block truncate">Score médio: {avgPerformanceInPeriod}%</span>
          </div>
        </div>

        {/* UNIFIED MONOCHROME AREA CHART (SAME SLEEK AESTHETIC FOR ALL METRICS) */}
        <div className="w-full h-72 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart 
              data={chartData} 
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              onClick={(e: any) => {
                if (e && e.activePayload && e.activePayload.length) {
                  const d = e.activePayload[0].payload.date;
                  if (d) handleChartPointClick(d);
                }
              }}
              style={{ cursor: 'pointer' }}
            >
              <defs>
                <linearGradient id="colorMonoChartArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ffffff" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#ffffff" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
              <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
              <YAxis 
                stroke="#666" 
                fontSize={11} 
                tickLine={false} 
                unit={
                  chartMetric === 'estudo' ? 'm' : 
                  chartMetric === 'treino' ? 'kg' : 
                  chartMetric === 'habitos' || chartMetric === 'geral' ? '%' : 
                  chartMetric === 'agua' ? 'ml' : ''
                }
                domain={
                  chartMetric === 'habitos' || chartMetric === 'geral' ? [0, 100] :
                  chartMetric === 'mental' ? [1, 5] :
                  ['auto', 'auto']
                }
              />
              <Tooltip 
                content={
                  <CustomMonochromeTooltip 
                    selectedDate={selectedDate} 
                    todayStr={todayStr} 
                  />
                } 
              />
              <Area 
                type="monotone" 
                dataKey="displayValue" 
                name={
                  chartMetric === 'estudo' ? 'Tempo de Estudo (min)' :
                  chartMetric === 'treino' ? 'Carga de Treino (kg)' :
                  chartMetric === 'habitos' ? 'Taxa de Hábitos (%)' :
                  chartMetric === 'agua' ? 'Consumo de Água (ml)' :
                  chartMetric === 'mental' ? 'Nota de Humor (1-5)' :
                  'Performance Life OS (%)'
                }
                stroke="#ffffff" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorMonoChartArea)" 
                dot={{ r: 3.5, fill: '#ffffff', strokeWidth: 0 }}
                activeDot={{ r: 6.5, fill: '#ffffff', stroke: '#000', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[10px] font-mono text-neutral-500 text-center">
          Passe o mouse nos picos para ver o raio-x multidimensional • Clique em qualquer ponto para abrir os registros do dia
        </p>
      </section>

      {/* 4. MAPA DE CALOR / HEATMAP DE HÁBITOS (ÚLTIMOS 35 DIAS) */}
      <section className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-white">
            Consistência nos Últimos 35 Dias (Heatmap Monocromático)
          </h2>
          <div className="flex items-center space-x-1.5 text-[10px] font-mono text-neutral-500">
            <span>0%</span>
            <div className="w-2.5 h-2.5 bg-black border border-neutral-900 rounded-xs" />
            <div className="w-2.5 h-2.5 bg-neutral-800 rounded-xs" />
            <div className="w-2.5 h-2.5 bg-neutral-500 rounded-xs" />
            <div className="w-2.5 h-2.5 bg-white rounded-xs" />
            <span>100%</span>
          </div>
        </div>

        <div className="grid grid-cols-7 gap-1.5 pt-1">
          {allDatesHeatmap.slice(-35).map((item) => {
            const isSelected = item.date === selectedDate;
            let bgClass = 'bg-black border-neutral-900 text-neutral-600';
            if (item.ratio >= 0.99) bgClass = 'bg-white border-white text-black font-bold';
            else if (item.ratio >= 0.7) bgClass = 'bg-neutral-300 border-neutral-300 text-black';
            else if (item.ratio >= 0.4) bgClass = 'bg-neutral-600 border-neutral-600 text-white';
            else if (item.ratio > 0) bgClass = 'bg-neutral-800 border-neutral-800 text-neutral-300';

            const parts = item.date.split('-');
            const displayDay = parts[2] || item.date;

            return (
              <button
                key={item.date}
                onClick={() => {
                  setSelectedDate(item.date);
                  playChime();
                  setNavToast(`Data ativa alterada para ${formatDisplayDate(item.date, todayStr)} (${item.date})`);
                  setTimeout(() => setNavToast(''), 3500);
                }}
                className={`h-9 rounded border font-mono text-xs flex items-center justify-center transition-all cursor-pointer ${bgClass} ${
                  isSelected ? 'ring-2 ring-white ring-offset-2 ring-offset-black scale-105 z-10' : 'hover:scale-102'
                }`}
                title={`${item.date}: ${item.count} de ${item.total} hábitos (${Math.round(item.ratio * 100)}%)`}
              >
                {displayDay}
              </button>
            );
          })}
        </div>
      </section>

      {/* 5. MODO TIMELAPSE DE EVOLUÇÃO ACUMULADA */}
      <section className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-white" />
            <div>
              <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-white">
                Modo Replay / Timelapse de Evolução
              </h2>
              <p className="text-[11px] text-neutral-500 font-mono mt-0.5">
                Veja o crescimento diário acumulado dia a dia com animação contínua
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={startTimelapse}
              disabled={isPlayingTimelapse}
              className="bg-white text-black px-3 py-1 rounded text-xs font-mono font-bold uppercase hover:bg-neutral-200 disabled:opacity-50 transition-colors flex items-center space-x-1 cursor-pointer"
            >
              <Play className="w-3 h-3" />
              <span>{isPlayingTimelapse ? 'Reproduzindo...' : 'Iniciar Replay'}</span>
            </button>
            <button
              onClick={() => {
                setIsPlayingTimelapse(false);
                setTimelapseIndex(evolutionHistory.length - 1);
              }}
              className="border border-neutral-800 text-neutral-400 hover:text-white px-2.5 py-1 rounded text-xs font-mono cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
          <div className="bg-black border border-neutral-900 p-3 rounded">
            <span className="text-[10px] text-neutral-500 uppercase block">Data no Replay</span>
            <span className="text-sm font-bold text-white">{currentEvolutionPoint.date}</span>
          </div>
          <div className="bg-black border border-neutral-900 p-3 rounded">
            <span className="text-[10px] text-neutral-500 uppercase block">Estudo Acumulado</span>
            <span className="text-sm font-bold text-white">{currentEvolutionPoint.studyMins} min</span>
          </div>
          <div className="bg-black border border-neutral-900 p-3 rounded">
            <span className="text-[10px] text-neutral-500 uppercase block">Carga Acumulada</span>
            <span className="text-sm font-bold text-white">{(currentEvolutionPoint.workoutVol).toLocaleString('pt-BR')} kg</span>
          </div>
          <div className="bg-black border border-neutral-900 p-3 rounded">
            <span className="text-[10px] text-neutral-500 uppercase block">Score de Performance</span>
            <span className="text-sm font-bold text-white">{currentEvolutionPoint.performanceScore || 80}%</span>
          </div>
        </div>
      </section>

      {/* 6. CITAÇÃO ESTÓICA & AUDITORIA DA IA */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Citação */}
        <section className="bg-neutral-950 border border-neutral-900 rounded p-5 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center space-x-2 text-neutral-500 font-mono text-xs mb-2">
              <Quote className="w-3.5 h-3.5" />
              <span className="uppercase tracking-wider">Citação de Fixação Ativa</span>
            </div>
            <p className="text-sm text-neutral-200 font-mono italic leading-relaxed">
              "{dailyQuote.quote}"
            </p>
          </div>
          <span className="text-xs font-mono text-neutral-500 border-t border-neutral-900 pt-2 block">
            — {dailyQuote.bookTitle}
          </span>
        </section>

        {/* Auditoria IA */}
        <section className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 text-white" />
              <h3 className="font-mono text-xs uppercase tracking-widest font-bold text-white">
                Auditoria do Mentor Estóico (IA)
              </h3>
            </div>
            <button
              onClick={handleRequestAudit}
              disabled={loadingAi}
              className="bg-white text-black px-3 py-1 rounded text-xs font-mono font-bold uppercase hover:bg-neutral-200 disabled:opacity-50 cursor-pointer"
            >
              {loadingAi ? 'Analisando...' : 'Auditar Hoje'}
            </button>
          </div>

          <div className="bg-black border border-neutral-900 p-3 rounded min-h-[90px] text-xs font-mono text-neutral-300 leading-relaxed">
            {aiAnalysis ? (
              <p className="whitespace-pre-wrap">{aiAnalysis}</p>
            ) : (
              <p className="text-neutral-500 italic">
                Clique em "Auditar Hoje" para cruzar os dados do dia ({formatDisplayDate(selectedDate)}) e receber um diagnóstico frio e cirúrgico do seu desempenho.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};
