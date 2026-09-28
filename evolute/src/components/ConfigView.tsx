import React from 'react';
import { Settings, Download, Upload, Database } from 'lucide-react';
import { ApiSettings } from '../types';
import { exportAllData, importAllData, getLocalDateString } from '../utils/storage';
import { playChime } from '../utils/sound';
import { isJarvisShell } from '../utils/shell';

interface ConfigViewProps {
  apiSettings: ApiSettings;
  onSaveApiSettings: (settings: ApiSettings) => void;
  onReloadApp: () => void;
}

export const ConfigView: React.FC<ConfigViewProps> = ({ onReloadApp }) => {
  const inJarvis = isJarvisShell();

  const handleExportBackup = () => {
    const json = exportAllData();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lifeos_backup_${getLocalDateString()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleImportBackup = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content && importAllData(content)) {
        playChime();
        alert('Dados importados com sucesso! O aplicativo será recarregado.');
        onReloadApp();
      } else {
        alert('Arquivo de backup inválido.');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="space-y-6 pb-20">
      <div className="border-b border-neutral-900 pb-4">
        <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-white flex items-center space-x-2">
          <Settings className="w-4 h-4 text-white" />
          <span>Dados do Life OS</span>
        </h2>
        <p className="text-xs text-neutral-500 font-mono mt-0.5">
          Backup local dos seus hábitos, treinos, estudos e evolução pessoal
        </p>
      </div>

      {inJarvis && (
        <div className="bg-neutral-950 border border-neutral-800 rounded p-4 text-xs font-mono text-neutral-400">
          APIs, nuvem e conexão com o PC ficam em <strong className="text-white">Jarvis → Configurações</strong>.
          Este painel guarda apenas exportação e restauração dos dados do Evolução.
        </div>
      )}

      <div className="bg-neutral-950 border border-neutral-900 rounded p-5 space-y-4">
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-white" />
          <span className="font-mono text-xs uppercase tracking-wider font-bold text-white">
            Persistência & Backup (Offline-First)
          </span>
        </div>
        <p className="text-[11px] text-neutral-500 font-mono">
          Seus registros ficam salvos localmente. Exporte um JSON para backup ou transfira entre dispositivos.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleExportBackup}
            className="flex-1 border border-neutral-800 hover:border-white text-white py-2.5 rounded font-mono text-xs uppercase flex items-center justify-center space-x-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Exportar Dados (JSON)</span>
          </button>

          <label className="flex-1 border border-neutral-800 hover:border-white text-white py-2.5 rounded font-mono text-xs uppercase flex items-center justify-center space-x-2 cursor-pointer transition-colors">
            <Upload className="w-4 h-4" />
            <span>Restaurar Backup</span>
            <input type="file" accept=".json" onChange={handleImportBackup} className="hidden" />
          </label>
        </div>
      </div>
    </div>
  );
};
