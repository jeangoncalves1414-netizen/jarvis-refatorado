import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, Plus, Trash2, Flame, Award, 
  AlertTriangle, CheckCircle, Heart, Clock, FileText 
} from 'lucide-react';
import { ViceItem, ViceLog } from '../types';
import { playChime } from '../utils/sound';

interface AntiViceViewProps {
  selectedDate: string;
  vices: ViceItem[];
  onAddVice: (vice: Omit<ViceItem, 'id' | 'streak' | 'longestStreak'>) => void;
  onDeleteVice: (id: string) => void;
  onUpdateViceStreak: (id: string, newStreak: number) => void;
  onUpdateLetter: (id: string, letter: string) => void;
  viceLogs: ViceLog[];
  onAddViceLog: (log: Omit<ViceLog, 'id'>) => void;
  onDeleteViceLog: (id: string) => void;
  onOpenSosModal: () => void;
}

export const AntiViceView: React.FC<AntiViceViewProps> = ({
  selectedDate,
  vices,
  onAddVice,
  onDeleteVice,
  onUpdateViceStreak,
  onUpdateLetter,
  viceLogs,
  onAddViceLog,
  onDeleteViceLog,
  onOpenSosModal
}) => {
  const [subTab, setSubTab] = useState<'status' | 'auditoria' | 'cartas'>('status');

  // New Vice form
  const [newViceName, setNewViceName] = useState('');
  const [newViceLetter, setNewViceLetter] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Relapse Audit Form
  const [auditViceId, setAuditViceId] = useState(vices[0]?.id || '');
  const [auditTime, setAuditTime] = useState('21:30');
  const [auditCommitted, setAuditCommitted] = useState(true);
  const [auditTrigger, setAuditTrigger] = useState('');
  const [auditPrevention, setAuditPrevention] = useState('');
  const [freeFeeling, setFreeFeeling] = useState('');

  useEffect(() => {
    if (vices.length > 0 && !vices.some(v => v.id === auditViceId)) {
      setAuditViceId(vices[0].id);
    }
  }, [vices, auditViceId]);

  const handleCreateVice = () => {
    if (!newViceName.trim()) return;
    onAddVice({
      name: newViceName.trim(),
      letterToSelf: newViceLetter.trim() || 'Lembre-se do seu compromisso com sua honra e seu futuro.'
    });
    setNewViceName('');
    setNewViceLetter('');
    setShowAddForm(false);
    playChime();
  };

  const handleSaveAudit = () => {
    const selectedVice = vices.find(v => v.id === auditViceId);
    if (!selectedVice) return;

    onAddViceLog({
      date: selectedDate,
      time: auditTime,
      viceId: selectedVice.id,
      viceName: selectedVice.name,
      committed: auditCommitted,
      trigger: auditTrigger,
      preventionPlan: auditPrevention,
      freeFeeling: freeFeeling
    });

    if (auditCommitted) {
      // Relapse occurred: reset streak to 0
      onUpdateViceStreak(selectedVice.id, 0);
    } else {
      // Victory logged!
      onUpdateViceStreak(selectedVice.id, selectedVice.streak + 1);
    }

    setAuditTrigger('');
    setAuditPrevention('');
    setFreeFeeling('');
    playChime();
  };

  return (
    <div className="space-y-6 pb-20">
      {/* HEADER & SOS CALLOUT */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-4">
        <div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-red-500" />
            <span>Blindagem Anti-Vício & Dopamina</span>
          </h2>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Monitoramento de abstinência, auditoria de gatilhos e cartas anti-recaída
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onOpenSosModal}
            className="bg-red-950/80 border border-red-800 hover:border-red-500 text-red-300 px-4 py-1.5 rounded font-mono text-xs font-bold uppercase tracking-wider flex items-center space-x-1.5 transition-all shadow-md animate-pulse"
          >
            <ShieldAlert className="w-4 h-4" />
            <span>S.O.S Emergência</span>
          </button>
        </div>
      </div>

      {/* PROTOCOLO DE URGÊNCIA / SOS ANTI-RECAÍDA */}
      <div className="bg-gradient-to-r from-red-950/40 via-neutral-950 to-neutral-950 border border-red-900/40 rounded p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded bg-red-950/80 border border-red-800 flex items-center justify-center flex-shrink-0">
            <ShieldAlert className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-white flex items-center space-x-2">
              <span>Sentindo Vontade ou Gatilho Agora?</span>
              <span className="bg-red-900/60 text-red-300 text-[9px] px-1.5 py-0.2 rounded uppercase font-normal">Protocolo Ativo</span>
            </span>
            <p className="font-mono text-[11px] text-neutral-400 mt-0.5">
              Não aja no piloto automático. Respire fundo (4-7-8), releia sua carta ao eu do futuro e registre a vitória.
            </p>
          </div>
        </div>

        <button
          onClick={onOpenSosModal}
          className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded font-mono text-xs font-bold uppercase tracking-wider transition-all shadow-lg hover:shadow-red-900/40 flex items-center justify-center space-x-2 cursor-pointer flex-shrink-0"
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Abrir Protocolo S.O.S</span>
        </button>
      </div>

      {/* SUB-TABS */}
      <div className="flex items-center space-x-1 bg-neutral-950 p-1 rounded border border-neutral-800">
        {[
          { id: 'status', label: 'Contadores de Dias Limpos' },
          { id: 'auditoria', label: 'Auditoria de Impulso / Vitória' },
          { id: 'cartas', label: 'Cartas ao Eu do Futuro' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id as any)}
            className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
              subTab === tab.id 
                ? 'bg-white text-black font-bold' 
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 1. ABA: CONTADORES DE DIAS LIMPOS */}
      {subTab === 'status' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="bg-white text-black px-4 py-1.5 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              {showAddForm ? 'Fechar' : '+ Novo Vício a Vencer'}
            </button>
          </div>

          {showAddForm && (
            <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
              <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
                Cadastrar Hábito Compulsivo / Vício
              </h3>
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Nome do Vício</label>
                <input
                  type="text"
                  placeholder="Ex: Rolagem de Shorts, Cigarro, Apostas, Açúcar..."
                  value={newViceName}
                  onChange={(e) => setNewViceName(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                  Carta de Choque (Mensagem para quando você estiver prestes a recair)
                </label>
                <textarea
                  placeholder="Escreva algo duro e lúcido para salvar a si mesmo no futuro..."
                  value={newViceLetter}
                  onChange={(e) => setNewViceLetter(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded p-3 text-xs text-white font-mono h-24 resize-none"
                />
              </div>
              <button
                onClick={handleCreateVice}
                className="w-full bg-white text-black py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
              >
                Ativar Blindagem
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {vices.map((v) => (
              <div key={v.id} className="bg-black border border-neutral-900 p-5 rounded space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="font-mono text-sm font-bold text-white">{v.name}</h4>
                    <span className="text-[11px] font-mono text-neutral-500">
                      Recorde histórico: {v.longestStreak} dias
                    </span>
                  </div>
                  <button
                    onClick={() => onDeleteVice(v.id)}
                    className="text-neutral-700 hover:text-red-400 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="bg-neutral-950 border border-neutral-900 p-4 rounded text-center">
                  <span className="text-[10px] font-mono text-neutral-500 uppercase block mb-1">
                    Dias Limpos Ininterruptos
                  </span>
                  <div className="font-mono text-4xl font-bold text-white flex items-center justify-center space-x-2">
                    <Flame className="w-6 h-6 text-white" />
                    <span>{v.streak}</span>
                    <span className="text-xs text-neutral-500 font-normal">dias</span>
                  </div>
                </div>

                <div className="flex space-x-2">
                  <button
                    onClick={() => {
                      onUpdateViceStreak(v.id, v.streak + 1);
                      playChime();
                    }}
                    className="flex-1 bg-white text-black py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
                  >
                    +1 Dia Vencido
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('Registrar recaída? O contador voltará a 0 dias.')) {
                        onUpdateViceStreak(v.id, 0);
                        setAuditViceId(v.id);
                        setSubTab('auditoria');
                      }
                    }}
                    className="border border-neutral-800 hover:border-red-500 text-neutral-500 hover:text-red-400 px-3 py-2 rounded font-mono text-xs uppercase"
                  >
                    Zerar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. ABA: AUDITORIA DE RECAÍDA / VITÓRIA */}
      {subTab === 'auditoria' && (
        <div className="space-y-6">
          <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
            <h3 className="font-mono text-xs uppercase tracking-wider font-bold text-white">
              Auditar Episódio de Impulso ({selectedDate})
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Hábito / Vício</label>
                <select
                  value={auditViceId}
                  onChange={(e) => setAuditViceId(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  {vices.map(v => (
                    <option key={v.id} value={v.id}>{v.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Horário do Evento</label>
                <input
                  type="time"
                  value={auditTime}
                  onChange={(e) => setAuditTime(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">Desfecho</label>
                <select
                  value={auditCommitted ? 'relapse' : 'victory'}
                  onChange={(e) => setAuditCommitted(e.target.value === 'relapse')}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                >
                  <option value="victory">Vitória (Resisti e Venci a Vontade)</option>
                  <option value="relapse">Recaída (Cedi ao Impulso)</option>
                </select>
              </div>
            </div>

            {auditCommitted ? (
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                    Gatilho Exato (Onde eu estava? O que estava sentindo? O que causou?)
                  </label>
                  <input
                    type="text"
                    placeholder="Ex: Cansaço após o trabalho, celular ao lado da cama..."
                    value={auditTrigger}
                    onChange={(e) => setAuditTrigger(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                    Plano Preventivo Rígido (O que farei para eliminar esse gatilho amanhã?)
                  </label>
                  <input
                    type="text"
                    placeholder="Ex: Deixar o celular carregando fora do quarto a partir das 21h..."
                    value={auditPrevention}
                    onChange={(e) => setAuditPrevention(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                  />
                </div>
              </div>
            ) : (
              <div>
                <label className="text-[10px] font-mono text-neutral-500 block mb-1">
                  Como me sinto por ter sido livre, lúcido e forte hoje?
                </label>
                <input
                  type="text"
                  placeholder="Ex: Sensação de controle total e autodomínio restaurado..."
                  value={freeFeeling}
                  onChange={(e) => setFreeFeeling(e.target.value)}
                  className="w-full bg-black border border-neutral-800 rounded px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            )}

            <button
              onClick={handleSaveAudit}
              className="w-full bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200"
            >
              Registrar Auditoria
            </button>
          </div>

          {/* Histórico de Auditorias */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-mono text-xs text-neutral-500 uppercase tracking-wider">
                Registros de {selectedDate}
              </h4>
              <span className="text-[10px] font-mono text-neutral-500">
                {viceLogs.filter(l => l.date === selectedDate).length} no dia • {viceLogs.length} no total
              </span>
            </div>
            {viceLogs.filter(l => l.date === selectedDate).length === 0 ? (
              <div className="p-4 border border-neutral-900 rounded bg-neutral-950/40 text-center font-mono text-xs text-neutral-500">
                Nenhum registro de auditoria nesta data ({selectedDate}).
              </div>
            ) : (
              viceLogs
                .filter(l => l.date === selectedDate)
                .map(log => (
                  <div key={log.id} className="bg-black border border-neutral-900 p-4 rounded flex items-start justify-between font-mono text-xs">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                          log.committed ? 'bg-red-950 text-red-300 border border-red-900' : 'bg-white text-black'
                        }`}>
                          {log.committed ? 'Recaída' : 'Vitória'}
                        </span>
                        <span className="font-bold text-white">{log.viceName}</span>
                        <span className="text-neutral-500">{log.date} às {log.time}</span>
                      </div>

                      {log.trigger && (
                        <p className="text-neutral-400 text-[11px] mt-1.5">
                          <strong>Gatilho:</strong> {log.trigger}
                        </p>
                      )}
                      {log.preventionPlan && (
                        <p className="text-neutral-300 text-[11px] mt-0.5">
                          <strong>Blindagem:</strong> {log.preventionPlan}
                        </p>
                      )}
                      {log.freeFeeling && (
                        <p className="text-neutral-300 text-[11px] mt-0.5">
                          <strong>Sensação:</strong> "{log.freeFeeling}"
                        </p>
                      )}
                    </div>

                    <button
                      onClick={() => onDeleteViceLog(log.id)}
                      className="text-neutral-700 hover:text-red-400 p-1 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
            )}
          </div>
        </div>
      )}

      {/* 3. ABA: CARTAS AO EU DO FUTURO */}
      {subTab === 'cartas' && (
        <div className="space-y-4">
          <div className="bg-neutral-900/40 border border-neutral-800 p-3 rounded text-xs font-mono text-neutral-400">
            Estas cartas são abertas automaticamente ao acionar o botão de pânico S.O.S. Edite-as para conter a verdade mais dura e libertadora possível.
          </div>

          <div className="space-y-4">
            {vices.map(v => (
              <div key={v.id} className="bg-black border border-neutral-900 p-5 rounded space-y-3">
                <span className="font-mono text-xs font-bold text-white block">
                  Carta Anti-Recaída: {v.name}
                </span>
                <textarea
                  value={v.letterToSelf}
                  onChange={(e) => onUpdateLetter(v.id, e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded p-3 text-xs text-neutral-200 font-mono h-28 resize-none focus:outline-none focus:border-white"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
