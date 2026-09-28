import React, { useState, useEffect, useMemo } from 'react';
import { 
  Brain, Smile, Meh, Frown, Users, MessageSquare, 
  Sparkles, CheckCircle2, Heart, Activity, TrendingUp, Check,
  Trash2, Edit3, Calendar, ShieldAlert
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  Tooltip, CartesianGrid 
} from 'recharts';
import { MentalLog } from '../types';
import { 
  StorageKeys, getStoredItem, setStoredItem, 
  getLocalDateString, parseLocalDate, formatDisplayDate, getAllStoredMentalLogs 
} from '../utils/storage';
import { playChime } from '../utils/sound';

interface MentalViewProps {
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  todayStr?: string;
  mentalLog: MentalLog;
  onSaveMentalLog: (log: MentalLog) => void;
  onDeleteMentalLog?: (date: string) => void;
}

export const MentalView: React.FC<MentalViewProps> = ({
  selectedDate,
  setSelectedDate,
  todayStr = getLocalDateString(),
  mentalLog,
  onSaveMentalLog,
  onDeleteMentalLog
}) => {
  const [moodScore, setMoodScore] = useState<number>(mentalLog.moodScore || 3);
  const [moodTags, setMoodTags] = useState<string[]>(mentalLog.moodTags || []);
  const [journalText, setJournalText] = useState<string>(mentalLog.journalText || '');
  const [socialStranger, setSocialStranger] = useState<boolean>(mentalLog.socialStranger || false);
  const [socialDeepContact, setSocialDeepContact] = useState<boolean>(mentalLog.socialDeepContact || false);
  const [socialListeningScore, setSocialListeningScore] = useState<number>(mentalLog.socialListeningScore || 3);
  const [socialLearned, setSocialLearned] = useState<string>(mentalLog.socialLearned || '');
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [historyList, setHistoryList] = useState<MentalLog[]>(() => getAllStoredMentalLogs());

  // Synchronize local form inputs whenever mentalLog or selectedDate changes
  useEffect(() => {
    setMoodScore(mentalLog.moodScore || 3);
    setMoodTags(mentalLog.moodTags || []);
    setJournalText(mentalLog.journalText || '');
    setSocialStranger(mentalLog.socialStranger || false);
    setSocialDeepContact(mentalLog.socialDeepContact || false);
    setSocialListeningScore(mentalLog.socialListeningScore || 3);
    setSocialLearned(mentalLog.socialLearned || '');
    setHistoryList(getAllStoredMentalLogs());
  }, [mentalLog, selectedDate]);

  const availableTags = ['Calmo', 'Focado', 'Ansioso', 'Disciplinado', 'Cansado', 'Confiante', 'Grato', 'Irritado'];

  const toggleTag = (tag: string) => {
    if (moodTags.includes(tag)) {
      setMoodTags(moodTags.filter(t => t !== tag));
    } else {
      setMoodTags([...moodTags, tag]);
    }
  };

  const handleSave = () => {
    const updatedLog: MentalLog = {
      date: selectedDate,
      moodScore,
      moodTags,
      journalText,
      socialStranger,
      socialDeepContact,
      socialListeningScore,
      socialLearned
    };

    onSaveMentalLog(updatedLog);
    playChime();
    setSaveSuccess(true);
    setHistoryList(getAllStoredMentalLogs());
    setTimeout(() => setSaveSuccess(false), 3500);
  };

  const handleDeleteHistory = (dateToDelete: string) => {
    if (confirm(`Deseja excluir a reflexão do dia ${formatDisplayDate(dateToDelete)}?`)) {
      try {
        localStorage.removeItem(`${StorageKeys.MENTAL_PREFIX}${dateToDelete}`);
        if (onDeleteMentalLog) {
          onDeleteMentalLog(dateToDelete);
        }
        setHistoryList(getAllStoredMentalLogs());
        playChime();
      } catch (e) {
        console.error('Falha ao remover log mental:', e);
      }
    }
  };

  // 14-day Mood Trend calculation using local dates
  const moodHistory = useMemo(() => {
    const base = new Date();
    const list = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i, 12, 0, 0);
      const dStr = getLocalDateString(d);
      const parts = dStr.split('-');
      const displayDate = parts.length === 3 ? `${parts[2]}/${parts[1]}` : dStr;
      
      let score = 3;
      let tags: string[] = [];
      let hasRecord = false;
      let journal = '';

      if (dStr === selectedDate) {
        score = moodScore;
        tags = moodTags;
        journal = journalText;
        hasRecord = true;
      } else {
        const stored = getStoredItem<MentalLog | null>(`${StorageKeys.MENTAL_PREFIX}${dStr}`, null);
        if (stored) {
          score = stored.moodScore || 3;
          tags = stored.moodTags || [];
          journal = stored.journalText || '';
          hasRecord = true;
        }
      }

      list.push({
        date: dStr,
        name: displayDate,
        score,
        hasRecord,
        journalSnippet: journal ? (journal.length > 50 ? journal.slice(0, 48) + '...' : journal) : '',
        tags: tags.join(', ')
      });
    }
    return list;
  }, [selectedDate, moodScore, moodTags, journalText, mentalLog, historyList]);

  const avgMood = (
    moodHistory.reduce((acc, c) => acc + c.score, 0) / (moodHistory.length || 1)
  ).toFixed(1);

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-4">
        <div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
            <Brain className="w-4 h-4 text-white" />
            <span>Saúde Mental, Estoicismo & Socialização</span>
          </h2>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Registro diário de humor, escuta ativa, conexões humanas e diário de autoanálise
          </p>
        </div>

        <div className="flex items-center space-x-2 font-mono text-xs text-neutral-400">
          <span className="bg-neutral-950 border border-neutral-800 px-2.5 py-1 rounded">
            Data Ativa: <strong className="text-white">{formatDisplayDate(selectedDate)}</strong>
          </span>
        </div>
      </div>

      {/* SUCCESS NOTIFICATION BANNER */}
      {saveSuccess && (
        <div className="bg-neutral-950 border border-white text-white p-4 rounded font-mono text-xs flex items-center justify-between animate-fadeIn shadow-xl">
          <div className="flex items-center space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-white" />
            <div>
              <p className="font-bold">Reflexão Gravada com Sucesso no Life OS!</p>
              <p className="text-[11px] text-neutral-400">
                Os dados de {formatDisplayDate(selectedDate)} foram sincronizados em tempo real com o Dashboard e gráficos.
              </p>
            </div>
          </div>
          <span className="text-[10px] uppercase bg-white text-black font-bold px-2 py-0.5 rounded">
            Sincronizado
          </span>
        </div>
      )}

      {/* 1. HUMOR & EMOÇÕES */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs uppercase tracking-wider font-bold text-white">
            Estado de Espírito em {formatDisplayDate(selectedDate)} ({selectedDate})
          </span>
          <span className="font-mono text-xs text-neutral-400">
            Nível: <strong className="text-white">{moodScore} / 5</strong>
          </span>
        </div>

        {/* Escala 1 a 5 */}
        <div className="grid grid-cols-5 gap-2">
          {[
            { score: 1, label: 'Crítico' },
            { score: 2, label: 'Baixo' },
            { score: 3, label: 'Neutro' },
            { score: 4, label: 'Focado' },
            { score: 5, label: 'Pleno' },
          ].map((item) => (
            <button
              key={item.score}
              onClick={() => setMoodScore(item.score)}
              className={`py-3 rounded font-mono text-xs border text-center transition-all ${
                moodScore === item.score
                  ? 'bg-white text-black font-bold border-white shadow-md scale-[1.02]'
                  : 'border-neutral-800 text-neutral-400 hover:border-neutral-600 bg-black'
              }`}
            >
              <div className="text-base font-bold mb-0.5">{item.score}</div>
              <div className="text-[10px] uppercase tracking-wider">{item.label}</div>
            </button>
          ))}
        </div>

        {/* Tags de Emoção */}
        <div>
          <span className="text-[10px] font-mono text-neutral-500 block mb-2 uppercase">
            Identificadores Emocionais
          </span>
          <div className="flex flex-wrap gap-2">
            {availableTags.map((tag) => {
              const active = moodTags.includes(tag);
              return (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={`px-3 py-1 rounded text-xs font-mono border transition-colors ${
                    active 
                      ? 'bg-white text-black font-bold border-white' 
                      : 'border-neutral-800 text-neutral-400 hover:border-neutral-600 bg-black'
                  }`}
                >
                  {tag}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. GRÁFICO DE ESTABILIDADE & EQUILÍBRIO EMOCIONAL (ÁREA ESTILIZADA) */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-neutral-900 pb-2">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-white" />
            <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
              Oscilação & Estabilidade Emocional (Últimos 14 Dias)
            </h3>
          </div>
          <span className="text-[10px] font-mono text-neutral-400">
            Média: <strong className="text-white">{avgMood} / 5</strong>
          </span>
        </div>

        <div className="w-full h-56 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart 
              data={moodHistory} 
              margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
              onClick={(e: any) => {
                if (e && e.activePayload && e.activePayload.length && setSelectedDate) {
                  const clickedDate = e.activePayload[0].payload.date;
                  if (clickedDate) {
                    setSelectedDate(clickedDate);
                    playChime();
                  }
                }
              }}
              style={{ cursor: 'pointer' }}
            >
              <defs>
                <linearGradient id="colorMentalArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ffffff" stopOpacity={0.35}/>
                  <stop offset="95%" stopColor="#ffffff" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
              <XAxis dataKey="name" stroke="#666" fontSize={11} tickLine={false} />
              <YAxis stroke="#666" fontSize={11} tickLine={false} domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} />
              <Tooltip 
                content={({ active, payload }: any) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    const moodLabel = ['Crítico', 'Baixo', 'Neutro', 'Focado', 'Pleno'][data.score - 1] || 'Neutro';
                    const isCurrent = data.date === selectedDate;
                    return (
                      <div className="bg-black/95 border border-neutral-700 p-3 rounded font-mono text-xs shadow-2xl space-y-1.5 z-50 backdrop-blur">
                        <div className="flex items-center justify-between border-b border-neutral-800 pb-1">
                          <span className="text-white font-bold">{formatDisplayDate(data.date)}</span>
                          <span className="text-[10px] text-neutral-500">{data.date}</span>
                        </div>
                        <p className="text-white text-xs">
                          Humor: <strong>{moodLabel} ({data.score}/5)</strong>
                        </p>
                        {data.tags && <p className="text-neutral-400 text-[11px]">{data.tags}</p>}
                        {data.journalSnippet && (
                          <p className="text-neutral-300 text-[10px] italic bg-neutral-950 p-1.5 border border-neutral-800 rounded">
                            "{data.journalSnippet}"
                          </p>
                        )}
                        <p className="text-[10px] text-neutral-400 border-t border-neutral-800 pt-1 text-center font-mono">
                          {isCurrent ? '• Dia aberto no formulário' : '⚡ Clique para abrir este dia'}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area 
                type="monotone" 
                dataKey="score" 
                name="Nível" 
                stroke="#ffffff" 
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorMentalArea)"
                dot={{ r: 3, fill: '#ffffff', strokeWidth: 0 }}
                activeDot={{ r: 6, fill: '#ffffff', stroke: '#000', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. RADAR DE SOCIALIZAÇÃO */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <span className="font-mono text-xs uppercase tracking-wider font-bold text-white flex items-center space-x-2">
          <Users className="w-4 h-4" />
          <span>Radar de Socialização & Conexão Humana</span>
        </span>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Desconhecido */}
          <div 
            onClick={() => setSocialStranger(!socialStranger)}
            className={`p-3.5 border rounded cursor-pointer transition-colors ${
              socialStranger 
                ? 'bg-neutral-900 border-white text-white' 
                : 'bg-black border-neutral-800 text-neutral-400'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold">Conversei com um desconhecido hoje?</span>
              <div className={`w-4 h-4 rounded border flex items-center justify-center ${socialStranger ? 'bg-white text-black' : 'border-neutral-700'}`}>
                {socialStranger && <CheckCircle2 className="w-3.5 h-3.5" />}
              </div>
            </div>
            <p className="text-[10px] font-mono text-neutral-500 mt-1">
              Quebra a timidez, desenvolve carisma e presença social.
            </p>
          </div>

          {/* Conversa Profunda */}
          <div 
            onClick={() => setSocialDeepContact(!socialDeepContact)}
            className={`p-3.5 border rounded cursor-pointer transition-colors ${
              socialDeepContact 
                ? 'bg-neutral-900 border-white text-white' 
                : 'bg-black border-neutral-800 text-neutral-400'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold">Tive conversa profunda com alguém?</span>
              <div className={`w-4 h-4 rounded border flex items-center justify-center ${socialDeepContact ? 'bg-white text-black' : 'border-neutral-700'}`}>
                {socialDeepContact && <CheckCircle2 className="w-3.5 h-3.5" />}
              </div>
            </div>
            <p className="text-[10px] font-mono text-neutral-500 mt-1">
              Fortalece relacionamentos autênticos e vínculos reais.
            </p>
          </div>
        </div>

        {/* Escuta Ativa (1 a 5) */}
        <div>
          <label className="text-[10px] font-mono text-neutral-500 block mb-1">
            Qualidade da Minha Escuta Ativa Hoje (Sem interromper, ouvindo com presença)
          </label>
          <div className="flex items-center space-x-2">
            {[1, 2, 3, 4, 5].map((score) => (
              <button
                key={score}
                onClick={() => setSocialListeningScore(score)}
                className={`flex-1 py-1.5 rounded font-mono text-xs border transition-colors ${
                  socialListeningScore === score 
                    ? 'bg-white text-black font-bold border-white' 
                    : 'border-neutral-800 text-neutral-400 bg-black hover:border-neutral-600'
                }`}
              >
                {score}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-[10px] font-mono text-neutral-500 block mb-1">
            O que aprendi com alguém hoje?
          </label>
          <input
            type="text"
            placeholder="Ex: Aprendi uma lição sobre paciência com um colega..."
            value={socialLearned}
            onChange={(e) => setSocialLearned(e.target.value)}
            className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-white"
          />
        </div>
      </div>

      {/* 4. DIÁRIO REFLEXIVO ESTÓICO */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-3">
        <span className="font-mono text-xs uppercase tracking-wider font-bold text-white flex items-center space-x-2">
          <MessageSquare className="w-4 h-4" />
          <span>Diário Estoico de Autoanálise ({formatDisplayDate(selectedDate)})</span>
        </span>
        <p className="text-[11px] font-mono text-neutral-500">
          O que estava sob meu controle hoje? Em que momento me desviei e como posso agir com mais honra amanhã?
        </p>

        <textarea
          value={journalText}
          onChange={(e) => setJournalText(e.target.value)}
          placeholder="Escreva livremente sem filtros..."
          className="w-full bg-black border border-neutral-800 rounded p-4 text-xs text-neutral-200 font-mono leading-relaxed h-40 resize-none focus:outline-none focus:border-white"
        />

        <button
          onClick={handleSave}
          className={`w-full py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center space-x-2 cursor-pointer ${
            saveSuccess 
              ? 'bg-neutral-900 text-white border border-white' 
              : 'bg-white text-black hover:bg-neutral-200'
          }`}
        >
          {saveSuccess ? (
            <>
              <Check className="w-4 h-4 text-white" />
              <span>Reflexão Salva com Sucesso!</span>
            </>
          ) : (
            <span>Salvar Reflexão do Dia ({formatDisplayDate(selectedDate)})</span>
          )}
        </button>
      </div>

      {/* 5. HISTÓRICO VISUAL DE REFLEXÕES & DIÁRIOS ANTERIORES */}
      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
          <div className="flex items-center space-x-2">
            <Calendar className="w-4 h-4 text-white" />
            <h3 className="font-mono text-xs uppercase font-bold tracking-wider text-white">
              Histórico de Reflexões & Diários Salvos
            </h3>
          </div>
          <span className="text-[11px] font-mono text-neutral-500">
            {historyList.length} registros no cofre mental
          </span>
        </div>

        {historyList.length === 0 ? (
          <div className="p-6 text-center border border-neutral-900 rounded bg-black font-mono text-xs text-neutral-500">
            Nenhuma reflexão anterior gravada ainda. Escreva sua reflexão de hoje e clique em "Salvar Reflexão do Dia".
          </div>
        ) : (
          <div className="space-y-3">
            {historyList.map((item) => {
              const isCurrent = item.date === selectedDate;
              const moodLabel = ['Crítico', 'Baixo', 'Neutro', 'Focado', 'Pleno'][item.moodScore - 1] || 'Neutro';
              return (
                <div
                  key={item.date}
                  className={`border rounded p-4 font-mono text-xs transition-all ${
                    isCurrent 
                      ? 'bg-neutral-900/60 border-white' 
                      : 'bg-black border-neutral-900 hover:border-neutral-700'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-900 pb-2 mb-2.5">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-white text-sm">
                        {formatDisplayDate(item.date)}
                      </span>
                      <span className="text-neutral-500 text-[10px]">({item.date})</span>
                      <span className="px-2 py-0.5 rounded bg-white text-black font-bold text-[10px] uppercase">
                        {moodLabel} ({item.moodScore}/5)
                      </span>
                      {isCurrent && (
                        <span className="text-[10px] text-neutral-400 bg-neutral-800 px-1.5 py-0.5 rounded">
                          Visualizando agora
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => {
                          setSelectedDate(item.date);
                          playChime();
                        }}
                        className="border border-neutral-800 hover:border-white px-2.5 py-1 rounded text-[10px] text-white uppercase flex items-center space-x-1"
                      >
                        <Edit3 className="w-3 h-3" />
                        <span>Abrir / Editar</span>
                      </button>
                      <button
                        onClick={() => handleDeleteHistory(item.date)}
                        className="text-neutral-600 hover:text-red-400 p-1 transition-colors"
                        title="Excluir este registro"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {item.moodTags && item.moodTags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {item.moodTags.map(tag => (
                        <span key={tag} className="text-[10px] bg-neutral-950 border border-neutral-800 text-neutral-300 px-2 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {item.journalText ? (
                    <p className="text-neutral-300 text-xs leading-relaxed whitespace-pre-wrap bg-neutral-950 p-3 rounded border border-neutral-900">
                      {item.journalText}
                    </p>
                  ) : (
                    <p className="text-neutral-600 italic text-[11px]">
                      Nenhum texto de autoanálise inserido neste dia.
                    </p>
                  )}

                  {(item.socialStranger || item.socialDeepContact || item.socialLearned) && (
                    <div className="mt-2 pt-2 border-t border-neutral-900 text-[11px] text-neutral-400 flex flex-wrap gap-x-4 gap-y-1">
                      {item.socialStranger && <span>• Falou com desconhecido</span>}
                      {item.socialDeepContact && <span>• Conversa profunda</span>}
                      <span>• Escuta ativa: {item.socialListeningScore}/5</span>
                      {item.socialLearned && (
                        <span className="w-full text-neutral-300 italic">
                          Aprendizado social: "{item.socialLearned}"
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
