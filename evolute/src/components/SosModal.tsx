import React, { useState, useEffect } from 'react';
import { ShieldAlert, X, Heart, Clock, ArrowRight, CheckCircle2 } from 'lucide-react';
import { ViceItem } from '../types';
import { playChime } from '../utils/sound';

interface SosModalProps {
  isOpen: boolean;
  onClose: () => void;
  vices: ViceItem[];
  onVictory: (viceName: string) => void;
}

export const SosModal: React.FC<SosModalProps> = ({
  isOpen,
  onClose,
  vices,
  onVictory
}) => {
  // 4-7-8 Breathing Loop: 4s inhale, 7s hold, 8s exhale (Total 19s)
  const [breathPhase, setBreathPhase] = useState<'inspire' | 'segure' | 'expire'>('inspire');
  const [breathCount, setBreathCount] = useState<number>(4);

  // 5-minute Urge Delay Timer
  const [delaySeconds, setDelaySeconds] = useState<number>(300);
  const [selectedViceIndex, setSelectedViceIndex] = useState<number>(0);

  useEffect(() => {
    if (!isOpen) return;

    let timer = setInterval(() => {
      setDelaySeconds(s => (s > 0 ? s - 1 : 0));
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    let cycleSecond = 0;
    setBreathPhase('inspire');
    setBreathCount(4);

    const timer = setInterval(() => {
      cycleSecond = (cycleSecond + 1) % 19;
      if (cycleSecond < 4) {
        setBreathPhase('inspire');
        setBreathCount(4 - cycleSecond);
      } else if (cycleSecond < 11) {
        setBreathPhase('segure');
        setBreathCount(11 - cycleSecond);
      } else {
        setBreathPhase('expire');
        setBreathCount(19 - cycleSecond);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen]);

  if (!isOpen) return null;

  const currentVice = vices[selectedViceIndex] || {
    name: 'Impulso Compulsivo',
    letterToSelf: 'Pare agora. Respire fundo. Este impulso vai passar em menos de 10 minutos. Não troque anos de disciplina por 10 segundos de dopamina barata.'
  };

  const handleLogVictory = () => {
    playChime();
    onVictory(currentVice.name);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/95 backdrop-blur-2xl flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-neutral-950 border border-neutral-800 rounded-lg max-w-2xl w-full p-6 sm:p-8 space-y-6 shadow-2xl my-auto">
        {/* Top bar */}
        <div className="flex items-center justify-between border-b border-neutral-900 pb-4">
          <div className="flex items-center space-x-2 text-red-400">
            <ShieldAlert className="w-5 h-5 animate-pulse" />
            <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white">
              PROTOCOLO DE EMERGÊNCIA S.O.S
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-white p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Breathing Circle */}
        <div className="text-center space-y-3 py-2">
          <div className="relative w-36 h-36 mx-auto flex items-center justify-center">
            <div 
              className={`absolute inset-0 rounded-full border-2 border-white transition-all duration-1000 ${
                breathPhase === 'inspire' ? 'scale-110 bg-white/10' :
                breathPhase === 'segure' ? 'scale-110 bg-white/20 border-dashed' :
                'scale-90 bg-transparent'
              }`}
            />
            <div className="z-10 font-mono">
              <span className="text-xs uppercase tracking-widest text-neutral-400 block mb-1">
                {breathPhase === 'inspire' ? 'Inspire' : breathPhase === 'segure' ? 'Segure' : 'Expire'}
              </span>
              <span className="text-3xl font-bold text-white">{breathCount}s</span>
            </div>
          </div>
          <p className="text-[11px] font-mono text-neutral-500">
            Ciclo Parassimpático 4-7-8 para baixar a frequência cardíaca e cortar a fissura imediata
          </p>
        </div>

        {/* Letter from Past Self */}
        <div className="bg-black border border-neutral-900 p-5 rounded space-y-2">
          <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500">
            <span className="uppercase">Carta do Seu "Eu" Racional para Agora:</span>
            {vices.length > 1 && (
              <select
                value={selectedViceIndex}
                onChange={(e) => setSelectedViceIndex(Number(e.target.value))}
                className="bg-neutral-900 text-white rounded px-2 py-0.5"
              >
                {vices.map((v, i) => (
                  <option key={v.id} value={i}>{v.name}</option>
                ))}
              </select>
            )}
          </div>
          <p className="font-mono text-xs sm:text-sm text-neutral-200 leading-relaxed italic pt-1">
            "{currentVice.letterToSelf}"
          </p>
        </div>

        {/* 5-minute Urge Delay Timer & Victory Button */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-neutral-900">
          <div className="font-mono text-xs text-neutral-400 flex items-center space-x-2">
            <Clock className="w-4 h-4 text-neutral-500" />
            <span>Tempo de Adiamento: </span>
            <strong className="text-white">
              {Math.floor(delaySeconds / 60)}:{(delaySeconds % 60).toString().padStart(2, '0')}
            </strong>
          </div>

          <div className="flex items-center space-x-3 w-full sm:w-auto">
            <button
              onClick={handleLogVictory}
              className="flex-1 sm:flex-none bg-white text-black hover:bg-neutral-200 px-6 py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center space-x-1.5 transition-colors shadow-lg"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Resisti & Venci o Impulso!</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
