import React, { useState, useMemo } from 'react';
import { 
  CheckSquare, Plus, Trash2, CheckCircle2, Circle, 
  Flame, Award, Link as LinkIcon, Edit2, BarChart2, TrendingUp,
  Grid, Calendar, Crown
} from 'lucide-react';
import { 
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, 
  Tooltip, CartesianGrid 
} from 'recharts';
import { Habit, HabitLog } from '../types';
import { getLocalDateString, parseLocalDate, formatDisplayDate, StorageKeys, getStoredItem } from '../utils/storage';
import { playChime } from '../utils/sound';

interface HabitsViewProps {
  selectedDate: string;
  setSelectedDate?: (date: string) => void;
  habits: Habit[];
  habitLogs: HabitLog;
  onToggleHabit: (habitId: string) => void;
  onTogglePriority?: (habitId: string) => void;
  onUpdateHabitValue: (habitId: string, value: number) => void;
  onAddHabit: (habit: Omit<Habit, 'id' | 'streak' | 'bestStreak'>) => void;
  onDeleteHabit: (id: string) => void;
}

export const HabitsView: React.FC<HabitsViewProps> = ({
  selectedDate,
  setSelectedDate,
  habits,
  habitLogs,
  onToggleHabit,
  onTogglePriority,
  onUpdateHabitValue,
  onAddHabit,
  onDeleteHabit
}) => {
  const [showAddForm, setShowAddForm] = useState(false);
  const [title, setTitle] = useState('');
  const [type, setType] = useState<'boolean' | 'number'>('boolean');
  const [targetValue, setTargetValue] = useState<string>('10');
  const [unit, setUnit] = useState('páginas');
  const [connectedTo, setConnectedTo] = useState<string>('');
  const [customStartDate, setCustomStartDate] = useState<string>(selectedDate);

  // Habits active on the selected date (created on or before selectedDate)
  const activeHabits = useMemo(() => {
    return habits.filter(h => !h.createdAt || h.createdAt <= selectedDate);
  }, [habits, selectedDate]);

  const handleCreate = () => {
    if (!title.trim()) return;

    onAddHabit({
      title: title.trim(),
      type,
      targetValue: type === 'number' ? Number(targetValue) || 1 : undefined,
      unit: type === 'number' ? unit : undefined,
      connectedTo: (connectedTo as any) || undefined,
      createdAt: customStartDate || selectedDate
    });

    setTitle('');
    setShowAddForm(false);
    playChime();
  };

  const completedCount = activeHabits.filter(h => habitLogs[h.id]?.completed).length;

  // 14-day Habit Consistency Data - accurately reads each day's existing habits using local date
  const habitsTrendData = useMemo(() => {
    const base = new Date();
    const list = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i, 12, 0, 0);
      const dStr = getLocalDateString(d);
      const parts = dStr.split('-');
      const displayDate = parts.length === 3 ? `${parts[2]}/${parts[1]}` : dStr;

      // Habits active on day dStr
      const dayActiveHabits = habits.filter(h => !h.createdAt || h.createdAt <= dStr);

      let done = 0;
      if (dStr === selectedDate) {
        done = completedCount;
      } else {
        const logs = getStoredItem<HabitLog>(`${StorageKeys.HABIT_LOGS_PREFIX}${dStr}`, {});
        done = dayActiveHabits.filter(h => logs[h.id]?.completed).length;
      }
      const total = dayActiveHabits.length;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      list.push({
        date: dStr,
        name: displayDate,
        feitos: done,
        total,
        taxa: pct
      });
    }
    return list;
  }, [selectedDate, habits, habitLogs, completedCount]);

  const [showConsistencyChart, setShowConsistencyChart] = useState(false);
  const [heatmapDays, setHeatmapDays] = useState<30 | 60 | 90>(90);
  const [showHeatmap, setShowHeatmap] = useState(true);

  const heatmapData = useMemo(() => {
    const base = new Date();
    const days: Array<{
      date: string;
      dayOfWeek: number;
      done: number;
      total: number;
      pct: number;
      level: number;
      isToday: boolean;
      isSelected: boolean;
      isPlaceholder?: boolean;
    }> = [];

    // Determine start date
    const startDate = new Date(base.getFullYear(), base.getMonth(), base.getDate() - (heatmapDays - 1), 12, 0, 0);
    const startDayOfWeek = startDate.getDay(); // 0 = Sun, 1 = Mon ...

    // Pad beginning with placeholders so Sunday is always row 0
    for (let p = 0; p < startDayOfWeek; p++) {
      days.push({
        date: '',
        dayOfWeek: p,
        done: 0,
        total: 0,
        pct: 0,
        level: -1,
        isToday: false,
        isSelected: false,
        isPlaceholder: true
      });
    }

    let fullDays = 0;
    let totalPctSum = 0;
    let daysWithHabits = 0;

    for (let i = heatmapDays - 1; i >= 0; i--) {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i, 12, 0, 0);
      const dStr = getLocalDateString(d);
      const dayOfWeek = d.getDay();

      const dayActiveHabits = habits.filter(h => !h.createdAt || h.createdAt <= dStr);
      let done = 0;
      if (dStr === selectedDate) {
        done = completedCount;
      } else {
        const logs = getStoredItem<HabitLog>(`${StorageKeys.HABIT_LOGS_PREFIX}${dStr}`, {});
        done = dayActiveHabits.filter(h => logs[h.id]?.completed).length;
      }
      const total = dayActiveHabits.length;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;

      if (total > 0) {
        daysWithHabits++;
        totalPctSum += pct;
        if (pct === 100) fullDays++;
      }

      let level = 0;
      if (total > 0) {
        if (pct === 100) level = 4;
        else if (pct >= 70) level = 3;
        else if (pct >= 40) level = 2;
        else if (pct > 0) level = 1;
      }

      days.push({
        date: dStr,
        dayOfWeek,
        done,
        total,
        pct,
        level,
        isToday: dStr === getLocalDateString(new Date()),
        isSelected: dStr === selectedDate,
        isPlaceholder: false
      });
    }

    const avgPct = daysWithHabits > 0 ? Math.round(totalPctSum / daysWithHabits) : 0;
    return { days, fullDays, avgPct, daysWithHabits };
  }, [heatmapDays, selectedDate, habits, completedCount]);

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-4">
        <div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
            <CheckSquare className="w-4 h-4 text-white" />
            <span>Hábitos & Disciplina Rígida</span>
          </h2>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Hábitos binários e quantitativos com integração automática aos módulos
          </p>
        </div>

        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="bg-white text-black px-4 py-1.5 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200 transition-colors flex items-center space-x-1.5 self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>{showAddForm ? 'Fechar' : 'Novo Hábito'}</span>
        </button>
      </div>

      {/* FORMULÁRIO DE NOVO HÁBITO */}
      {showAddForm && (
        <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
          <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
            Configurar Novo Hábito Inegociável
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">Título do Hábito</label>
              <input
                type="text"
                placeholder="Ex: Leitura Noturna, Banho Frio, Treino de Força..."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              />
            </div>

            <div>
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">Tipo de Medição</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as any)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              >
                <option value="boolean">Binário (Fiz / Não Fiz)</option>
                <option value="number">Quantitativo (Meta Numérica)</option>
              </select>
            </div>

            {type === 'number' && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">Meta</label>
                  <input
                    type="number"
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">Unidade</label>
                  <input
                    type="text"
                    placeholder="páginas, ml, min..."
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                Data de Início do Hábito
              </label>
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              />
            </div>

            <div>
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                Conexão Automática com Módulos (Opcional)
              </label>
              <select
                value={connectedTo}
                onChange={(e) => setConnectedTo(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              >
                <option value="">Nenhuma (Check manual)</option>
                <option value="treino">Treino (Conclui automaticamente ao registrar exercícios)</option>
                <option value="agua">Hidratação (Conclui ao bater 3000ml de água)</option>
                <option value="estudo">Estudo (Conclui ao registrar sessões de foco)</option>
                <option value="leitura">Leitura (Conclui ao registrar páginas lidas)</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleCreate}
            className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-200 transition-colors cursor-pointer"
          >
            Salvar e Ativar Hábito
          </button>
        </div>
      )}

      {/* STATUS DO DIA */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 font-mono text-xs">
        <span className="text-neutral-400">
          Progresso em <strong className="text-white">{formatDisplayDate(selectedDate)}</strong> ({selectedDate}):
        </span>
        <div className="flex items-center flex-wrap gap-2">
          <span className="text-white font-bold">{completedCount} de {activeHabits.length} concluídos</span>
          <span className="bg-neutral-900 text-neutral-300 text-[10px] px-2 py-0.5 rounded">
            {activeHabits.length > 0 ? Math.round((completedCount / activeHabits.length) * 100) : 0}%
          </span>
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className={`text-[10px] border px-2 py-0.5 rounded transition-colors flex items-center space-x-1 cursor-pointer ${
              showHeatmap ? 'border-white text-white bg-neutral-900' : 'border-neutral-800 text-neutral-400 hover:text-white'
            }`}
          >
            <Grid className="w-3 h-3" />
            <span>Heatmap</span>
          </button>
          <button
            onClick={() => setShowConsistencyChart(!showConsistencyChart)}
            className={`text-[10px] border px-2 py-0.5 rounded transition-colors flex items-center space-x-1 cursor-pointer ${
              showConsistencyChart ? 'border-white text-white bg-neutral-900' : 'border-neutral-800 text-neutral-400 hover:text-white'
            }`}
          >
            <BarChart2 className="w-3 h-3" />
            <span>Barras 14D</span>
          </button>
        </div>
      </div>

      {/* HEATMAP DE HÁBITOS (30 / 60 / 90 DIAS) */}
      {showHeatmap && (
        <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-900 pb-3">
            <div className="flex items-center space-x-2">
              <Grid className="w-4 h-4 text-white" />
              <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                Heatmap de Consistência & Disciplina
              </h3>
            </div>
            
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1 bg-black border border-neutral-800 rounded p-0.5">
                {([30, 60, 90] as const).map(d => (
                  <button
                    key={d}
                    onClick={() => setHeatmapDays(d)}
                    className={`px-2 py-0.5 text-[10px] font-mono rounded cursor-pointer transition-all ${
                      heatmapDays === d 
                        ? 'bg-white text-black font-bold shadow-sm' 
                        : 'text-neutral-400 hover:text-white'
                    }`}
                  >
                    {d}D
                  </button>
                ))}
              </div>

              <div className="hidden sm:flex items-center space-x-3 text-[11px] font-mono">
                <span className="text-neutral-400">
                  100%: <strong className="text-white">{heatmapData.fullDays} dias</strong>
                </span>
                <span className="text-neutral-400">
                  Média: <strong className="text-white">{heatmapData.avgPct}%</strong>
                </span>
              </div>
            </div>
          </div>

          {/* GRID DO HEATMAP */}
          <div className="overflow-x-auto pb-2 pt-1">
            <div className="min-w-fit flex items-start space-x-2">
              {/* Day of week labels */}
              <div className="grid grid-rows-7 gap-1 text-[9px] font-mono text-neutral-500 pr-1 select-none pt-0.5">
                <span className="h-3.5 leading-[14px]">D</span>
                <span className="h-3.5 leading-[14px]">S</span>
                <span className="h-3.5 leading-[14px]">T</span>
                <span className="h-3.5 leading-[14px]">Q</span>
                <span className="h-3.5 leading-[14px]">Q</span>
                <span className="h-3.5 leading-[14px]">S</span>
                <span className="h-3.5 leading-[14px]">S</span>
              </div>

              {/* Grid 7 rows x N columns */}
              <div className="grid grid-rows-7 grid-flow-col gap-1">
                {heatmapData.days.map((day, idx) => {
                  if (day.isPlaceholder) {
                    return <div key={`ph-${idx}`} className="w-3.5 h-3.5 opacity-0" />;
                  }

                  let colorClass = 'bg-neutral-900/80 border-neutral-800/80';
                  if (day.level === 1) colorClass = 'bg-neutral-800 border-neutral-700';
                  else if (day.level === 2) colorClass = 'bg-neutral-600 border-neutral-500';
                  else if (day.level === 3) colorClass = 'bg-neutral-300 border-neutral-200 text-black';
                  else if (day.level === 4) colorClass = 'bg-white border-white shadow-[0_0_6px_rgba(255,255,255,0.4)] text-black';

                  return (
                    <button
                      key={day.date}
                      onClick={() => setSelectedDate && setSelectedDate(day.date)}
                      title={`${day.date}: ${day.done}/${day.total} concluídos (${day.pct}%)${day.isSelected ? ' [Selecionado]' : ''}`}
                      className={`w-3.5 h-3.5 rounded-[2px] border transition-all cursor-pointer ${colorClass} ${
                        day.isSelected 
                          ? 'ring-2 ring-white ring-offset-1 ring-offset-black scale-110 z-10' 
                          : 'hover:scale-125 hover:z-10'
                      }`}
                    />
                  );
                })}
              </div>
            </div>
          </div>

          {/* LEGENDA E FOOTER */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pt-2 border-t border-neutral-900/80 text-[10px] font-mono text-neutral-500">
            <span>Clique em qualquer quadrado para navegar até o dia correspondente.</span>
            <div className="flex items-center space-x-1.5 self-end sm:self-auto">
              <span>0%</span>
              <div className="w-3 h-3 rounded-[2px] bg-neutral-900/80 border border-neutral-800" />
              <div className="w-3 h-3 rounded-[2px] bg-neutral-800 border border-neutral-700" />
              <div className="w-3 h-3 rounded-[2px] bg-neutral-600 border border-neutral-500" />
              <div className="w-3 h-3 rounded-[2px] bg-neutral-300 border border-neutral-200" />
              <div className="w-3 h-3 rounded-[2px] bg-white border border-white" />
              <span>100%</span>
            </div>
          </div>
        </div>
      )}

      {/* GRÁFICO DE CONSISTÊNCIA DE HÁBITOS (14 DIAS) */}
      {showConsistencyChart && (
        <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-white" />
              <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                Taxa de Conclusão Diária (% nos Últimos 14 Dias)
              </h3>
            </div>
            <span className="text-[10px] font-mono text-neutral-500">
              Manter acima de 80%
            </span>
          </div>

          <div className="w-full h-48 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart 
                data={habitsTrendData} 
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                onClick={(e: any) => {
                  if (e && e.activePayload && e.activePayload.length && setSelectedDate) {
                    const clickedDate = e.activePayload[0].payload.date;
                    if (clickedDate) setSelectedDate(clickedDate);
                  }
                }}
                style={{ cursor: setSelectedDate ? 'pointer' : 'default' }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
                <YAxis stroke="#666" fontSize={11} tickLine={false} domain={[0, 100]} unit="%" />
                <Tooltip 
                  content={({ active, payload }: any) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl space-y-1">
                          <p className="text-white font-bold">{data.date}</p>
                          <p className="text-neutral-300">Taxa: <strong className="text-white">{data.taxa}%</strong></p>
                          <p className="text-neutral-400">{data.feitos} de {data.total} concluídos</p>
                          {setSelectedDate && <p className="text-[10px] text-neutral-400 border-t border-neutral-800 pt-1">Clique para abrir este dia</p>}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="taxa" name="Taxa (%)" fill="#ffffff" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* LISTA DE HÁBITOS */}
      <div className="space-y-3">
        {activeHabits.length === 0 ? (
          <div className="p-8 text-center border border-neutral-900 rounded bg-neutral-950/50 font-mono text-xs text-neutral-500 space-y-2">
            <p>Nenhum hábito cadastrado até {formatDisplayDate(selectedDate)} ({selectedDate}).</p>
            <p className="text-[11px] text-neutral-600">
              Hábitos cadastrados em datas posteriores não são exibidos no passado para manter a fidelidade histórica.
            </p>
          </div>
        ) : (
          activeHabits.map((h) => {
          const log = habitLogs[h.id] || { completed: false, currentValue: 0 };
          const isDone = log.completed;

          return (
            <div
              key={h.id}
              className={`border rounded p-4 transition-all ${
                isDone 
                  ? 'bg-neutral-950 border-neutral-700 shadow-sm' 
                  : 'bg-black border-neutral-900'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                {/* Botão de Conclusão / Check */}
                <div className="flex items-center space-x-3 flex-1">
                  <button
                    onClick={() => {
                      onToggleHabit(h.id);
                      playChime();
                    }}
                    className="p-1 hover:scale-110 transition-transform cursor-pointer"
                  >
                    {isDone ? (
                      <CheckCircle2 className="w-6 h-6 text-white fill-white text-black" />
                    ) : (
                      <Circle className="w-6 h-6 text-neutral-700 hover:text-white" />
                    )}
                  </button>

                  <div>
                    <div className="flex items-center space-x-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onTogglePriority) {
                            onTogglePriority(h.id);
                            playChime();
                          }
                        }}
                        title={h.isPriority ? "Hábito Inegociável (clique para remover)" : "Marcar como Hábito Inegociável"}
                        className={`p-1 rounded transition-all cursor-pointer ${
                          h.isPriority 
                            ? 'text-amber-400 hover:text-amber-300 bg-amber-400/10' 
                            : 'text-neutral-700 hover:text-amber-400 hover:bg-neutral-900'
                        }`}
                      >
                        <Crown className={`w-4 h-4 transition-transform ${h.isPriority ? 'fill-amber-400 scale-110 drop-shadow-[0_0_8px_rgba(251,191,36,0.6)]' : ''}`} />
                      </button>
                      <span className={`font-mono text-sm font-bold ${isDone ? 'line-through text-neutral-400' : 'text-white'}`}>
                        {h.title}
                      </span>
                      {h.isPriority && (
                        <span className="bg-amber-400/10 border border-amber-400/30 text-amber-400 text-[9px] font-mono px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">
                          Inegociável
                        </span>
                      )}
                      {h.connectedTo && (
                        <span className="bg-neutral-900 text-neutral-400 text-[9px] font-mono px-1.5 py-0.5 rounded flex items-center space-x-1" title="Integrado automaticamente">
                          <LinkIcon className="w-2.5 h-2.5" />
                          <span className="uppercase">{h.connectedTo}</span>
                        </span>
                      )}
                    </div>

                    {/* Streaks info */}
                    <div className="flex items-center space-x-3 text-[11px] font-mono text-neutral-500 mt-1">
                      <span className="flex items-center space-x-1 text-white">
                        <Flame className="w-3 h-3 text-white" />
                        <span>{h.streak} dias seguidos</span>
                      </span>
                      <span>•</span>
                      <span>Recorde: {h.bestStreak} dias</span>
                    </div>
                  </div>
                </div>

                {/* Quantitative input if applicable */}
                {h.type === 'number' && (
                  <div className="flex items-center space-x-2 bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1">
                    <input
                      type="number"
                      value={log.currentValue || 0}
                      onChange={(e) => onUpdateHabitValue(h.id, Number(e.target.value))}
                      className="w-16 bg-transparent text-white font-mono text-xs text-right focus:outline-none"
                    />
                    <span className="font-mono text-xs text-neutral-500">
                      / {h.targetValue} {h.unit}
                    </span>
                  </div>
                )}

                {/* Excluir */}
                <button
                  onClick={() => onDeleteHabit(h.id)}
                  className="text-neutral-700 hover:text-red-400 p-1"
                  title="Excluir hábito"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        }))}
      </div>
    </div>
  );
};
