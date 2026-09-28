import React, { useState, useEffect, useMemo } from 'react';
import { 
  Play, Pause, RotateCcw, Volume2, VolumeX, Plus, 
  Trash2, Edit3, BookOpen, Brain, Sparkles, Check, 
  X, ExternalLink, RefreshCw, BarChart2, Layers, Award,
  TrendingUp, Target
} from 'lucide-react';
import { 
  ResponsiveContainer, BarChart, Bar, LineChart, Line, 
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid 
} from 'recharts';
import { 
  Subject, StudyLog, ExamSimulation, Flashcard, 
  CognitiveRecord, PomodoroSessionState 
} from '../types';
import { FocusSoundType, playChime } from '../utils/sound';
import { getLocalDateString } from '../utils/storage';

interface StudyViewProps {
  selectedDate: string;
  subjects: Subject[];
  onAddSubject: (name: string) => void;
  onUpdateSubjectPoints: (id: string, delta: number) => void;
  studyLogs: StudyLog[];
  onAddStudyLog: (log: Omit<StudyLog, 'id' | 'timestamp'>) => void;
  onDeleteStudyLog: (id: string) => void;
  simulations: ExamSimulation[];
  onAddSimulation: (sim: Omit<ExamSimulation, 'id' | 'timestamp'>) => void;
  onDeleteSimulation: (id: string) => void;
  flashcards: Flashcard[];
  onAddFlashcard: (card: Omit<Flashcard, 'id'>) => void;
  onReviewFlashcard: (id: string, correct: boolean) => void;
  onDeleteFlashcard: (id: string) => void;
  cognitiveRecords: CognitiveRecord[];
  onAddCognitiveRecord: (rec: Omit<CognitiveRecord, 'id'>) => void;
  infiniteNotes: string;
  onChangeInfiniteNotes: (notes: string) => void;
  // Global Pomodoro Props
  pomodoro: PomodoroSessionState;
  onTogglePomodoro: () => void;
  onResetPomodoro: (minutes: number) => void;
  onSelectPomodoroSubject: (id: string, name: string) => void;
  onChangeSound: (sound: FocusSoundType) => void;
}

