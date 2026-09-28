import { 
  Habit, Subject, StudyLog, ExamSimulation, Flashcard, 
  WorkoutExercise, WorkoutSplitDay, BodyWeightLog, Book, 
  BookQuote, BookSummary, MentalLog, ViceItem, ViceLog, 
  CognitiveRecord, ApiSettings, DayVictory 
} from '../types';

// A chave publicável identifica o cliente; acesso aos dados exige login e é
// restrito por RLS. Nenhuma chave administrativa é distribuída no app.
const SUPABASE_PROJECT_URL = 'https://rhfqrgptnpviplxplcbo.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable__dLqOSYJpM5WfGArFbVyYw_OFdak85E';

export const DEFAULT_SPLIT: WorkoutSplitDay[] = [
  { dayOfWeek: 1, dayName: 'Segunda-feira', muscleGroups: 'Peito, Ombros e Tríceps', isRestDay: false },
  { dayOfWeek: 2, dayName: 'Terça-feira', muscleGroups: 'Costas e Bíceps', isRestDay: false },
  { dayOfWeek: 3, dayName: 'Quarta-feira', muscleGroups: 'Pernas e Panturrilhas', isRestDay: false },
  { dayOfWeek: 4, dayName: 'Quinta-feira', muscleGroups: 'Ombros e Abdômen', isRestDay: false },
  { dayOfWeek: 5, dayName: 'Sexta-feira', muscleGroups: 'Braços e Cardio Intenso', isRestDay: false },
  { dayOfWeek: 6, dayName: 'Sábado', muscleGroups: 'Mobilidade e Força Funcional', isRestDay: false },
  { dayOfWeek: 0, dayName: 'Domingo', muscleGroups: 'Descanso Ativo / Recuperação', isRestDay: true },
];

export const DEFAULT_HABITS: Habit[] = [
  { id: 'h1', title: 'Treinar com Sobrecarga', type: 'boolean', connectedTo: 'treino', createdAt: '2026-09-01', streak: 12, bestStreak: 24 },
  { id: 'h2', title: 'Consumo de Água (3000ml)', type: 'number', targetValue: 3000, unit: 'ml', connectedTo: 'agua', createdAt: '2026-09-01', streak: 15, bestStreak: 30 },
  { id: 'h3', title: 'Sessão de Foco / Estudo Profundo', type: 'number', targetValue: 60, unit: 'min', connectedTo: 'estudo', createdAt: '2026-09-01', streak: 9, bestStreak: 18 },
  { id: 'h4', title: 'Leitura Ativa (Páginas)', type: 'number', targetValue: 20, unit: 'páginas', connectedTo: 'leitura', createdAt: '2026-09-01', streak: 8, bestStreak: 14 },
  { id: 'h5', title: 'Treino de Memória / Dual N-Back', type: 'boolean', createdAt: '2026-09-01', streak: 5, bestStreak: 11 },
];

export const DEFAULT_SUBJECTS: Subject[] = [
  { id: 's1', name: 'Matemática & Raciocínio Lógico', points: 14, totalMinutes: 620, lastStudiedDate: '2026-09-12' },
  { id: 's2', name: 'Algoritmos & Programação', points: 18, totalMinutes: 840, lastStudiedDate: '2026-09-13' },
  { id: 's3', name: 'Filosofia Estóica & Neurociência', points: 6, totalMinutes: 240, lastStudiedDate: '2026-09-09' },
  { id: 's4', name: 'Inglês & Vocabulário Avançado', points: 4, totalMinutes: 180, lastStudiedDate: '2026-09-05' },
];

export const DEFAULT_BOOKS: Book[] = [
  { id: 'b1', title: 'Meditações', author: 'Marco Aurélio', totalPages: 220, currentPage: 145, status: 'reading', startDate: '2026-09-01' },
  { id: 'b2', title: 'Hábitos Atômicos', author: 'James Clear', totalPages: 320, currentPage: 320, status: 'completed', startDate: '2026-08-10', finishDate: '2026-08-28' },
];

export const DEFAULT_QUOTES: BookQuote[] = [
  { id: 'q1', bookTitle: 'Meditações', quote: 'Você tem poder sobre a sua mente, não sobre os acontecimentos externos. Perceba isso e você encontrará força.', page: 48, createdAt: '2026-09-02' },
  { id: 'q2', bookTitle: 'Hábitos Atômicos', quote: 'Você não se eleva ao nível de suas metas. Você cai ao nível de seus sistemas.', page: 27, createdAt: '2026-08-15' },
  { id: 'q3', bookTitle: 'Meditações', quote: 'A melhor vingança é não ser como o seu inimigo.', page: 112, createdAt: '2026-09-10' }
];

export const DEFAULT_VICES: ViceItem[] = [
  { 
    id: 'v1', 
    name: 'Redes Sociais / Rolagem Infinita (Shorts)', 
    streak: 14, 
    longestStreak: 28,
    letterToSelf: 'Você não é um zumbi de algoritmos. Cada hora gasta rolando feed destrói sua dopamina, atrasa sua evolução física e intelectual e enriquece terceiros às custas do seu futuro.' 
  },
  { 
    id: 'v2', 
    name: 'Procrastinar Início do Estudo / Treino', 
    streak: 8, 
    longestStreak: 19,
    letterToSelf: 'A dor da disciplina dura minutos; a dor do arrependimento dura a vida inteira. Comece por 5 minutos agora mesmo.' 
  }
];

