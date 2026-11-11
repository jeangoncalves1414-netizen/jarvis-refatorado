export type TabType = 
  | 'inicio' 
  | 'estudo' 
  | 'treino' 
  | 'habitos' 
  | 'leitura' 
  | 'mental' 
  | 'antivicio' 
  | 'calendario' 
  | 'config'
  | 'mente';

export interface DayVictory {
  id: string;
  text: string;
  completed: boolean;
}

export interface Habit {
  id: string;
  title: string;
  type: 'boolean' | 'number';
  targetValue?: number;
  unit?: string; // 'ml', 'L', 'páginas', 'min', 'reps', 'g'
  connectedTo?: 'treino' | 'agua' | 'estudo' | 'leitura';
  createdAt: string;
  streak: number;
  bestStreak: number;
  isPriority?: boolean; // Hábito inegociável (coroa)
}

export interface HabitLog {
  [habitId: string]: {
    completed: boolean;
    currentValue?: number;
    manuallyUnchecked?: boolean; // set when user explicitly unchecks an auto-connected habit
  };
}

export interface Subject {
  id: string;
  name: string;
  points: number; // +1 point for each study
  totalMinutes: number;
  lastStudiedDate?: string;
}

export interface StudyLog {
  id: string;
  date: string;
  subjectId: string;
  subjectName: string;
  minutes: number;
  notes: string;
  timestamp: string;
}

export interface ExamSimulation {
  id: string;
  date: string;
  subjectId: string;
  subjectName: string;
  correct: number;
  wrong: number;
  total: number;
  accuracy: number;
  notes?: string;
  timestamp: string;
}

export interface Flashcard {
  id: string;
  subjectId: string;
  front: string;
  back: string;
  box: number; // Leitner system 1..5
  nextReviewDate: string;
}

export interface ExerciseSet {
  reps: number;
  load: number; // kg
}

export interface WorkoutExercise {
  jarvis_session_id?: string;
  id: string;
  date: string;
  exerciseName: string;
  muscleGroup: string;
  sets: ExerciseSet[];
  notes?: string;
  totalVolume: number; // sum of (reps * load)
  timestamp: string;
}

export interface WorkoutSplitDay {
  dayOfWeek: number; // 0 = Sunday, 1 = Monday, etc.
  dayName: string;
  muscleGroups: string;
  isRestDay: boolean;
}

export interface BodyWeightLog {
  id: string;
  date: string;
  weight: number;
  calories?: number;
  notes?: string;
}

export type PhotoPose = 'frente' | 'costas' | 'lado' | 'livre';

export interface BodyPhoto {
  id: string;
  date: string;
  imageData: string; // base64 data URL (compressed jpeg)
  pose: PhotoPose;
  weight?: number; // kg
  bodyFat?: number; // %
  notes?: string;
  timestamp: string;
}

export interface Book {
  id: string;
  title: string;
  author: string;
  totalPages: number;
  currentPage: number;
  status: 'reading' | 'completed' | 'wishlist';
  startDate?: string;
  finishDate?: string;
}

export interface BookQuote {
  id: string;
  bookTitle: string;
  quote: string;
  page?: number;
  createdAt: string;
}

export interface BookSummary {
  id: string;
  bookTitle: string;
  chapter: string;
  feynmanExplanation: string; // Explaining to a 10 year old
  createdAt: string;
}

export interface MentalLog {
  date: string;
  moodScore: number; // 1 to 5
  moodTags: string[];
  journalText: string;
  socialStranger: boolean;
  socialDeepContact: boolean;
  socialListeningScore: number; // 1 to 5
  socialLearned: string;
}

export interface ViceItem {
  id: string;
  name: string;
  streak: number;
  longestStreak: number;
  letterToSelf: string; // emergency anti-relapse letter
}

export interface ViceLog {
  id: string;
  date: string;
  time: string;
  viceId: string;
  viceName: string;
  committed: boolean;
  trigger?: string;
  preventionPlan?: string;
  freeFeeling?: string;
}

export interface CognitiveRecord {
  id: string;
  date: string;
  type: 'dual-n-back' | 'sudoku' | 'chess';
  score: number;
  timeSeconds: number;
  result: string;
}

export interface ApiSettings {
  oxxyKeys: string[];
  baseUrl: string;
  model: string;
  systemPrompt: string;
  /** URL opcional do Jarvis para sincronização (vazia = mesma origem). */
  syncEndpoint?: string;
  /** Token limitado ao controle remoto; só permanece no dispositivo. */
  syncToken?: string;
  supabaseUrl?: string;
  supabasePublishableKey?: string;
  supabaseAccessToken?: string;
  supabaseRefreshToken?: string;
}

export interface EvolutionHistoryItem {
  date: string;
  displayDate?: string;
  studyMins: number;
  workoutVol: number;
  habitsDone: number;
  habitsTotal: number;
  dailyStudy: number;
  dailyWorkout: number;
  habitsRate: number;
  waterMl: number;
  waterPct: number;
  performanceScore: number;
  subjectsStudied: string[];
  exercisesDone: string[];
  simulationsCount: number;
  simulationsAccuracy: number;
  moodScore?: number;
  moodLabel?: string;
  moodTags?: string[];
  hasJournal?: boolean;
  journalSnippet?: string;
  vicesClean?: boolean;
  vicesReported?: string[];
  victoriesDone?: number;
  victoriesTotal?: number;
  weightKg?: number;
}

export interface PomodoroSessionState {
  durationMinutes: number;
  timeLeftSeconds: number;
  targetEndTime: number | null;
  isRunning: boolean;
  subjectId?: string;
  subjectName?: string;
  activeSound: 'none' | 'white' | 'brown' | 'rain' | 'binaural40hz';
  soundVolume: number;
}

export interface DailyReadingLog {
  id: string;
  date: string;
  bookId: string;
  bookTitle: string;
  pagesRead: number;
  timestamp: string;
}
