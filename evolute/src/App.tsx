import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  TabType, Habit, HabitLog, Subject, StudyLog, 
  ExamSimulation, Flashcard, WorkoutExercise, WorkoutSplitDay, 
  BodyWeightLog, Book, BookQuote, BookSummary, MentalLog, 
  ViceItem, ViceLog, CognitiveRecord, ApiSettings, DayVictory,
  EvolutionHistoryItem, PomodoroSessionState, DailyReadingLog, BodyPhoto
} from './types';
import { 
  DEFAULT_SPLIT, DEFAULT_HABITS, DEFAULT_SUBJECTS, 
  DEFAULT_BOOKS, DEFAULT_QUOTES, DEFAULT_VICES, 
  DEFAULT_API_SETTINGS, StorageKeys, getStoredItem, setStoredItem,
  getLocalDateString, parseLocalDate, formatDisplayDate
} from './utils/storage';
import { pullLatestFromServer } from './utils/sync';
import { playFocusSound, stopFocusSound, FocusSoundType, playChime } from './utils/sound';
import { Navbar } from './components/Navbar';
import { BottomNav } from './components/BottomNav';
import { DashboardView } from './components/DashboardView';
import { StudyView } from './components/StudyView';
import { WorkoutView } from './components/WorkoutView';
import { HabitsView } from './components/HabitsView';
import { ReadingView } from './components/ReadingView';
import { MentalView } from './components/MentalView';
import { AntiViceView } from './components/AntiViceView';
import { CalendarView } from './components/CalendarView';
import { ConfigView } from './components/ConfigView';
import { SosModal } from './components/SosModal';
import { PomodoroHud } from './components/PomodoroHud';
import { QuickActionModal } from './components/QuickActionModal';
import { MenteViewShell } from './components/MenteViewShell';
import { GlobalSearch } from './components/GlobalSearch';
import { isJarvisShell } from './utils/shell';