export const DEFAULT_API_SETTINGS: ApiSettings = {
  oxxyKeys: [],
  baseUrl: 'https://api.openai.com/v1',
  model: 'gpt-4o-mini',
  systemPrompt: 'Você é o Mentor Estóico do Life OS. Responda de forma direta, analítica e sem rodeios. Foque em autodisciplina e melhoria contínua.',
  syncEndpoint: '',
  syncToken: '',
  supabaseUrl: SUPABASE_PROJECT_URL,
  supabasePublishableKey: SUPABASE_PUBLISHABLE_KEY,
};

export const StorageKeys = {
  HABITS: 'lifeos_habits',
  HABIT_LOGS_PREFIX: 'lifeos_hlog_',
  SUBJECTS: 'lifeos_subjects',
  STUDY_LOGS: 'lifeos_study_logs',
  SIMULATIONS: 'lifeos_simulations',
  FLASHCARDS: 'lifeos_flashcards',
  WORKOUTS: 'lifeos_workouts',
  WORKOUT_SPLIT: 'lifeos_workout_split',
  WEIGHT_LOGS: 'lifeos_weight_logs',
  WATER_PREFIX: 'lifeos_water_',
  BOOKS: 'lifeos_books',
  QUOTES: 'lifeos_quotes',
  SUMMARIES: 'lifeos_summaries',
  MENTAL_PREFIX: 'lifeos_mental_',
  VICES: 'lifeos_vices',
  VICE_LOGS: 'lifeos_vice_logs',
  COGNITIVE: 'lifeos_cognitive',
  SETTINGS: 'lifeos_api_settings',
  VICTORIES_PREFIX: 'lifeos_victories_',
  STUDY_NOTES_INFINITE: 'lifeos_infinite_notes',
  READING_LOGS: 'lifeos_reading_logs',
  BODY_PHOTOS: 'lifeos_body_photos'
};

// Keys that must strictly be arrays in localStorage
const ARRAY_STORAGE_KEYS = [
  StorageKeys.HABITS,
  StorageKeys.SUBJECTS,
  StorageKeys.STUDY_LOGS,
  StorageKeys.SIMULATIONS,
  StorageKeys.FLASHCARDS,
  StorageKeys.WORKOUTS,
  StorageKeys.WORKOUT_SPLIT,
  StorageKeys.WEIGHT_LOGS,
  StorageKeys.BOOKS,
  StorageKeys.QUOTES,
  StorageKeys.SUMMARIES,
  StorageKeys.VICES,
  StorageKeys.VICE_LOGS,
  StorageKeys.COGNITIVE,
  StorageKeys.READING_LOGS,
  StorageKeys.BODY_PHOTOS,
];

// Sanitize localStorage: clean up any keys corrupted as plain objects {} instead of arrays []
export function sanitizeStoredData(): void {
  try {
    for (const key of ARRAY_STORAGE_KEYS) {
      const raw = localStorage.getItem(key);
      if (raw === '{}' || raw === 'null') {
        localStorage.removeItem(key);
      } else if (raw) {
        try {
          const parsed = JSON.parse(raw);
          if (typeof parsed === 'object' && !Array.isArray(parsed)) {
            localStorage.removeItem(key);
          }
        } catch {
          localStorage.removeItem(key);
        }
      }
    }
  } catch {
    /* ignore storage errors */
  }
}

// Run immediately on module import
sanitizeStoredData();

// Generic safe getters/setters
export function getStoredItem<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    if (parsed === null || parsed === undefined) return fallback;
    // CRITICAL: If fallback is an array, ensure parsed value is actually an array
    if (Array.isArray(fallback) && !Array.isArray(parsed)) {
      if (typeof parsed === 'object' && Object.keys(parsed).length === 0) {
        return fallback;
      }
      const vals = Object.values(parsed);
      if (vals.length > 0 && typeof vals[0] === 'object') {
        return vals as unknown as T;
      }
      return fallback;
    }
    return parsed;
  } catch {
    return fallback;
  }
}

import { pushToServerDebounced } from './sync';

export function setStoredItem<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    pushToServerDebounced();
  } catch (e) {
    console.error(`Falha ao salvar ${key} no localStorage:`, e);
  }
}

// Canonical date formatting based on local timezone (avoids UTC toISOString displacement)
export function getLocalDateString(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function parseLocalDate(dateStr: string): Date {
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]), 12, 0, 0);
  }
  return new Date();
}

export function formatDisplayDate(dateStr: string, todayStr: string = getLocalDateString()): string {
  if (dateStr === todayStr) return 'Hoje';
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }
  return dateStr;
}

// Retrieve all stored mental logs for history & reflection viewing
export function getAllStoredMentalLogs(): MentalLog[] {
  const list: MentalLog[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(StorageKeys.MENTAL_PREFIX)) {
        const item = getStoredItem<MentalLog | null>(key, null);
        if (item && item.date) {
          list.push(item);
        }
      }
    }
  } catch (e) {
    console.error('Falha ao recuperar logs mentais:', e);
  }
  return list.sort((a, b) => b.date.localeCompare(a.date));
}

// Export all user data as JSON
export function exportAllData(): string {
  const data: Record<string, any> = {};
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith('lifeos_') && key !== StorageKeys.SETTINGS) {
      try {
        data[key] = JSON.parse(localStorage.getItem(key) || 'null');
      } catch {
        data[key] = localStorage.getItem(key);
      }
    }
  }
  return JSON.stringify(data, null, 2);
}

// Import all user data from JSON
export function importAllData(jsonString: string): boolean {
  try {
    const data = JSON.parse(jsonString);
    Object.entries(data).forEach(([key, val]) => {
      if (key.startsWith('lifeos_') && key !== StorageKeys.SETTINGS) {
        localStorage.setItem(key, JSON.stringify(val));
      }
    });
    return true;
  } catch (e) {
    console.error('Falha ao importar dados:', e);
    return false;
  }
}