export const StudyView: React.FC<StudyViewProps> = ({
  selectedDate,
  subjects,
  onAddSubject,
  onUpdateSubjectPoints,
  studyLogs,
  onAddStudyLog,
  onDeleteStudyLog,
  simulations,
  onAddSimulation,
  onDeleteSimulation,
  flashcards,
  onAddFlashcard,
  onReviewFlashcard,
  onDeleteFlashcard,
  cognitiveRecords,
  onAddCognitiveRecord,
  infiniteNotes,
  onChangeInfiniteNotes,
  pomodoro,
  onTogglePomodoro,
  onResetPomodoro,
  onSelectPomodoroSubject,
  onChangeSound
}) => {
  // Sub-tabs inside Study
  const [studySubTab, setStudySubTab] = useState<'foco' | 'materias' | 'simulados' | 'graficos' | 'flashcards' | 'cognicao' | 'notas'>('foco');

  // YouTube audio player state
  const [youtubeUrl, setYoutubeUrl] = useState<string>('');
  const [embedVideoId, setEmbedVideoId] = useState<string>('');

  const handleSetYoutube = () => {
    try {
      const match = youtubeUrl.trim().match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))([\w-]{11})/);
      if (match && match[1]) {
        setEmbedVideoId(match[1]);
      } else if (youtubeUrl.trim().length === 11 && !youtubeUrl.includes('/')) {
        setEmbedVideoId(youtubeUrl.trim());
      }
    } catch {
      // ignore
    }
  };

  // --- 2. REGISTER STUDY LOG ---
  const [logSubjectId, setLogSubjectId] = useState<string>(subjects[0]?.id || '');
  const [logMinutes, setLogMinutes] = useState<string>('30');
  const [logNotes, setLogNotes] = useState<string>('');


  const handleSaveStudySession = () => {
    const subject = subjects.find(s => s.id === logSubjectId);
    if (!subject) return;

    onAddStudyLog({
      date: selectedDate,
      subjectId: subject.id,
      subjectName: subject.name,
      minutes: Number(logMinutes) || 30,
      notes: logNotes
    });

    // Award +1 point to the studied subject
    onUpdateSubjectPoints(subject.id, 1);
    setLogNotes('');
    playChime();
  };

  // --- 3. EXAM SIMULATIONS ---
  const [simSubjectId, setSimSubjectId] = useState<string>(subjects[0]?.id || '');
  const [simCorrect, setSimCorrect] = useState<string>('');
  const [simWrong, setSimWrong] = useState<string>('');
  const [simNotes, setSimNotes] = useState<string>('');

  const simCorrectNum = Number(simCorrect) || 0;
  const simWrongNum = Number(simWrong) || 0;
  const simTotalCalculated = simCorrectNum + simWrongNum;
  const simAccuracyCalculated = simTotalCalculated > 0 
    ? Math.round((simCorrectNum / simTotalCalculated) * 100) 
    : 0;

  const handleSaveSimulation = () => {
    const subject = subjects.find(s => s.id === simSubjectId);
    if (!subject || simTotalCalculated === 0) return;

    onAddSimulation({
      date: selectedDate,
      subjectId: subject.id,
      subjectName: subject.name,
      correct: simCorrectNum,
      wrong: simWrongNum,
      total: simTotalCalculated,
      accuracy: simAccuracyCalculated,
      notes: simNotes
    });

    setSimCorrect('');
    setSimWrong('');
    setSimNotes('');
    playChime();
  };

  // --- 4. SUBJECTS PRIORITY ALGORITHM ---
  // Matérias com menos pontos ou menor precisão sobem como prioridade máxima
  const sortedSubjects = useMemo(() => {
    return [...subjects].sort((a, b) => {
      // Prioridade: menor pontuação e menor tempo
      if (a.points !== b.points) {
        return a.points - b.points; // less studied comes first
      }
      return a.totalMinutes - b.totalMinutes;
    });
  }, [subjects]);

  const [newSubjectName, setNewSubjectName] = useState<string>('');
  const handleAddNewSubject = () => {
    if (!newSubjectName.trim()) return;
    onAddSubject(newSubjectName.trim());
    setNewSubjectName('');
  };

  // --- 5. FLASHCARDS SRS ---
  const [cardSubjectId, setCardSubjectId] = useState<string>(subjects[0]?.id || '');
  const [cardFront, setCardFront] = useState<string>('');
  const [cardBack, setCardBack] = useState<string>('');
  const [activeCardIndex, setActiveCardIndex] = useState<number>(0);
  const [isFlipped, setIsFlipped] = useState<boolean>(false);

  // Keep subject selection state synchronized when subjects update/load
  useEffect(() => {
    if (subjects.length > 0) {
      if (!subjects.some(s => s.id === logSubjectId)) {
        setLogSubjectId(subjects[0].id);
      }
      if (!subjects.some(s => s.id === simSubjectId)) {
        setSimSubjectId(subjects[0].id);
      }
      if (!subjects.some(s => s.id === cardSubjectId)) {
        setCardSubjectId(subjects[0].id);
      }
    }
  }, [subjects, logSubjectId, simSubjectId, cardSubjectId]);

  const handleAddCard = () => {
    if (!cardFront.trim() || !cardBack.trim()) return;
    onAddFlashcard({
      subjectId: cardSubjectId,
      front: cardFront,
      back: cardBack,
      box: 1,
      nextReviewDate: selectedDate
    });
    setCardFront('');
    setCardBack('');
    playChime();
  };

  // --- 6. COGNITIVE MEMORY GAME (DUAL N-BACK / MEMORY MATRIX) ---
  const [gridSequence, setGridSequence] = useState<number[]>([]);
  const [userSequence, setUserSequence] = useState<number[]>([]);
  const [isShowingPattern, setIsShowingPattern] = useState<boolean>(false);
  const [gameLevel, setGameLevel] = useState<number>(3);
  const [gameMessage, setGameMessage] = useState<string>('Clique em Iniciar para treinar a memória de trabalho');

  // Sudoku & Chess Manual Log
  const [cogType, setCogType] = useState<'sudoku' | 'chess'>('sudoku');
  const [cogScore, setCogScore] = useState<string>('');
  const [cogMinutes, setCogMinutes] = useState<string>('');
  const [cogResult, setCogResult] = useState<string>('Resolvido');

  const startMemoryGame = () => {
    const pattern: number[] = [];
    for (let i = 0; i < gameLevel; i++) {
      pattern.push(Math.floor(Math.random() * 9));
    }
    setGridSequence(pattern);
    setUserSequence([]);
    setIsShowingPattern(true);
    setGameMessage(`Memorize o padrão de ${gameLevel} blocos...`);

    setTimeout(() => {
      setIsShowingPattern(false);
      setGameMessage('Sua vez: repita o padrão na mesma ordem.');
    }, gameLevel * 750);
  };

  const handleGridClick = (index: number) => {
    if (isShowingPattern) return;
    const nextSeq = [...userSequence, index];
    setUserSequence(nextSeq);

    // Check match
    const step = nextSeq.length - 1;
    if (gridSequence[step] !== index) {
      setGameMessage('Padrão incorreto! Treino de memória registrado.');
      onAddCognitiveRecord({
        date: selectedDate,
        type: 'dual-n-back',
        score: gameLevel - 1,
        timeSeconds: 30,
        result: `Nível ${gameLevel - 1} alcançado`
      });
      setGameLevel(3);
      setGridSequence([]);
      setUserSequence([]);
      return;
    }

    if (nextSeq.length === gridSequence.length) {
      setGameMessage(`Perfeito! Nível ${gameLevel} concluído! Avançando...`);
      playChime();
      onAddCognitiveRecord({
        date: selectedDate,
        type: 'dual-n-back',
        score: gameLevel,
        timeSeconds: 45,
        result: `Nível ${gameLevel} dominado`
      });
      setGameLevel(l => l + 1);
      setTimeout(() => startMemoryGame(), 1000);
    }
  };

  const handleSaveCognitive = () => {
    onAddCognitiveRecord({
      date: selectedDate,
      type: cogType,
      score: Number(cogScore) || 0,
      timeSeconds: (Number(cogMinutes) || 0) * 60,
      result: cogResult
    });
    setCogScore('');
    setCogMinutes('');
    playChime();
  };

  // Day's study logs
  const todayStudyLogs = studyLogs.filter(s => s.date === selectedDate);
  const todaySimulations = simulations.filter(s => s.date === selectedDate);

  // --- CHART DATA PREPARATION ---
  // 1. Time distribution per subject
  const subjectChartData = useMemo(() => {
    return subjects.map(s => ({
      name: s.name.length > 14 ? s.name.slice(0, 12) + '...' : s.name,
      fullName: s.name,
      minutos: s.totalMinutes || 0,
      pontos: s.points || 0
    })).sort((a, b) => b.minutos - a.minutos);
  }, [subjects]);

  // 2. Exam simulations accuracy evolution
  const simulationChartData = useMemo(() => {
    return [...simulations]
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(s => {
        const parts = s.date.split('-');
        return {
          date: s.date,
          name: parts.length === 3 ? `${parts[2]}/${parts[1]}` : s.date,
          materia: s.subjectName,
          acertoPct: s.accuracy,
          acertos: s.correct,
          erros: s.wrong,
          total: s.total
        };
      });
  }, [simulations]);

  // 3. Daily study minutes (last 14 days)
  const dailyStudyChartData = useMemo(() => {
    const base = new Date();
    const res = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i, 12, 0, 0);
      const dStr = getLocalDateString(d);
      const mins = studyLogs.filter(s => s.date === dStr).reduce((acc, c) => acc + c.minutes, 0);
      res.push({
        date: dStr,
        name: `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')}`,
        minutos: mins
      });
    }
    return res;
  }, [studyLogs]);

  const totalMinutesAllSubjects = subjects.reduce((acc, s) => acc + (s.totalMinutes || 0), 0);
  const avgSimulationAccuracy = simulations.length > 0 
    ? Math.round(simulations.reduce((acc, s) => acc + s.accuracy, 0) / simulations.length)
    : 0;

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER & SUB-NAVIGATION */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-4">
        <div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
            <BookOpen className="w-4 h-4 text-white" />
            <span>Módulo de Estudo & Cognição</span>
          </h2>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Pomodoro, prioridades, simulados, gráficos e treino de memória
          </p>
        </div>

        {/* Sub-tabs pills */}
        <div className="flex items-center space-x-1 overflow-x-auto no-scrollbar bg-neutral-950 p-1 rounded border border-neutral-800">
          {[
            { id: 'foco', label: 'Pomodoro & Som' },
            { id: 'materias', label: 'Matérias & Prioridades' },
            { id: 'simulados', label: 'Simulados' },
            { id: 'graficos', label: 'Gráficos de Estudo' },
            { id: 'flashcards', label: 'Flashcards' },
            { id: 'cognicao', label: 'Memória & QI' },
            { id: 'notas', label: 'Notas Infinitas' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStudySubTab(tab.id as any)}
              className={`px-3 py-1 text-xs font-mono rounded whitespace-nowrap transition-colors ${
                studySubTab === tab.id 
                  ? 'bg-white text-black font-bold' 
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 1. ABA: POMODORO & FOCO SONORO */}
      {studySubTab === 'foco' && (
        <div className="space-y-6">
          {/* Cronômetro Central Minimalista */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-8 text-center relative overflow-hidden">
            {pomodoro.durationMinutes === 5 && (
              <div className="inline-block bg-white text-black text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-wider mb-4">
                Regra dos 5 Minutos (Anti-Procrastinação Ativa)
              </div>
            )}
            
            {/* Matéria Vinculada à Sessão */}
            <div className="flex items-center justify-center space-x-2 mb-4">
              <span className="text-[11px] font-mono text-neutral-500">Matéria:</span>
              <select
                value={pomodoro.subjectId || (subjects[0]?.id || '')}
                onChange={(e) => {
                  const s = subjects.find(sub => sub.id === e.target.value);
                  if (s) onSelectPomodoroSubject(s.id, s.name);
                }}
                className="bg-neutral-900 border border-neutral-800 text-white font-mono text-xs rounded px-3 py-1.5 focus:outline-none focus:border-white max-w-[240px] truncate"
              >
                {subjects.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div className="font-mono text-6xl md:text-8xl font-bold tracking-tight text-white mb-6 select-none">
              {Math.floor(pomodoro.timeLeftSeconds / 60).toString().padStart(2, '0')}:{(pomodoro.timeLeftSeconds % 60).toString().padStart(2, '0')}
            </div>

            <div className="flex items-center justify-center space-x-3 mb-6">
              <button
                onClick={onTogglePomodoro}
                className="bg-white text-black hover:bg-neutral-200 px-8 py-3 rounded font-mono text-xs font-bold uppercase tracking-widest transition-all shadow-lg cursor-pointer"
              >
                {pomodoro.isRunning ? 'Pausar Foco' : 'Iniciar Foco'}
              </button>
              <button
                onClick={() => onResetPomodoro(25)}
                className="border border-neutral-800 hover:border-white text-neutral-400 hover:text-white px-4 py-3 rounded font-mono text-xs uppercase"
              >
                Reset
              </button>
            </div>

            {/* Quick Timer Presets */}
            <div className="flex items-center justify-center space-x-2 text-xs font-mono">
              <button
                onClick={() => onResetPomodoro(5)}
                className={`px-3 py-1 rounded border transition-colors ${pomodoro.durationMinutes === 5 ? 'border-white text-white font-bold bg-neutral-900' : 'border-neutral-800 hover:border-white text-neutral-300'}`}
              >
                5 min (Anti-Inércia)
              </button>
              <button
                onClick={() => onResetPomodoro(25)}
                className={`px-3 py-1 rounded border transition-colors ${pomodoro.durationMinutes === 25 ? 'border-white text-white font-bold bg-neutral-900' : 'border-neutral-800 hover:border-white text-neutral-300'}`}
              >
                25 min (Clássico)
              </button>
              <button
                onClick={() => onResetPomodoro(50)}
                className={`px-3 py-1 rounded border transition-colors ${pomodoro.durationMinutes === 50 ? 'border-white text-white font-bold bg-neutral-900' : 'border-neutral-800 hover:border-white text-neutral-300'}`}
              >
                50 min (Profundo)
              </button>
            </div>
          </div>

          {/* Gerador de Áudio de Foco (Sintetizador Web Audio API) & YouTube Player */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Sintetizador de Som Ambiente */}
            <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs uppercase tracking-wider font-bold text-white flex items-center space-x-2">
                  <Volume2 className="w-4 h-4" />
                  <span>Áudio de Foco Sintetizado</span>
                </span>
                {pomodoro.activeSound !== 'none' && (
                  <span className="text-[10px] font-mono text-white bg-neutral-900 px-2 py-0.5 rounded animate-pulse">
                    Tocando: {pomodoro.activeSound}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'white', label: 'Ruído Branco' },
                  { id: 'brown', label: 'Ruído Marrom' },
                  { id: 'rain', label: 'Chuva Suave' },
                  { id: 'binaural40hz', label: 'Binaural 40Hz (Gama)' },
                ].map((s) => (
                  <button
                    key={s.id}
                    onClick={() => onChangeSound(pomodoro.activeSound === s.id ? 'none' : s.id as any)}
                    className={`py-2 text-xs font-mono rounded border text-center transition-colors ${
                      pomodoro.activeSound === s.id 
                        ? 'bg-white text-black border-white font-bold' 
                        : 'border-neutral-800 text-neutral-400 hover:border-neutral-600'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

              {pomodoro.activeSound !== 'none' && (
                <button
                  onClick={() => onChangeSound('none')}
                  className="w-full py-1 text-[11px] font-mono border border-neutral-900 text-neutral-500 hover:text-white"
                >
                  Silenciar Áudio
                </button>
              )}
            </div>

            {/* Reprodutor de Foco via Link do YouTube */}
            <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
              <span className="font-mono text-xs uppercase tracking-wider font-bold text-white block">
                Música de Estudo (YouTube)
              </span>
              <p className="text-[11px] text-neutral-500 font-mono">
                Cole o link de Lofi, ondas alfa ou música de foco:
              </p>

              <div className="flex space-x-2">
                <input
                  type="text"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  className="flex-1 bg-black border border-neutral-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-white font-mono"
                />
                <button
                  onClick={handleSetYoutube}
                  className="bg-white text-black px-3 py-1.5 rounded font-mono text-xs font-bold hover:bg-neutral-200"
                >
                  Carregar
                </button>
              </div>

              {embedVideoId && (
                <div className="aspect-video w-full rounded overflow-hidden border border-neutral-800 mt-2">
                  <iframe
                    src={`https://www.youtube.com/embed/${embedVideoId}?autoplay=1`}
                    title="YouTube Focus Audio"
                    className="w-full h-full"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  />
                </div>
              )}
            </div>
          </div>

          {/* Formulário Rápido de Registro de Estudo no Dia */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Registrar Sessão Estudada no Dia ({selectedDate})
            </h3>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Matéria</label>
                <select
                  value={logSubjectId}
                  onChange={(e) => setLogSubjectId(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-white font-mono"
                >
                  {subjects.map(s => (
                    <option key={s.id} value={s.id}>{s.name} ({s.points} pts)</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Tempo (minutos)</label>
                <input
                  type="number"
                  value={logMinutes}
                  onChange={(e) => setLogMinutes(e.target.value)}
                  placeholder="30"
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Observações / Tópicos</label>
                <input
                  type="text"
                  value={logNotes}
                  onChange={(e) => setLogNotes(e.target.value)}
                  placeholder="Ex: Teorema de Bayes, Exercícios 1 a 10..."
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-white font-mono"
                />
              </div>
            </div>

            <button
              onClick={handleSaveStudySession}
              className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-200 transition-colors"
            >
              + Salvar Registro e Adicionar 1 Ponto à Matéria
            </button>
          </div>

          {/* Histórico de Estudos Registrados no Dia */}
          <div className="space-y-2">
            <h4 className="font-mono text-xs text-neutral-500 uppercase tracking-wider">
              Registros de Estudo em {selectedDate}
            </h4>
            {todayStudyLogs.length === 0 ? (
              <p className="text-xs font-mono text-neutral-600 italic bg-black border border-neutral-900 p-4 rounded">
                Nenhuma sessão registrada nesta data ainda.
              </p>
            ) : (
              todayStudyLogs.map(log => (
                <div key={log.id} className="bg-black border border-neutral-800 p-3 rounded flex items-center justify-between">
                  <div>
                    <span className="font-mono text-xs font-bold text-white block">{log.subjectName}</span>
                    <span className="font-mono text-[11px] text-neutral-400">
                      {log.minutes} minutos estudados {log.notes && `• ${log.notes}`}
                    </span>
                  </div>
                  <button
                    onClick={() => onDeleteStudyLog(log.id)}
                    className="text-neutral-600 hover:text-red-400 p-1"
                    title="Excluir registro"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 2. ABA: MATÉRIAS & ALGORITMO DE PRIORIDADE */}
      {studySubTab === 'materias' && (
        <div className="space-y-6">
          {/* Adicionar nova matéria */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-4 flex gap-2">
            <input
              type="text"
              placeholder="Nome da matéria (ex: Termodinâmica, Estruturas de Dados)..."
              value={newSubjectName}
              onChange={(e) => setNewSubjectName(e.target.value)}
              className="flex-1 bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-white font-mono"
            />
            <button
              onClick={handleAddNewSubject}
              className="bg-white text-black px-4 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              Adicionar
            </button>
          </div>

          {/* Explicação do Algoritmo */}
          <div className="bg-neutral-900/40 border border-neutral-800 p-3 rounded text-[11px] font-mono text-neutral-400 flex items-start space-x-2">
            <Award className="w-4 h-4 text-white mt-0.5 shrink-0" />
            <div>
              <strong className="text-white">Algoritmo de Prioridade Ativo:</strong> As matérias menos estudadas ou com menor pontuação sobem para o topo automaticamente para evitar defasagem no seu conhecimento.
            </div>
          </div>

          {/* Lista de Matérias Ordenadas por Prioridade */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sortedSubjects.map((sub, index) => {
              const isHighPriority = index === 0 || sub.points <= 5;
              return (
                <div 
                  key={sub.id} 
                  className={`border rounded p-4 bg-black transition-all ${
                    isHighPriority ? 'border-neutral-600 shadow-md' : 'border-neutral-900'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-bold text-white">{sub.name}</span>
                        {isHighPriority && (
                          <span className="bg-white text-black text-[9px] font-mono font-bold px-1.5 py-0.2 rounded uppercase">
                            Prioridade Alta
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] font-mono text-neutral-500 block mt-1">
                        Total: {sub.totalMinutes} min estudados
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="font-mono text-xl font-bold text-white block">
                        {sub.points} <span className="text-xs font-normal text-neutral-500">pts</span>
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-neutral-900 flex items-center justify-between text-xs font-mono">
                    <span className="text-neutral-500 text-[10px]">
                      Último estudo: {sub.lastStudiedDate || 'Nunca'}
                    </span>
                    <div className="flex space-x-1">
                      <button
                        onClick={() => onUpdateSubjectPoints(sub.id, 1)}
                        className="border border-neutral-800 hover:border-white px-2 py-1 rounded text-white text-[10px]"
                        title="Adicionar +1 ponto"
                      >
                        +1 Ponto
                      </button>
                      <button
                        onClick={() => onUpdateSubjectPoints(sub.id, -1)}
                        className="border border-neutral-900 text-neutral-600 hover:text-white px-2 py-1 rounded text-[10px]"
                        title="Remover 1 ponto"
                      >
                        -1
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. ABA: SIMULADOS & TAXA DE ACERTO */}
      {studySubTab === 'simulados' && (
        <div className="space-y-6">
          {/* Formulário de Registro de Simulado */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Registrar Simulado / Questões Realizadas ({selectedDate})
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Matéria</label>
                <select
                  value={simSubjectId}
                  onChange={(e) => setSimSubjectId(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  {subjects.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Acertos</label>
                <input
                  type="number"
                  placeholder="Ex: 18"
                  value={simCorrect}
                  onChange={(e) => setSimCorrect(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-white"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Erros</label>
                <input
                  type="number"
                  placeholder="Ex: 4"
                  value={simWrong}
                  onChange={(e) => setSimWrong(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-white"
                />
              </div>

              {/* Total Automático e Taxa */}
              <div className="bg-black border border-neutral-800 p-2 rounded flex flex-col justify-center text-center">
                <span className="text-[9px] font-mono text-neutral-500 uppercase">Total & Taxa Calculados</span>
                <span className="font-mono text-sm font-bold text-white">
                  {simTotalCalculated} questões • {simAccuracyCalculated}%
                </span>
              </div>
            </div>

            <div>
              <label className="text-[10px] font-mono text-neutral-500 block mb-1">Anotações do Simulado (Opcional)</label>
              <input
                type="text"
                placeholder="Ex: Simulado ENEM 2025, erros principais em geometria espacial..."
                value={simNotes}
                onChange={(e) => setSimNotes(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
              />
            </div>

            <button
              onClick={handleSaveSimulation}
              disabled={simTotalCalculated === 0}
              className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-200 transition-colors disabled:opacity-40"
            >
              Salvar Simulado
            </button>
          </div>

          {/* Histórico Geral de Simulados */}
          <div className="space-y-3">
            <h4 className="font-mono text-xs text-neutral-500 uppercase tracking-wider">
              Histórico de Simulados Registrados
            </h4>
            {simulations.length === 0 ? (
              <p className="text-xs font-mono text-neutral-600 italic bg-black border border-neutral-900 p-4 rounded">
                Nenhum simulado cadastrado. Registre seu primeiro simulado acima para acompanhar a taxa de acerto.
              </p>
            ) : (
              simulations.map(sim => (
                <div key={sim.id} className="bg-black border border-neutral-900 p-4 rounded flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-xs font-bold text-white">{sim.subjectName}</span>
                      <span className="text-[10px] font-mono text-neutral-500">{sim.date}</span>
                    </div>
                    <div className="text-xs font-mono text-neutral-400 mt-1">
                      Total: <strong className="text-white">{sim.total}</strong> ({sim.correct} acertos, {sim.wrong} erros)
                      {sim.notes && <span className="text-neutral-500 ml-2">"{sim.notes}"</span>}
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <span className={`font-mono text-xs px-2.5 py-1 rounded font-bold ${
                      sim.accuracy >= 80 ? 'bg-white text-black' : 'border border-neutral-800 text-neutral-300'
                    }`}>
                      {sim.accuracy}%
                    </span>
                    <button
                      onClick={() => onDeleteSimulation(sim.id)}
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

      {/* 4. ABA: GRÁFICOS DE ESTUDO & SIMULADOS */}
      {studySubTab === 'graficos' && (
        <div className="space-y-6">
          {/* Métricas Resumo */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono">
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Tempo Total Estudado</span>
              <span className="text-xl font-bold text-white">{totalMinutesAllSubjects} min</span>
              <span className="text-[10px] text-neutral-500 block">{(totalMinutesAllSubjects / 60).toFixed(1)} horas</span>
            </div>
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Média em Simulados</span>
              <span className="text-xl font-bold text-white">{avgSimulationAccuracy}%</span>
              <span className="text-[10px] text-neutral-500 block">{simulations.length} simulados feitos</span>
            </div>
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Total de Questões</span>
              <span className="text-xl font-bold text-white">
                {simulations.reduce((acc, s) => acc + s.total, 0)}
              </span>
              <span className="text-[10px] text-neutral-500 block">
                {simulations.reduce((acc, s) => acc + s.correct, 0)} acertos
              </span>
            </div>
            <div className="bg-neutral-950 border border-neutral-900 p-4 rounded">
              <span className="text-[10px] text-neutral-500 uppercase block">Matérias Ativas</span>
              <span className="text-xl font-bold text-white">{subjects.length}</span>
              <span className="text-[10px] text-neutral-500 block">no algoritmo</span>
            </div>
          </div>

          {/* Gráfico 1: Tempo por Matéria */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
              <div className="flex items-center space-x-2">
                <BarChart2 className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  Distribuição de Tempo por Matéria (Minutos Acumulados)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">
                Identifique disciplinas negligenciadas
              </span>
            </div>

            {subjectChartData.length > 0 ? (
              <div className="w-full h-64 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={subjectChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                    <XAxis 
                      dataKey="name" 
                      stroke="#666" 
                      fontSize={11} 
                      tickLine={false} 
                      angle={-20} 
                      textAnchor="end" 
                    />
                    <YAxis stroke="#666" fontSize={11} tickLine={false} />
                    <Tooltip 
                      content={({ active, payload }: any) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl space-y-1">
                              <p className="text-white font-bold">{data.fullName}</p>
                              <p className="text-neutral-300">Tempo: <strong className="text-white">{data.minutos} min</strong></p>
                              <p className="text-neutral-400">Pontos: {data.pontos} pts</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="minutos" name="Minutos" fill="#ffffff" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs font-mono text-neutral-500 italic py-6 text-center">
                Cadastre matérias para visualizar a distribuição gráfica.
              </p>
            )}
          </div>

          {/* Gráfico 2: Evolução de Taxa de Acerto em Simulados */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  Evolução de Assertividade nos Simulados (% Acerto)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">
                Progresso histórico contínuo
              </span>
            </div>

            {simulationChartData.length > 0 ? (
              <div className="w-full h-64 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={simulationChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                    <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
                    <YAxis stroke="#666" fontSize={11} tickLine={false} domain={[0, 100]} unit="%" />
                    <Tooltip 
                      content={({ active, payload }: any) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl space-y-1">
                              <p className="text-white font-bold">{data.materia} ({data.date})</p>
                              <p className="text-neutral-300">Taxa de Acerto: <strong className="text-white">{data.acertoPct}%</strong></p>
                              <p className="text-neutral-400">Desempenho: {data.acertos} acertos de {data.total} questões</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="acertoPct" 
                      name="% Acerto" 
                      stroke="#ffffff" 
                      strokeWidth={2}
                      dot={{ r: 4, fill: '#ffffff' }} 
                      activeDot={{ r: 6, fill: '#ffffff' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs font-mono text-neutral-500 italic py-6 text-center">
                Nenhum simulado registrado ainda. Adicione simulados na aba "Simulados" para acompanhar a curva de aprendizado!
              </p>
            )}
          </div>

          {/* Gráfico 3: Minutos Estudados nos Últimos 14 Dias */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
              <div className="flex items-center space-x-2">
                <Target className="w-4 h-4 text-white" />
                <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
                  Consistência Diária de Estudo (Últimos 14 Dias)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">Minutos por dia</span>
            </div>

            <div className="w-full h-56 pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dailyStudyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                  <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
                  <YAxis stroke="#666" fontSize={11} tickLine={false} unit="m" />
                  <Tooltip 
                    content={({ active, payload }: any) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-black border border-neutral-700 p-2.5 rounded font-mono text-xs shadow-xl">
                            <p className="text-white font-bold">{data.date}</p>
                            <p className="text-neutral-300">Tempo: <strong className="text-white">{data.minutos} min</strong></p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="minutos" 
                    name="Minutos" 
                    stroke="#ffffff" 
                    strokeWidth={2}
                    fill="#333" 
                    fillOpacity={0.6} 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* 5. ABA: FLASHCARDS SRS */}
      {studySubTab === 'flashcards' && (
        <div className="space-y-6">
          {/* Adicionar Flashcard */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Criar Novo Flashcard
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <textarea
                placeholder="Frente (Pergunta ou Conceito)..."
                value={cardFront}
                onChange={(e) => setCardFront(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono focus:outline-none focus:border-white h-24 resize-none"
              />
              <textarea
                placeholder="Verso (Resposta ou Explicação)..."
                value={cardBack}
                onChange={(e) => setCardBack(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono focus:outline-none focus:border-white h-24 resize-none"
              />
            </div>
            <button
              onClick={handleAddCard}
              className="bg-white text-black px-6 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              Salvar Flashcard
            </button>
          </div>

          {/* Modo de Revisão Ativo */}
          {flashcards.length > 0 ? (
            <div className="bg-black border border-neutral-800 rounded p-8 text-center space-y-6 max-w-xl mx-auto">
              <span className="text-[10px] font-mono text-neutral-500 uppercase tracking-widest block">
                Cartão {activeCardIndex + 1} de {flashcards.length}
              </span>

              <div 
                onClick={() => setIsFlipped(!isFlipped)}
                className="min-h-[180px] bg-neutral-950 border border-neutral-800 hover:border-neutral-600 rounded p-6 flex flex-col justify-center items-center cursor-pointer transition-all"
              >
                <span className="text-[10px] font-mono text-neutral-500 uppercase mb-2">
                  {isFlipped ? 'VERSO (RESPOSTA)' : 'FRENTE (CLIQUE PARA VIRAR)'}
                </span>
                <p className="font-mono text-sm md:text-base text-white font-medium">
                  {isFlipped 
                    ? flashcards[activeCardIndex]?.back 
                    : flashcards[activeCardIndex]?.front}
                </p>
              </div>

              <div className="flex justify-center space-x-4">
                <button
                  onClick={() => {
                    onReviewFlashcard(flashcards[activeCardIndex].id, false);
                    setIsFlipped(false);
                    setActiveCardIndex((prev) => (prev + 1) % flashcards.length);
                  }}
                  className="border border-neutral-800 text-neutral-400 hover:border-red-500 hover:text-red-400 px-6 py-2 rounded font-mono text-xs uppercase"
                >
                  Errei
                </button>
                <button
                  onClick={() => {
                    onReviewFlashcard(flashcards[activeCardIndex].id, true);
                    setIsFlipped(false);
                    setActiveCardIndex((prev) => (prev + 1) % flashcards.length);
                    playChime();
                  }}
                  className="bg-white text-black hover:bg-neutral-200 px-6 py-2 rounded font-mono text-xs font-bold uppercase"
                >
                  Acertei
                </button>
              </div>
            </div>
          ) : (
            <p className="text-xs font-mono text-neutral-600 italic text-center p-6 bg-black border border-neutral-900 rounded">
              Nenhum flashcard criado ainda. Crie seu primeiro acima para memorização espaçada.
            </p>
          )}
        </div>
      )}

      {/* 5. ABA: MEMÓRIA & QI (DUAL N-BACK & SUDOKU/XADREZ) */}
      {studySubTab === 'cognicao' && (
        <div className="space-y-6">
          {/* Treino Interativo de Memória de Trabalho (Memory Matrix) */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white flex items-center space-x-2">
                  <Brain className="w-4 h-4 text-white" />
                  <span>Treino de Memória de Trabalho (Nível {gameLevel})</span>
                </h3>
                <p className="text-[11px] font-mono text-neutral-400 mt-0.5">
                  {gameMessage}
                </p>
              </div>
              <button
                onClick={startMemoryGame}
                className="bg-white text-black px-4 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
              >
                {gridSequence.length > 0 ? 'Reiniciar' : 'Começar Desafio'}
              </button>
            </div>

            {/* 3x3 Memory Grid */}
            <div className="grid grid-cols-3 gap-2.5 max-w-[280px] mx-auto pt-4">
              {Array.from({ length: 9 }).map((_, idx) => {
                const isHighlight = isShowingPattern && gridSequence.includes(idx);
                const isUserClicked = userSequence.includes(idx);

                let cellBg = 'bg-black border-neutral-800 hover:border-neutral-500';
                if (isHighlight) cellBg = 'bg-white border-white scale-95 shadow-lg';
                if (isUserClicked && !isShowingPattern) cellBg = 'bg-neutral-400 border-white';

                return (
                  <button
                    key={idx}
                    disabled={isShowingPattern || gridSequence.length === 0}
                    onClick={() => handleGridClick(idx)}
                    className={`h-20 border rounded transition-all cursor-pointer ${cellBg}`}
                  />
                );
              })}
            </div>
          </div>

          {/* Registro Manual de Sudoku e Xadrez */}
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Registro de Sudoku / Xadrez (Evolução Cognitiva)
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Modalidade</label>
                <select
                  value={cogType}
                  onChange={(e) => setCogType(e.target.value as any)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  <option value="sudoku">Sudoku</option>
                  <option value="chess">Táticas / Partida de Xadrez</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                  {cogType === 'sudoku' ? 'Dificuldade / Pontos' : 'Rating / Precisão'}
                </label>
                <input
                  type="number"
                  placeholder="Ex: 1450"
                  value={cogScore}
                  onChange={(e) => setCogScore(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Tempo Gasto (minutos)</label>
                <input
                  type="number"
                  placeholder="Ex: 15"
                  value={cogMinutes}
                  onChange={(e) => setCogMinutes(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Resultado / Observação</label>
                <input
                  type="text"
                  placeholder="Ex: Vitória no meio-jogo, resolvido sem dicas"
                  value={cogResult}
                  onChange={(e) => setCogResult(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            </div>

            <button
              onClick={handleSaveCognitive}
              className="bg-white text-black px-6 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              Registrar Sessão Cognitiva
            </button>
          </div>

          {/* Histórico Cognitivo */}
          <div className="space-y-2">
            <h4 className="font-mono text-xs text-neutral-500 uppercase tracking-wider">
              Histórico de Treinos Cognitivos
            </h4>
            {cognitiveRecords.map((c) => (
              <div key={c.id} className="bg-black border border-neutral-900 p-3 rounded flex items-center justify-between font-mono text-xs">
                <div>
                  <span className="font-bold text-white uppercase">{c.type}</span>
                  <span className="text-neutral-500 ml-2">({c.date})</span>
                  <p className="text-neutral-400 text-[11px] mt-0.5">{c.result}</p>
                </div>
                <div className="text-right">
                  <span className="text-white font-bold">{c.score} pts</span>
                  <span className="text-neutral-500 text-[10px] block">{Math.round(c.timeSeconds / 60)} min</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 6. ABA: NOTAS INFINITAS ESTILO PAUTADO */}
      {studySubTab === 'notas' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Caderno de Anotações Infinitas
            </span>
            <span className="text-[10px] font-mono text-neutral-500">
              Salvo automaticamente em tempo real
            </span>
          </div>

          <div className="bg-neutral-950 border border-neutral-900 rounded p-4">
            <textarea
              value={infiniteNotes}
              onChange={(e) => onChangeInfiniteNotes(e.target.value)}
              placeholder="Digite aqui suas anotações, fórmulas, insights e resumos com rolagem infinita..."
              className="w-full min-h-[400px] bg-transparent text-neutral-100 font-mono text-xs leading-7 lined-paper focus:outline-none resize-y"
            />
          </div>
        </div>
      )}
    </div>
  );
};