export default function App() {
  // Current real-world date using local timezone
  const todayStr = useMemo(() => getLocalDateString(), []);

  // Global retroactive date navigation state
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);

  // Active navigation tab
  const [activeTab, setActiveTab] = useState<TabType>('inicio');

  // Emergency SOS Modal
  const [isSosOpen, setIsSosOpen] = useState<boolean>(false);

  // Quick Action Modal (+)
  const [isQuickActionOpen, setIsQuickActionOpen] = useState<boolean>(false);

  // Global Search Modal (Ctrl+K)
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);

  // Global shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // --- GLOBAL PERSISTENT POMODORO STATE ---
  const [pomodoro, setPomodoro] = useState<PomodoroSessionState>(() => ({
    durationMinutes: 25,
    timeLeftSeconds: 25 * 60,
    targetEndTime: null,
    isRunning: false,
    subjectId: undefined,
    subjectName: undefined,
    activeSound: 'none',
    soundVolume: 0.5
  }));

  // Reload all React state from localStorage after sync.
  // Called both after pullLatestFromServer and on 'jarvis-sync-applied' events
  // fired by jarvisCloud.ts / sync.ts when new data has been written.
  const reloadStateFromStorage = useCallback(() => {
    setHabits(getStoredItem(StorageKeys.HABITS, DEFAULT_HABITS));
    setStudyLogs(getStoredItem(StorageKeys.STUDY_LOGS, []));
    setSimulations(getStoredItem(StorageKeys.SIMULATIONS, []));
    setFlashcards(getStoredItem(StorageKeys.FLASHCARDS, []));
    setSubjects(getStoredItem(StorageKeys.SUBJECTS, DEFAULT_SUBJECTS));
    setWorkouts(getStoredItem(StorageKeys.WORKOUTS, []));
    setWorkoutSplit(getStoredItem(StorageKeys.WORKOUT_SPLIT, DEFAULT_SPLIT));
    setWeightLogs(getStoredItem(StorageKeys.WEIGHT_LOGS, []));
    setBodyPhotos(getStoredItem(StorageKeys.BODY_PHOTOS, []));
    setBooks(getStoredItem(StorageKeys.BOOKS, DEFAULT_BOOKS));
    setReadingLogs(getStoredItem(StorageKeys.READING_LOGS, []));
    setQuotes(getStoredItem(StorageKeys.QUOTES, DEFAULT_QUOTES));
    setSummaries(getStoredItem(StorageKeys.SUMMARIES, []));
    setVices(getStoredItem(StorageKeys.VICES, DEFAULT_VICES));
    setViceLogs(getStoredItem(StorageKeys.VICE_LOGS, []));
    setCognitiveRecords(getStoredItem(StorageKeys.COGNITIVE, []));
    setInfiniteNotes(getStoredItem(StorageKeys.STUDY_NOTES_INFINITE, ''));
    // Reload per-day state for currently selected date
    setHabitLogs(prev => getStoredItem(`${StorageKeys.HABIT_LOGS_PREFIX}${selectedDate}`, {}));
    setWaterMl(getStoredItem(`${StorageKeys.WATER_PREFIX}${selectedDate}`, 0));
    setMentalLog(getStoredItem(`${StorageKeys.MENTAL_PREFIX}${selectedDate}`, {
      date: selectedDate, moodScore: 3, moodTags: ['Neutro'], journalText: '',
      socialStranger: false, socialDeepContact: false, socialListeningScore: 3, socialLearned: ''
    }));
    setVictories(getStoredItem(`${StorageKeys.VICTORIES_PREFIX}${selectedDate}`, []));
    console.log('[App] React state reloaded from localStorage after sync');
  }, [selectedDate]);

  // Initial sync pull from cloud on mount
  useEffect(() => {
    pullLatestFromServer().then((updated) => {
      if (updated) {
        reloadStateFromStorage();
      }
    });
  }, []);

  // Listen for sync events from JarvisCloud (desktop sync panel) and sync.ts
  useEffect(() => {
    const handler = () => reloadStateFromStorage();
    window.addEventListener('jarvis-sync-applied', handler);
    return () => window.removeEventListener('jarvis-sync-applied', handler);
  }, [reloadStateFromStorage]);


  // --- CORE ENTITIES & PERSISTENCE ---

  // 1. API Settings
  const [apiSettings, setApiSettings] = useState<ApiSettings>(() => 
    getStoredItem(StorageKeys.SETTINGS, DEFAULT_API_SETTINGS)
  );

  // 2. Habits
  const [habits, setHabits] = useState<Habit[]>(() => 
    getStoredItem(StorageKeys.HABITS, DEFAULT_HABITS)
  );

  // 3. Habit logs per date
  const habitLogKey = `${StorageKeys.HABIT_LOGS_PREFIX}${selectedDate}`;
  const [habitLogs, setHabitLogs] = useState<HabitLog>(() => 
    getStoredItem(habitLogKey, {})
  );

  // Reload habit logs whenever selectedDate changes
  useEffect(() => {
    setHabitLogs(getStoredItem(`${StorageKeys.HABIT_LOGS_PREFIX}${selectedDate}`, {}));
  }, [selectedDate]);

  // 4. Day Victories (As 3 vitórias inegociáveis do dia)
  const victoriesKey = `${StorageKeys.VICTORIES_PREFIX}${selectedDate}`;
  const [victories, setVictories] = useState<DayVictory[]>(() => 
    getStoredItem(victoriesKey, [
      { id: 'v1', text: 'Concluir bloco principal de estudos', completed: false },
      { id: 'v2', text: 'Treinar com intensidade máxima', completed: false },
      { id: 'v3', text: 'Zero telas após as 22h', completed: false },
    ])
  );

  useEffect(() => {
    setVictories(getStoredItem(`${StorageKeys.VICTORIES_PREFIX}${selectedDate}`, [
      { id: 'v1', text: 'Concluir bloco principal de estudos', completed: false },
      { id: 'v2', text: 'Treinar com intensidade máxima', completed: false },
      { id: 'v3', text: 'Zero telas após as 22h', completed: false },
    ]));
  }, [selectedDate]);

  // 5. Water intake
  const waterKey = `${StorageKeys.WATER_PREFIX}${selectedDate}`;
  const [waterMl, setWaterMl] = useState<number>(() => 
    getStoredItem(waterKey, 0)
  );

  useEffect(() => {
    setWaterMl(getStoredItem(`${StorageKeys.WATER_PREFIX}${selectedDate}`, 0));
  }, [selectedDate]);

  // 6. Subjects & Study logs
  const [subjects, setSubjects] = useState<Subject[]>(() => 
    getStoredItem(StorageKeys.SUBJECTS, DEFAULT_SUBJECTS)
  );

  const [studyLogs, setStudyLogs] = useState<StudyLog[]>(() => 
    getStoredItem(StorageKeys.STUDY_LOGS, [
      { id: 'sl1', date: todayStr, subjectId: 's1', subjectName: 'Matemática & Raciocínio Lógico', minutes: 50, notes: 'Exercícios de combinatória', timestamp: '10:00' },
      { id: 'sl2', date: todayStr, subjectId: 's2', subjectName: 'Algoritmos & Programação', minutes: 45, notes: 'Otimização de tempo e complexidade', timestamp: '14:30' }
    ])
  );

  const [simulations, setSimulations] = useState<ExamSimulation[]>(() => 
    getStoredItem(StorageKeys.SIMULATIONS, [
      { id: 'sim1', date: todayStr, subjectId: 's1', subjectName: 'Matemática & Raciocínio Lógico', correct: 18, wrong: 2, total: 20, accuracy: 90, notes: 'Simulado de fixação', timestamp: '11:00' }
    ])
  );

  const [flashcards, setFlashcards] = useState<Flashcard[]>(() => 
    getStoredItem(StorageKeys.FLASHCARDS, [
      { id: 'fc1', subjectId: 's1', front: 'O que é o Teorema de Bayes?', back: 'P(A|B) = P(B|A)*P(A) / P(B). Permite atualizar a probabilidade de uma hipótese com base em novas evidências.', box: 2, nextReviewDate: todayStr },
      { id: 'fc2', subjectId: 's3', front: 'Qual o princípio estóico da Dicotomia do Controle?', back: 'Algumas coisas estão sob nosso controle (ações, opiniões, desejos); outras não (corpo, bens, reputação). Sofrer pelo incontrolável é irracional.', box: 3, nextReviewDate: todayStr }
    ])
  );

  const [infiniteNotes, setInfiniteNotes] = useState<string>(() => 
    getStoredItem(StorageKeys.STUDY_NOTES_INFINITE, '• Anotações de estudo com rolagem infinita\n• Revise todos os pontos fracos diariamente\n• A consistência vence o talento a longo prazo')
  );

  // 7. Workouts & Split
  const [workouts, setWorkouts] = useState<WorkoutExercise[]>(() => 
    getStoredItem(StorageKeys.WORKOUTS, [
      {
        id: 'w1',
        date: todayStr,
        exerciseName: 'Supino Reto Barra',
        muscleGroup: 'Peito',
        sets: [{ reps: 10, load: 30 }, { reps: 10, load: 30 }, { reps: 8, load: 32 }],
        notes: 'Execução cadenciada com pausa de 1s embaixo',
        totalVolume: 856,
        timestamp: '18:00'
      }
    ])
  );

  const [workoutSplit, setWorkoutSplit] = useState<WorkoutSplitDay[]>(() => 
    getStoredItem(StorageKeys.WORKOUT_SPLIT, DEFAULT_SPLIT)
  );

  const [weightLogs, setWeightLogs] = useState<BodyWeightLog[]>(() => 
    getStoredItem(StorageKeys.WEIGHT_LOGS, [
      { id: 'wl1', date: todayStr, weight: 75.8, calories: 2350, notes: 'Alimentação 100% limpa com 160g de proteína' }
    ])
  );

  // Body photos (Álbum de Evolução do Físico)
  const [bodyPhotos, setBodyPhotos] = useState<BodyPhoto[]>(() => 
    getStoredItem(StorageKeys.BODY_PHOTOS, [])
  );

  // 8. Reading
  const [books, setBooks] = useState<Book[]>(() => 
    getStoredItem(StorageKeys.BOOKS, DEFAULT_BOOKS)
  );

  const [readingLogs, setReadingLogs] = useState<DailyReadingLog[]>(() => 
    getStoredItem(StorageKeys.READING_LOGS, [])
  );

  const [quotes, setQuotes] = useState<BookQuote[]>(() => 
    getStoredItem(StorageKeys.QUOTES, DEFAULT_QUOTES)
  );

  const [summaries, setSummaries] = useState<BookSummary[]>(() => 
    getStoredItem(StorageKeys.SUMMARIES, [
      { id: 'sum1', bookTitle: 'Hábitos Atômicos', chapter: 'A Regra dos 2 Minutos', feynmanExplanation: 'Quando começar um hábito difícil parecer chato, reduza ele para algo que dure menos de 2 minutos. Ex: ao invés de ler 30 páginas, abra o livro e leia 1 página. Vencer a inércia é 90% da vitória.', createdAt: todayStr }
    ])
  );

  // 9. Mental & Diário
  const mentalKey = `${StorageKeys.MENTAL_PREFIX}${selectedDate}`;
  const [mentalLog, setMentalLog] = useState<MentalLog>(() => 
    getStoredItem(mentalKey, {
      date: selectedDate,
      moodScore: 4,
      moodTags: ['Focado', 'Disciplinado'],
      journalText: 'Hoje o foco foi sustentado sem distrações. A clareza mental melhora drasticamente com água e sem dopamina barata.',
      socialStranger: true,
      socialDeepContact: true,
      socialListeningScore: 4,
      socialLearned: 'Conversa honesta sobre prioridades e foco a longo prazo.'
    })
  );

  useEffect(() => {
    setMentalLog(getStoredItem(`${StorageKeys.MENTAL_PREFIX}${selectedDate}`, {
      date: selectedDate,
      moodScore: 3,
      moodTags: ['Neutro'],
      journalText: '',
      socialStranger: false,
      socialDeepContact: false,
      socialListeningScore: 3,
      socialLearned: ''
    }));
  }, [selectedDate]);

  // 10. Anti-Vício
  const [vices, setVices] = useState<ViceItem[]>(() => 
    getStoredItem(StorageKeys.VICES, DEFAULT_VICES)
  );

  const [viceLogs, setViceLogs] = useState<ViceLog[]>(() => 
    getStoredItem(StorageKeys.VICE_LOGS, [
      { id: 'vl1', date: todayStr, time: '16:45', viceId: 'v1', viceName: 'Redes Sociais / Rolagem Infinita (Shorts)', committed: false, freeFeeling: 'Respirei fundo, fechei a aba imediatamente e voltei ao estudo. Vitória limpa.' }
    ])
  );

  // 11. Cognitive records
  const [cognitiveRecords, setCognitiveRecords] = useState<CognitiveRecord[]>(() => 
    getStoredItem(StorageKeys.COGNITIVE, [
      { id: 'cr1', date: todayStr, type: 'dual-n-back', score: 4, timeSeconds: 45, result: 'Nível 4 dominado com 100% de precisão' }
    ])
  );

  // --- AUTOMATIC HABIT INTEGRATIONS ---
  // Auto-complete connected habits based on water/workout/study/reading data.
  // Respects manuallyUnchecked flag: if user explicitly unchecked a connected habit, do NOT re-check it.
  useEffect(() => {
    let updated = false;
    const nextLogs = { ...habitLogs };

    habits.forEach((h) => {
      // Skip if user manually unchecked this habit
      if (nextLogs[h.id]?.manuallyUnchecked) return;

      if (h.connectedTo === 'agua' && waterMl >= (h.targetValue || 3000)) {
        if (!nextLogs[h.id]?.completed) {
          nextLogs[h.id] = { ...nextLogs[h.id], completed: true, currentValue: waterMl };
          updated = true;
        }
      }
      if (h.connectedTo === 'treino') {
        const hasWorkout = workouts.some(w => w.date === selectedDate);
        if (hasWorkout && !nextLogs[h.id]?.completed) {
          nextLogs[h.id] = { ...nextLogs[h.id], completed: true };
          updated = true;
        }
      }
      if (h.connectedTo === 'estudo') {
        const hasStudy = studyLogs.some(s => s.date === selectedDate);
        if (hasStudy && !nextLogs[h.id]?.completed) {
          nextLogs[h.id] = { ...nextLogs[h.id], completed: true };
          updated = true;
        }
      }
      if (h.connectedTo === 'leitura') {
        const pagesToday = readingLogs
          .filter(r => r.date === selectedDate)
          .reduce((acc, r) => acc + r.pagesRead, 0);
        if (pagesToday >= (h.targetValue || 10) && !nextLogs[h.id]?.completed) {
          nextLogs[h.id] = { ...nextLogs[h.id], completed: true, currentValue: pagesToday };
          updated = true;
        }
      }
    });

    if (updated) {
      setHabitLogs(nextLogs);
      setStoredItem(`${StorageKeys.HABIT_LOGS_PREFIX}${selectedDate}`, nextLogs);
    }
  }, [waterMl, workouts, studyLogs, readingLogs, selectedDate, habits]);

  // --- PERSISTENCE HANDLERS ---
  const handleToggleHabit = (habitId: string) => {
    const current = habitLogs[habitId]?.completed || false;
    const willBeCompleted = !current;

    // Check if this habit is auto-connected (will be re-checked by useEffect if data exists)
    const habit = habits.find(h => h.id === habitId);
    const isAutoConnected = !!habit?.connectedTo;

    // When unchecking a connected habit, set manuallyUnchecked so auto-integration respects it.
    // When re-checking, clear the flag so auto-integration can work again.
    const nextLogs: HabitLog = {
      ...habitLogs,
      [habitId]: {
        ...habitLogs[habitId],
        completed: willBeCompleted,
        manuallyUnchecked: isAutoConnected && !willBeCompleted ? true : undefined
      }
    };
    setHabitLogs(nextLogs);
    setStoredItem(`${StorageKeys.HABIT_LOGS_PREFIX}${selectedDate}`, nextLogs);

    // Only update streak on today, and only if the toggle actually sticks
    // (for auto-connected habits being unchecked, the useEffect won't re-check so the toggle sticks)
    if (selectedDate === todayStr) {
      setHabits(prev => {
        const next = prev.map(h => {
          if (h.id === habitId) {
            const newStreak = willBeCompleted ? h.streak + 1 : Math.max(0, h.streak - 1);
            return {
              ...h,
              streak: newStreak,
              bestStreak: Math.max(h.bestStreak, newStreak)
            };
          }
          return h;
        });
        setStoredItem(StorageKeys.HABITS, next);
        return next;
      });
    }
  };

  const handleUpdateHabitValue = (habitId: string, val: number) => {
    const habit = habits.find(h => h.id === habitId);
    const completed = habit?.targetValue ? val >= habit.targetValue : false;
    const nextLogs: HabitLog = {
      ...habitLogs,
      [habitId]: {
        completed,
        currentValue: val
      }
    };
    setHabitLogs(nextLogs);
    setStoredItem(`${StorageKeys.HABIT_LOGS_PREFIX}${selectedDate}`, nextLogs);
  };

  const handleAddHabit = (newHabit: Omit<Habit, 'id' | 'streak' | 'bestStreak'>) => {
    const created: Habit = {
      ...newHabit,
      id: `h_${Date.now()}`,
      createdAt: newHabit.createdAt || selectedDate,
      streak: 0,
      bestStreak: 0
    };
    const next = [...habits, created];
    setHabits(next);
    setStoredItem(StorageKeys.HABITS, next);
  };

  const handleDeleteHabit = (id: string) => {
    const next = habits.filter(h => h.id !== id);
    setHabits(next);
    setStoredItem(StorageKeys.HABITS, next);
  };

  const handleToggleHabitPriority = (id: string) => {
    const next = habits.map(h => h.id === id ? { ...h, isPriority: !h.isPriority } : h);
    setHabits(next);
    setStoredItem(StorageKeys.HABITS, next);
  };

  const handleAddWater = (amount: number) => {
    const next = Math.max(0, waterMl + amount);
    setWaterMl(next);
    setStoredItem(`${StorageKeys.WATER_PREFIX}${selectedDate}`, next);
  };

  const handleUpdateVictories = (newVictories: DayVictory[]) => {
    setVictories(newVictories);
    setStoredItem(`${StorageKeys.VICTORIES_PREFIX}${selectedDate}`, newVictories);
  };

  // Study Handlers
  const handleAddSubject = (name: string) => {
    const created: Subject = {
      id: `s_${Date.now()}`,
      name,
      points: 0,
      totalMinutes: 0
    };
    const next = [...subjects, created];
    setSubjects(next);
    setStoredItem(StorageKeys.SUBJECTS, next);
  };

  const handleUpdateSubjectPoints = (id: string, delta: number) => {
    const next = subjects.map(s => {
      if (s.id === id) {
        return {
          ...s,
          points: Math.max(0, s.points + delta),
          lastStudiedDate: selectedDate
        };
      }
      return s;
    });
    setSubjects(next);
    setStoredItem(StorageKeys.SUBJECTS, next);
  };

  // --- POMODORO GLOBAL CONTROLS & TIMERS ---
  const handleTogglePomodoro = () => {
    if (pomodoro.isRunning) {
      setPomodoro(prev => ({
        ...prev,
        isRunning: false,
        targetEndTime: null
      }));
      stopFocusSound();
    } else {
      const targetEndTime = Date.now() + pomodoro.timeLeftSeconds * 1000;
      setPomodoro(prev => ({
        ...prev,
        isRunning: true,
        targetEndTime
      }));
      if (pomodoro.activeSound !== 'none') {
        playFocusSound(pomodoro.activeSound, pomodoro.soundVolume);
      }
    }
  };

  const handleResetPomodoro = (minutes: number = 25) => {
    setPomodoro(prev => ({
      ...prev,
      durationMinutes: minutes,
      timeLeftSeconds: minutes * 60,
      targetEndTime: null,
      isRunning: false
    }));
    stopFocusSound();
  };

  const handleSelectPomodoroSubject = (id: string, name: string) => {
    setPomodoro(prev => ({
      ...prev,
      subjectId: id,
      subjectName: name
    }));
  };

  const handleChangeSound = (type: FocusSoundType) => {
    setPomodoro(prev => ({
      ...prev,
      activeSound: type
    }));
    if (type === 'none') {
      stopFocusSound();
    } else {
      playFocusSound(type, pomodoro.soundVolume);
    }
  };

  const handleStartQuickPomodoro = (minutes: number, subjectId?: string) => {
    const targetSubject = subjects.find(s => s.id === subjectId) || subjects[0];
    const targetEndTime = Date.now() + minutes * 60 * 1000;
    setPomodoro(prev => ({
      ...prev,
      durationMinutes: minutes,
      timeLeftSeconds: minutes * 60,
      targetEndTime,
      isRunning: true,
      subjectId: targetSubject?.id,
      subjectName: targetSubject?.name
    }));
    if (pomodoro.activeSound !== 'none') {
      playFocusSound(pomodoro.activeSound, pomodoro.soundVolume);
    }
  };

  const handleAppendInfiniteNote = (text: string) => {
    const updated = (infiniteNotes ? infiniteNotes + '\n' : '') + text;
    setInfiniteNotes(updated);
    setStoredItem(StorageKeys.STUDY_NOTES_INFINITE, updated);
  };

  // Timer imune a congelamento e bloqueio de tela
  useEffect(() => {
    let interval: any = null;
    if (pomodoro.isRunning && pomodoro.targetEndTime) {
      interval = setInterval(() => {
        const now = Date.now();
        const remaining = Math.max(0, Math.round((pomodoro.targetEndTime! - now) / 1000));

        if (remaining <= 0) {
          clearInterval(interval);
          setPomodoro(prev => ({
            ...prev,
            timeLeftSeconds: 0,
            isRunning: false,
            targetEndTime: null
          }));
          playChime();
          stopFocusSound();

          // Auto-registro da sessão de foco
          const targetSubject = subjects.find(s => s.id === pomodoro.subjectId) || subjects[0];
          if (targetSubject && pomodoro.durationMinutes >= 5) {
            handleAddStudyLog({
              date: selectedDate,
              subjectId: targetSubject.id,
              subjectName: targetSubject.name,
              minutes: pomodoro.durationMinutes,
              notes: 'Sessão de Foco concluída com sucesso via Pomodoro Global'
            });
          }
        } else {
          setPomodoro(prev => ({ ...prev, timeLeftSeconds: remaining }));
        }
      }, 500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [pomodoro.isRunning, pomodoro.targetEndTime, pomodoro.durationMinutes, pomodoro.subjectId, subjects, selectedDate]);

  const handleAddStudyLog = (log: Omit<StudyLog, 'id' | 'timestamp'>) => {
    const created: StudyLog = {
      ...log,
      id: `sl_${Date.now()}`,
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    };
    const nextLogs = [created, ...studyLogs];
    setStudyLogs(nextLogs);
    setStoredItem(StorageKeys.STUDY_LOGS, nextLogs);

    // Update subject total minutes & points atomically and persist immediately
    setSubjects(prev => {
      const nextSubjects = prev.map(s => {
        if (s.id === log.subjectId) {
          return {
            ...s,
            totalMinutes: s.totalMinutes + log.minutes,
            points: s.points + 1,
            lastStudiedDate: log.date
          };
        }
        return s;
      });
      setStoredItem(StorageKeys.SUBJECTS, nextSubjects);
      return nextSubjects;
    });
  };

  const handleDeleteStudyLog = (id: string) => {
    const next = studyLogs.filter(s => s.id !== id);
    setStudyLogs(next);
    setStoredItem(StorageKeys.STUDY_LOGS, next);
  };

  const handleAddSimulation = (sim: Omit<ExamSimulation, 'id' | 'timestamp'>) => {
    const created: ExamSimulation = {
      ...sim,
      id: `sim_${Date.now()}`,
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    };
    const next = [created, ...simulations];
    setSimulations(next);
    setStoredItem(StorageKeys.SIMULATIONS, next);
  };

  const handleDeleteSimulation = (id: string) => {
    const next = simulations.filter(s => s.id !== id);
    setSimulations(next);
    setStoredItem(StorageKeys.SIMULATIONS, next);
  };

  const handleAddFlashcard = (card: Omit<Flashcard, 'id'>) => {
    const created: Flashcard = {
      ...card,
      id: `fc_${Date.now()}`
    };
    const next = [...flashcards, created];
    setFlashcards(next);
    setStoredItem(StorageKeys.FLASHCARDS, next);
  };

  const handleReviewFlashcard = (id: string, correct: boolean) => {
    const intervalsByBox: Record<number, number> = {
      1: 1,  // 1 dia
      2: 2,  // 2 dias
      3: 4,  // 4 dias
      4: 7,  // 7 dias
      5: 14  // 14 dias
    };

    const next = flashcards.map(fc => {
      if (fc.id === id) {
        const nextBox = correct ? Math.min(5, fc.box + 1) : 1;
        const daysToAdd = intervalsByBox[nextBox] || 1;
        const targetDate = parseLocalDate(selectedDate);
        targetDate.setDate(targetDate.getDate() + daysToAdd);
        const nextReviewDate = getLocalDateString(targetDate);

        return {
          ...fc,
          box: nextBox,
          nextReviewDate
        };
      }
      return fc;
    });

    setFlashcards(next);
    setStoredItem(StorageKeys.FLASHCARDS, next);
  };

  const handleDeleteFlashcard = (id: string) => {
    const next = flashcards.filter(f => f.id !== id);
    setFlashcards(next);
    setStoredItem(StorageKeys.FLASHCARDS, next);
  };

  const handleAddCognitiveRecord = (rec: Omit<CognitiveRecord, 'id'>) => {
    const created: CognitiveRecord = {
      ...rec,
      id: `cr_${Date.now()}`
    };
    const next = [created, ...cognitiveRecords];
    setCognitiveRecords(next);
    setStoredItem(StorageKeys.COGNITIVE, next);
  };

  const handleChangeInfiniteNotes = (notes: string) => {
    setInfiniteNotes(notes);
    setStoredItem(StorageKeys.STUDY_NOTES_INFINITE, notes);
  };

  // Workout Handlers
  const handleAddWorkout = (w: Omit<WorkoutExercise, 'id' | 'timestamp'>) => {
    const created: WorkoutExercise = {
      ...w,
      id: `w_${Date.now()}`,
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    };
    const next = [created, ...workouts];
    setWorkouts(next);
    setStoredItem(StorageKeys.WORKOUTS, next);
  };

  const handleDeleteWorkout = (id: string) => {
    const next = workouts.filter(w => w.id !== id);
    setWorkouts(next);
    setStoredItem(StorageKeys.WORKOUTS, next);
  };

  const handleUpdateSplitDay = (dayOfWeek: number, patch: Partial<WorkoutSplitDay>) => {
    const next = workoutSplit.map(s => s.dayOfWeek === dayOfWeek ? { ...s, ...patch } : s);
    setWorkoutSplit(next);
    setStoredItem(StorageKeys.WORKOUT_SPLIT, next);
  };

  const handleAddWeightLog = (wl: Omit<BodyWeightLog, 'id'>) => {
    const created: BodyWeightLog = { ...wl, id: `wl_${Date.now()}` };
    const next = [created, ...weightLogs];
    setWeightLogs(next);
    setStoredItem(StorageKeys.WEIGHT_LOGS, next);
  };

  const handleDeleteWeightLog = (id: string) => {
    const next = weightLogs.filter(w => w.id !== id);
    setWeightLogs(next);
    setStoredItem(StorageKeys.WEIGHT_LOGS, next);
  };

  const handleAddBodyPhoto = (photo: Omit<BodyPhoto, 'id' | 'timestamp'>) => {
    const newPhoto: BodyPhoto = {
      ...photo,
      id: `photo_${Date.now()}`,
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    };
    setBodyPhotos(prev => {
      const next = [newPhoto, ...prev];
      setStoredItem(StorageKeys.BODY_PHOTOS, next);
      return next;
    });
  };

  const handleDeleteBodyPhoto = (id: string) => {
    setBodyPhotos(prev => {
      const next = prev.filter(p => p.id !== id);
      setStoredItem(StorageKeys.BODY_PHOTOS, next);
      return next;
    });
  };

  // Reading Handlers
  const handleAddBook = (b: Omit<Book, 'id'>) => {
    const created: Book = { ...b, id: `b_${Date.now()}` };
    const next = [...books, created];
    setBooks(next);
    setStoredItem(StorageKeys.BOOKS, next);
  };

  const handleUpdateBookProgress = (id: string, currentPage: number) => {
    const book = books.find(b => b.id === id);
    if (!book) return;

    const previousPage = book.currentPage;
    const p = Math.min(book.totalPages, Math.max(0, currentPage));
    const deltaPages = Math.max(0, p - previousPage);

    const nextBooks = books.map(b => {
      if (b.id === id) {
        return {
          ...b,
          currentPage: p,
          status: (p >= b.totalPages ? 'completed' : 'reading') as any,
          finishDate: p >= b.totalPages ? selectedDate : b.finishDate
        };
      }
      return b;
    });
    setBooks(nextBooks);
    setStoredItem(StorageKeys.BOOKS, nextBooks);

    // Registro da sessão diária de leitura
    if (deltaPages > 0) {
      const newLog: DailyReadingLog = {
        id: `rl_${Date.now()}`,
        date: selectedDate,
        bookId: book.id,
        bookTitle: book.title,
        pagesRead: deltaPages,
        timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
      };
      const nextReadingLogs = [newLog, ...readingLogs];
      setReadingLogs(nextReadingLogs);
      setStoredItem(StorageKeys.READING_LOGS, nextReadingLogs);
    }
  };

  const handleDeleteBook = (id: string) => {
    const next = books.filter(b => b.id !== id);
    setBooks(next);
    setStoredItem(StorageKeys.BOOKS, next);
  };

  const handleAddQuote = (q: Omit<BookQuote, 'id' | 'createdAt'>) => {
    const created: BookQuote = { ...q, id: `q_${Date.now()}`, createdAt: selectedDate };
    const next = [created, ...quotes];
    setQuotes(next);
    setStoredItem(StorageKeys.QUOTES, next);
  };

  const handleDeleteQuote = (id: string) => {
    const next = quotes.filter(q => q.id !== id);
    setQuotes(next);
    setStoredItem(StorageKeys.QUOTES, next);
  };

  const handleAddSummary = (s: Omit<BookSummary, 'id' | 'createdAt'>) => {
    const created: BookSummary = { ...s, id: `sum_${Date.now()}`, createdAt: selectedDate };
    const next = [created, ...summaries];
    setSummaries(next);
    setStoredItem(StorageKeys.SUMMARIES, next);
  };

  const handleDeleteSummary = (id: string) => {
    const next = summaries.filter(s => s.id !== id);
    setSummaries(next);
    setStoredItem(StorageKeys.SUMMARIES, next);
  };

  // Mental Handlers
  const handleSaveMentalLog = (log: MentalLog) => {
    setMentalLog(log);
    setStoredItem(`${StorageKeys.MENTAL_PREFIX}${selectedDate}`, log);
  };

  const handleDeleteMentalLog = (dateToDelete: string) => {
    const key = `${StorageKeys.MENTAL_PREFIX}${dateToDelete}`;
    // Remove via setStoredItem with null so sync layer also removes it
    localStorage.removeItem(key);
    // If deleted date is the currently viewed date, reset in-memory state
    if (dateToDelete === selectedDate) {
      const empty: MentalLog = {
        date: selectedDate,
        moodScore: 3,
        moodTags: [],
        journalText: '',
        socialStranger: false,
        socialDeepContact: false,
        socialListeningScore: 3,
        socialLearned: '',
      };
      setMentalLog(empty);
    }
  };

  // Anti-Vice Handlers
  const handleAddVice = (v: Omit<ViceItem, 'id' | 'streak' | 'longestStreak'>) => {
    const created: ViceItem = { ...v, id: `v_${Date.now()}`, streak: 0, longestStreak: 0 };
    const next = [...vices, created];
    setVices(next);
    setStoredItem(StorageKeys.VICES, next);
  };

  const handleDeleteVice = (id: string) => {
    const next = vices.filter(v => v.id !== id);
    setVices(next);
    setStoredItem(StorageKeys.VICES, next);
  };

  const handleUpdateViceStreak = (id: string, newStreak: number) => {
    const next = vices.map(v => {
      if (v.id === id) {
        return {
          ...v,
          streak: newStreak,
          longestStreak: Math.max(v.longestStreak, newStreak)
        };
      }
      return v;
    });
    setVices(next);
    setStoredItem(StorageKeys.VICES, next);
  };

  const handleUpdateLetter = (id: string, letterToSelf: string) => {
    const next = vices.map(v => v.id === id ? { ...v, letterToSelf } : v);
    setVices(next);
    setStoredItem(StorageKeys.VICES, next);
  };

  const handleAddViceLog = (log: Omit<ViceLog, 'id'>) => {
    const created: ViceLog = { ...log, id: `vl_${Date.now()}` };
    const next = [created, ...viceLogs];
    setViceLogs(next);
    setStoredItem(StorageKeys.VICE_LOGS, next);
  };

  const handleDeleteViceLog = (id: string) => {
    const next = viceLogs.filter(v => v.id !== id);
    setViceLogs(next);
    setStoredItem(StorageKeys.VICE_LOGS, next);
  };

  const handleSaveApiSettings = (settings: ApiSettings) => {
    setApiSettings(settings);
    setStoredItem(StorageKeys.SETTINGS, settings);
  };

  // --- HEATMAP CALCULATION (Last 45 days) using local dates and fresh state ---
  const allDatesHeatmap = useMemo(() => {
    const safeHabits = Array.isArray(habits) ? habits : [];
    const result: { date: string; ratio: number; count: number; total: number }[] = [];
    const base = new Date();

    for (let i = 44; i >= 0; i--) {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i, 12, 0, 0);
      const dStr = getLocalDateString(d);

      // Habits active on this specific date
      const dayActiveHabits = safeHabits.filter(h => !h.createdAt || h.createdAt <= dStr);
      const total = dayActiveHabits.length;

      // Read logs: if selectedDate, use fresh React state habitLogs!
      const dayLogs = dStr === selectedDate 
        ? (habitLogs || {})
        : getStoredItem<HabitLog>(`${StorageKeys.HABIT_LOGS_PREFIX}${dStr}`, {});

      const doneCount = dayActiveHabits.filter(h => dayLogs && dayLogs[h.id]?.completed).length;
      const ratio = total > 0 ? doneCount / total : 0;

      result.push({ date: dStr, ratio, count: doneCount, total });
    }
    return result;
  }, [habits, habitLogs, selectedDate]);

  // --- EVOLUTION HISTORY (For Dynamic Replay, Tooltips & Unified Monochrome Charts) ---
  const evolutionHistory = useMemo((): EvolutionHistoryItem[] => {
    const safeHabits = Array.isArray(habits) ? habits : [];
    const safeStudies = Array.isArray(studyLogs) ? studyLogs : [];
    const safeWorkouts = Array.isArray(workouts) ? workouts : [];
    const safeSims = Array.isArray(simulations) ? simulations : [];
    const safeVices = Array.isArray(viceLogs) ? viceLogs : [];
    const safeWeight = Array.isArray(weightLogs) ? weightLogs : [];
    const safeVictories = Array.isArray(victories) ? victories : [];
    const safeSplit = Array.isArray(workoutSplit) ? workoutSplit : [];

    const base = new Date();
    const list: EvolutionHistoryItem[] = [];
    let cumulativeStudy = 0;
    let cumulativeWorkout = 0;

    for (let i = 29; i >= 0; i--) {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i, 12, 0, 0);
      const dStr = getLocalDateString(d);
      const displayDate = `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')}`;

      const dayStudies = safeStudies.filter(s => s && s.date === dStr);
      const dayWorkouts = safeWorkouts.filter(w => w && w.date === dStr);
      const daySims = safeSims.filter(s => s && s.date === dStr);
      const dayWater = dStr === selectedDate ? waterMl : getStoredItem<number>(`${StorageKeys.WATER_PREFIX}${dStr}`, 0);
      const dayVictoriesRaw = dStr === selectedDate ? safeVictories : getStoredItem<DayVictory[]>(`${StorageKeys.VICTORIES_PREFIX}${dStr}`, []);
      const dayVictories = Array.isArray(dayVictoriesRaw) ? dayVictoriesRaw : [];
      const dayMental = dStr === selectedDate ? mentalLog : getStoredItem<MentalLog | null>(`${StorageKeys.MENTAL_PREFIX}${dStr}`, null);
      const dayVices = safeVices.filter(v => v && v.date === dStr);
      const dayWeight = safeWeight.find(w => w && w.date === dStr);

      const dayActiveHabits = safeHabits.filter(h => !h.createdAt || h.createdAt <= dStr);
      const dayLogs = dStr === selectedDate 
        ? habitLogs 
        : getStoredItem<HabitLog>(`${StorageKeys.HABIT_LOGS_PREFIX}${dStr}`, {});

      const habitsDone = dayActiveHabits.filter(h => dayLogs[h.id]?.completed).length;
      const habitsTotal = dayActiveHabits.length;
      const habitsRate = habitsTotal > 0 ? Math.round((habitsDone / habitsTotal) * 100) : 0;

      const studyDay = dayStudies.reduce((a, c) => a + c.minutes, 0);
      const workoutDay = dayWorkouts.reduce((a, c) => a + c.totalVolume, 0);

      cumulativeStudy += studyDay;
      cumulativeWorkout += workoutDay;

      // Unique lists for rich telemetry tooltip
      const subjectsStudied: string[] = Array.from(new Set<string>(dayStudies.map(s => `${s.subjectName} (${s.minutes}m)`)));
      const exercisesDone: string[] = Array.from(new Set<string>(dayWorkouts.map(w => `${w.exerciseName} (${w.totalVolume}kg)`)));
      const simulationsCount = daySims.length;
      const simulationsAccuracy = simulationsCount > 0 
        ? Math.round(daySims.reduce((a, c) => a + c.accuracy, 0) / simulationsCount) 
        : 0;

      const moodScore = dayMental?.moodScore;
      const moodLabel = dayMental ? ['Crítico', 'Baixo', 'Neutro', 'Focado', 'Pleno'][(dayMental.moodScore || 3) - 1] || 'Neutro' : undefined;
      const moodTags = dayMental?.moodTags;
      const hasJournal = Boolean(dayMental?.journalText && dayMental.journalText.trim().length > 0);
      const journalSnippet = dayMental?.journalText 
        ? (dayMental.journalText.length > 55 ? dayMental.journalText.slice(0, 52) + '...' : dayMental.journalText) 
        : undefined;

      const vicesClean = !dayVices.some(v => v.committed);
      const vicesReported = dayVices.filter(v => v.committed).map(v => v.viceName);

      const victoriesDone = dayVictories.filter(v => v.completed).length;
      const victoriesTotal = dayVictories.length;
      const weightKg = dayWeight?.weight;
      const waterPct = Math.min(100, Math.round((dayWater / 3000) * 100));

      // Weighted Life OS Composite Score (0-100%)
      const habitScore = habitsRate * 0.35;
      const studyScore = Math.min(100, (studyDay / 60) * 100) * 0.25;
      const splitDay = safeSplit.find(s => s && s.dayOfWeek === d.getDay());
      const isRest = splitDay?.isRestDay || false;
      const workoutScore = (workoutDay > 0 || isRest ? 100 : 0) * 0.20;
      const waterScore = Math.min(100, (dayWater / 3000) * 100) * 0.10;
      const mentalScore = (dayMental ? (dayMental.moodScore / 5) * 100 : 50) * 0.10;
      const performanceScore = Math.round(habitScore + studyScore + workoutScore + waterScore + mentalScore);

      list.push({
        date: dStr,
        displayDate,
        studyMins: cumulativeStudy,
        workoutVol: cumulativeWorkout,
        habitsDone,
        habitsTotal,
        dailyStudy: studyDay,
        dailyWorkout: workoutDay,
        habitsRate,
        waterMl: dayWater,
        waterPct,
        performanceScore,
        subjectsStudied,
        exercisesDone,
        simulationsCount,
        simulationsAccuracy,
        moodScore,
        moodLabel,
        moodTags,
        hasJournal,
        journalSnippet,
        vicesClean,
        vicesReported,
        victoriesDone,
        victoriesTotal,
        weightKg
      });
    }
    return list;
  }, [studyLogs, workouts, simulations, habits, habitLogs, selectedDate, waterMl, victories, mentalLog, viceLogs, weightLogs]);

  const activeHabitsToday = useMemo(() => {
    const list = Array.isArray(habits) ? habits : [];
    return list.filter(h => h && (!h.createdAt || h.createdAt <= selectedDate));
  }, [habits, selectedDate]);

  const completedHabitsCount = (Array.isArray(activeHabitsToday) ? activeHabitsToday : []).filter(h => h && habitLogs && habitLogs[h.id]?.completed).length;

  const inJarvis = isJarvisShell();

  return (
    <div className={`${inJarvis ? 'h-full min-h-0 jarvis-shell-embed' : 'min-h-screen'} bg-black text-neutral-100 flex flex-col font-sans selection:bg-white selection:text-black`}>
      {/* Top Navbar */}
      <Navbar
        selectedDate={selectedDate}
        setSelectedDate={setSelectedDate}
        todayStr={todayStr}
        onOpenSos={() => setIsSosOpen(true)}
        onOpenSearch={() => setIsSearchOpen(true)}
        completedHabitsCount={completedHabitsCount}
        totalHabitsCount={activeHabitsToday.length}
        onNavigateTab={setActiveTab}
      />

      {/* Main Content Area */}
      <main className={`flex-1 min-h-0 max-w-5xl w-full mx-auto px-4 md:px-6 pt-6 overflow-y-auto ${inJarvis ? 'pb-4' : 'pb-28'}`}>
        {activeTab === 'inicio' && (
          <DashboardView
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            todayStr={todayStr}
            habits={habits}
            habitLogs={habitLogs}
            onToggleHabit={handleToggleHabit}
            onTogglePriority={handleToggleHabitPriority}
            waterMl={waterMl}
            onAddWater={handleAddWater}
            workouts={workouts}
            studyLogs={studyLogs}
            simulations={simulations}
            victories={victories}
            onUpdateVictories={handleUpdateVictories}
            quotes={quotes}
            apiSettings={apiSettings}
            allDatesHeatmap={allDatesHeatmap}
            evolutionHistory={evolutionHistory}
            mentalLog={mentalLog}
            viceLogs={viceLogs}
            weightLogs={weightLogs}
            onNavigateTab={setActiveTab}
          />
        )}

        {activeTab === 'estudo' && (
          <StudyView
            selectedDate={selectedDate}
            subjects={subjects}
            onAddSubject={handleAddSubject}
            onUpdateSubjectPoints={handleUpdateSubjectPoints}
            studyLogs={studyLogs}
            onAddStudyLog={handleAddStudyLog}
            onDeleteStudyLog={handleDeleteStudyLog}
            simulations={simulations}
            onAddSimulation={handleAddSimulation}
            onDeleteSimulation={handleDeleteSimulation}
            flashcards={flashcards}
            onAddFlashcard={handleAddFlashcard}
            onReviewFlashcard={handleReviewFlashcard}
            onDeleteFlashcard={handleDeleteFlashcard}
            cognitiveRecords={cognitiveRecords}
            onAddCognitiveRecord={handleAddCognitiveRecord}
            infiniteNotes={infiniteNotes}
            onChangeInfiniteNotes={handleChangeInfiniteNotes}
            pomodoro={pomodoro}
            onTogglePomodoro={handleTogglePomodoro}
            onResetPomodoro={handleResetPomodoro}
            onSelectPomodoroSubject={handleSelectPomodoroSubject}
            onChangeSound={handleChangeSound}
          />
        )}

        {activeTab === 'treino' && (
          <WorkoutView
            selectedDate={selectedDate}
            workouts={workouts}
            onAddWorkout={handleAddWorkout}
            onDeleteWorkout={handleDeleteWorkout}
            workoutSplit={workoutSplit}
            onUpdateSplitDay={handleUpdateSplitDay}
            weightLogs={weightLogs}
            onAddWeightLog={handleAddWeightLog}
            onDeleteWeightLog={handleDeleteWeightLog}
            waterMl={waterMl}
            onAddWater={handleAddWater}
            bodyPhotos={bodyPhotos}
            onAddBodyPhoto={handleAddBodyPhoto}
            onDeleteBodyPhoto={handleDeleteBodyPhoto}
          />
        )}

        {(activeTab === 'mente' || ['habitos', 'leitura', 'mental', 'antivicio'].includes(activeTab)) && (
          <MenteViewShell
            defaultSubTab={activeTab === 'mente' ? 'habitos' : activeTab}
            onSetActiveTab={setActiveTab}
          >
            {(subTab) => (
              <>
                {subTab === 'habitos' && (
                  <HabitsView
                    selectedDate={selectedDate}
                    setSelectedDate={setSelectedDate}
                    habits={habits}
                    habitLogs={habitLogs}
                    onToggleHabit={handleToggleHabit}
                    onTogglePriority={handleToggleHabitPriority}
                    onUpdateHabitValue={handleUpdateHabitValue}
                    onAddHabit={handleAddHabit}
                    onDeleteHabit={handleDeleteHabit}
                  />
                )}

                {subTab === 'leitura' && (
                  <ReadingView
                    selectedDate={selectedDate}
                    books={books}
                    onAddBook={handleAddBook}
                    onUpdateBookProgress={handleUpdateBookProgress}
                    onDeleteBook={handleDeleteBook}
                    quotes={quotes}
                    onAddQuote={handleAddQuote}
                    onDeleteQuote={handleDeleteQuote}
                    summaries={summaries}
                    onAddSummary={handleAddSummary}
                    onDeleteSummary={handleDeleteSummary}
                  />
                )}

                {subTab === 'mental' && (
                  <MentalView
                    selectedDate={selectedDate}
                    setSelectedDate={setSelectedDate}
                    todayStr={todayStr}
                    mentalLog={mentalLog}
                    onSaveMentalLog={handleSaveMentalLog}
                    onDeleteMentalLog={handleDeleteMentalLog}
                  />
                )}

                {subTab === 'antivicio' && (
                  <AntiViceView
                    selectedDate={selectedDate}
                    vices={vices}
                    onAddVice={handleAddVice}
                    onDeleteVice={handleDeleteVice}
                    onUpdateViceStreak={handleUpdateViceStreak}
                    onUpdateLetter={handleUpdateLetter}
                    viceLogs={viceLogs}
                    onAddViceLog={handleAddViceLog}
                    onDeleteViceLog={handleDeleteViceLog}
                    onOpenSosModal={() => setIsSosOpen(true)}
                  />
                )}
              </>
            )}
          </MenteViewShell>
        )}

        {activeTab === 'calendario' && (
          <CalendarView
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            todayStr={todayStr}
            habits={habits}
            studyLogs={studyLogs}
            workouts={workouts}
            onNavigateToTab={setActiveTab}
          />
        )}

        {activeTab === 'config' && (
          <ConfigView
            apiSettings={apiSettings}
            onSaveApiSettings={handleSaveApiSettings}
            onReloadApp={() => window.location.reload()}
          />
        )}
      </main>

      {/* Floating Global Pomodoro Mini-Player HUD */}
      <PomodoroHud
        pomodoro={pomodoro}
        onToggleTimer={handleTogglePomodoro}
        onResetTimer={() => handleResetPomodoro(25)}
        onNavigateToStudy={() => setActiveTab('estudo')}
      />

      {/* Persistent Bottom Dock Navigation (4 Pilares + Ação Rápida Central) */}
      <BottomNav 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        onOpenQuickAction={() => setIsQuickActionOpen(true)}
      />

      {/* Quick Action Modal (+) 1 Toque */}
      <QuickActionModal
        isOpen={isQuickActionOpen}
        onClose={() => setIsQuickActionOpen(false)}
        waterMl={waterMl}
        onAddWater={handleAddWater}
        subjects={subjects}
        onStartQuickPomodoro={handleStartQuickPomodoro}
        onAppendNote={handleAppendInfiniteNote}
        onNavigateTab={setActiveTab}
        onOpenSos={() => setIsSosOpen(true)}
      />

      {/* Emergency S.O.S Anti-Relapse Modal */}
      <SosModal
        isOpen={isSosOpen}
        onClose={() => setIsSosOpen(false)}
        vices={vices}
        onVictory={(viceName) => {
          handleAddViceLog({
            date: selectedDate,
            time: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
            viceId: 'sos',
            viceName: viceName || 'Impulso Emergencial',
            committed: false,
            freeFeeling: 'Acionei o protocolo de respiração 4-7-8, reli minha carta e venci o impulso com lucidez.'
          });
        }}
      />

      {/* Global Search Modal (Ctrl+K) */}
      <GlobalSearch
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onNavigate={(tab, date) => {
          setActiveTab(tab);
          if (date) setSelectedDate(date);
        }}
        habits={habits}
        subjects={subjects}
        books={books}
        quotes={quotes}
        workouts={workouts}
        vices={vices}
      />
    </div>
  );
}
