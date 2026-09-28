import React, { useState, useMemo, useRef } from 'react';
import { 
  Camera, Image as ImageIcon, ArrowLeftRight, Trash2, Plus, 
  Calendar, Scale, Percent, Filter, ZoomIn, X, Eye
} from 'lucide-react';
import { BodyPhoto, PhotoPose } from '../types';
import { formatDisplayDate } from '../utils/storage';
import { playChime } from '../utils/sound';

interface EvolutionAlbumViewProps {
  photos: BodyPhoto[];
  onAddPhoto: (photo: Omit<BodyPhoto, 'id' | 'timestamp'>) => void;
  onDeletePhoto: (id: string) => void;
  selectedDate: string;
  defaultWeight?: number | null;
}

// Client-side canvas image compressor to maintain localStorage efficiency
function compressImage(file: File, maxWidth = 1080, quality = 0.75): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;

        if (width > maxWidth || height > maxWidth) {
          if (width > height) {
            height = Math.round((height * maxWidth) / width);
            width = maxWidth;
          } else {
            width = Math.round((width * maxWidth) / height);
            height = maxWidth;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          resolve(e.target?.result as string);
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      img.onerror = reject;
      img.src = e.target?.result as string;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const POSE_LABELS: Record<PhotoPose, string> = {
  frente: 'Frente',
  costas: 'Costas',
  lado: 'Lado (Perfil)',
  livre: 'Livre / Outro'
};

export const EvolutionAlbumView: React.FC<EvolutionAlbumViewProps> = ({
  photos,
  onAddPhoto,
  onDeletePhoto,
  selectedDate,
  defaultWeight
}) => {
  const [subTab, setSubTab] = useState<'galeria' | 'comparar' | 'adicionar'>('galeria');
  const [filterPose, setFilterPose] = useState<string>('todas');
  const [selectedPhotoModal, setSelectedPhotoModal] = useState<BodyPhoto | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [cardConfirmDeleteId, setCardConfirmDeleteId] = useState<string | null>(null);

  // Form state
  const [formDate, setFormDate] = useState(selectedDate);
  const [formPose, setFormPose] = useState<PhotoPose>('frente');
  const [formWeight, setFormWeight] = useState<string>(defaultWeight ? String(defaultWeight) : '');
  const [formBodyFat, setFormBodyFat] = useState<string>('');
  const [formNotes, setFormNotes] = useState<string>('');
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [isCompressing, setIsCompressing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Compare state
  const sortedPhotos = useMemo(() => {
    return [...photos].sort((a, b) => b.date.localeCompare(a.date));
  }, [photos]);

  const chronologicalPhotos = useMemo(() => {
    return [...photos].sort((a, b) => a.date.localeCompare(b.date));
  }, [photos]);

  const [compareIdA, setCompareIdA] = useState<string>('');
  const [compareIdB, setCompareIdB] = useState<string>('');

  // Auto-select first and latest for compare if not set
  const photoA = useMemo(() => {
    if (compareIdA) return photos.find(p => p.id === compareIdA) || null;
    return chronologicalPhotos[0] || null;
  }, [photos, compareIdA, chronologicalPhotos]);

  const photoB = useMemo(() => {
    if (compareIdB) return photos.find(p => p.id === compareIdB) || null;
    return sortedPhotos[0] || null;
  }, [photos, compareIdB, sortedPhotos]);

  // Filtered photos for gallery
  const filteredPhotos = useMemo(() => {
    if (filterPose === 'todas') return sortedPhotos;
    return sortedPhotos.filter(p => p.pose === filterPose);
  }, [sortedPhotos, filterPose]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsCompressing(true);
      const base64 = await compressImage(file, 1080, 0.78);
      setPreviewImage(base64);
    } catch (err) {
      alert('Erro ao carregar e comprimir imagem. Tente outro formato (JPG/PNG).');
    } finally {
      setIsCompressing(false);
    }
  };

  const handleSubmit = () => {
    if (!previewImage) {
      alert('Por favor, selecione uma foto.');
      return;
    }

    onAddPhoto({
      date: formDate || selectedDate,
      imageData: previewImage,
      pose: formPose,
      weight: formWeight ? Number(formWeight) : undefined,
      bodyFat: formBodyFat ? Number(formBodyFat) : undefined,
      notes: formNotes.trim() || undefined
    });

    playChime();
    setPreviewImage(null);
    setFormNotes('');
    setFormBodyFat('');
    setSubTab('galeria');
  };

  // Compare delta calculation
  const compareDelta = useMemo(() => {
    if (!photoA || !photoB) return null;
    const dateA = new Date(photoA.date + 'T12:00:00');
    const dateB = new Date(photoB.date + 'T12:00:00');
    const diffDays = Math.round(Math.abs((dateB.getTime() - dateA.getTime()) / (1000 * 60 * 60 * 24)));

    let weightDiff: number | null = null;
    if (photoA.weight !== undefined && photoB.weight !== undefined) {
      weightDiff = Number((photoB.weight - photoA.weight).toFixed(1));
    }

    let bfDiff: number | null = null;
    if (photoA.bodyFat !== undefined && photoB.bodyFat !== undefined) {
      bfDiff = Number((photoB.bodyFat - photoA.bodyFat).toFixed(1));
    }

    return { diffDays, weightDiff, bfDiff };
  }, [photoA, photoB]);

  return (
    <div className="space-y-6">
      {/* SUB-HEADER CONTROLS */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-neutral-950 p-4 border border-neutral-900 rounded">
        <div>
          <div className="flex items-center space-x-2">
            <Camera className="w-4 h-4 text-white" />
            <h3 className="font-mono text-sm font-bold uppercase tracking-wider text-white">
              Álbum de Evolução & Shape
            </h3>
          </div>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Registro visual da sua composição corporal e comparador de transformação física
          </p>
        </div>

        <div className="flex items-center space-x-1.5 bg-black p-1 rounded border border-neutral-800">
          <button
            onClick={() => setSubTab('galeria')}
            className={`px-3 py-1 text-xs font-mono rounded cursor-pointer transition-all flex items-center space-x-1.5 ${
              subTab === 'galeria' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5" />
            <span>Galeria ({photos.length})</span>
          </button>
          <button
            onClick={() => setSubTab('comparar')}
            className={`px-3 py-1 text-xs font-mono rounded cursor-pointer transition-all flex items-center space-x-1.5 ${
              subTab === 'comparar' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
            }`}
          >
            <ArrowLeftRight className="w-3.5 h-3.5" />
            <span>Antes & Depois</span>
          </button>
          <button
            onClick={() => setSubTab('adicionar')}
            className={`px-3 py-1 text-xs font-mono rounded cursor-pointer transition-all flex items-center space-x-1.5 ${
              subTab === 'adicionar' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nova Foto</span>
          </button>
        </div>
      </div>

      {/* ABA: FORMULÁRIO DE NOVA FOTO */}
      {subTab === 'adicionar' && (
        <div className="bg-neutral-950 border border-neutral-900 rounded p-5 sm:p-6 space-y-5 max-w-2xl mx-auto">
          <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
            <h4 className="font-mono text-xs uppercase font-bold tracking-wider text-white flex items-center space-x-2">
              <Camera className="w-4 h-4 text-white" />
              <span>Registrar Nova Foto do Físico</span>
            </h4>
            <span className="text-[10px] font-mono text-neutral-500">Compressão local automática</span>
          </div>

          {/* UPLOAD / DROPZONE */}
          <div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/*"
              className="hidden"
            />
            {previewImage ? (
              <div className="relative group rounded border border-neutral-800 bg-black overflow-hidden flex flex-col items-center">
                <img
                  src={previewImage}
                  alt="Preview"
                  className="max-h-96 w-auto object-contain rounded"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="absolute bottom-3 bg-neutral-900/90 text-white border border-neutral-700 px-3 py-1.5 rounded font-mono text-xs hover:bg-white hover:text-black transition-all cursor-pointer"
                >
                  Trocar Foto
                </button>
              </div>
            ) : (
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-neutral-800 hover:border-neutral-600 rounded p-8 text-center cursor-pointer transition-all bg-black/40 flex flex-col items-center justify-center space-y-2"
              >
                <div className="w-12 h-12 rounded-full bg-neutral-900 flex items-center justify-center border border-neutral-800">
                  <Camera className="w-6 h-6 text-neutral-400" />
                </div>
                <p className="font-mono text-xs text-neutral-300 font-bold">
                  {isCompressing ? 'Comprimindo foto...' : 'Clique para selecionar foto do shape'}
                </p>
                <p className="font-mono text-[11px] text-neutral-500">
                  JPG, PNG ou WEBP. A foto é otimizada e salva localmente no navegador.
                </p>
              </div>
            )}
          </div>

          {/* CAMPOS DO REGISTRO */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-mono text-[11px] text-neutral-400 uppercase tracking-wider mb-1.5">
                Data do Registro
              </label>
              <input
                type="date"
                value={formDate}
                onChange={(e) => setFormDate(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white"
              />
            </div>

            <div>
              <label className="block font-mono text-[11px] text-neutral-400 uppercase tracking-wider mb-1.5">
                Ângulo / Pose
              </label>
              <select
                value={formPose}
                onChange={(e) => setFormPose(e.target.value as PhotoPose)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white"
              >
                <option value="frente">Frente</option>
                <option value="costas">Costas</option>
                <option value="lado">Lado (Perfil)</option>
                <option value="livre">Livre / Outro</option>
              </select>
            </div>

            <div>
              <label className="block font-mono text-[11px] text-neutral-400 uppercase tracking-wider mb-1.5">
                Peso Corporal (kg)
              </label>
              <input
                type="number"
                step="0.1"
                placeholder="Ex: 78.5"
                value={formWeight}
                onChange={(e) => setFormWeight(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white"
              />
            </div>

            <div>
              <label className="block font-mono text-[11px] text-neutral-400 uppercase tracking-wider mb-1.5">
                Gordura Corporal estimado (%) <span className="text-neutral-600 font-normal">opcional</span>
              </label>
              <input
                type="number"
                step="0.1"
                placeholder="Ex: 14.5"
                value={formBodyFat}
                onChange={(e) => setFormBodyFat(e.target.value)}
                className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white"
              />
            </div>
          </div>

          <div>
            <label className="block font-mono text-[11px] text-neutral-400 uppercase tracking-wider mb-1.5">
              Notas & Sensação (opcional)
            </label>
            <textarea
              rows={2}
              placeholder="Ex: Em jejum pós-cardio. Vasodilatação evidente nos braços e abdômen mais aparente."
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white resize-none"
            />
          </div>

          <div className="flex items-center space-x-3 pt-2">
            <button
              onClick={handleSubmit}
              disabled={!previewImage || isCompressing}
              className="flex-1 bg-white text-black py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              Salvar Foto no Álbum
            </button>
            <button
              onClick={() => {
                setPreviewImage(null);
                setSubTab('galeria');
              }}
              className="border border-neutral-800 text-neutral-400 hover:text-white px-4 py-2.5 rounded font-mono text-xs transition-colors cursor-pointer"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* ABA: ANTES & DEPOIS (COMPARADOR) */}
      {subTab === 'comparar' && (
        <div className="space-y-6">
          {photos.length < 2 ? (
            <div className="bg-neutral-950 border border-neutral-900 rounded p-12 text-center font-mono text-xs text-neutral-500 space-y-3">
              <ArrowLeftRight className="w-8 h-8 text-neutral-700 mx-auto" />
              <p className="text-white font-bold">Fotos insuficientes para comparação</p>
              <p>Cadastre pelo menos 2 fotos do shape para ativar o comparador Antes e Depois.</p>
              <button
                onClick={() => setSubTab('adicionar')}
                className="bg-white text-black px-4 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200 transition-colors cursor-pointer inline-block mt-2"
              >
                Cadastrar Foto Agora
              </button>
            </div>
          ) : (
            <>
              {/* SELETORES E METRICAS DE DELTA */}
              <div className="bg-neutral-950 border border-neutral-900 rounded p-4 sm:p-5 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Seletor A (Antes) */}
                  <div className="space-y-1.5">
                    <label className="font-mono text-xs text-neutral-400 uppercase tracking-wider flex items-center space-x-1.5">
                      <span className="w-2 h-2 rounded-full bg-neutral-500 inline-block" />
                      <span>Foto 1 (Marco Inicial / Antes)</span>
                    </label>
                    <select
                      value={photoA?.id || ''}
                      onChange={(e) => setCompareIdA(e.target.value)}
                      className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white"
                    >
                      {chronologicalPhotos.map((p) => (
                        <option key={`a-${p.id}`} value={p.id}>
                          {p.date} — {POSE_LABELS[p.pose]} {p.weight ? `(${p.weight}kg)` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Seletor B (Depois) */}
                  <div className="space-y-1.5">
                    <label className="font-mono text-xs text-neutral-400 uppercase tracking-wider flex items-center space-x-1.5">
                      <span className="w-2 h-2 rounded-full bg-white inline-block" />
                      <span>Foto 2 (Atual / Depois)</span>
                    </label>
                    <select
                      value={photoB?.id || ''}
                      onChange={(e) => setCompareIdB(e.target.value)}
                      className="w-full bg-black border border-neutral-800 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white"
                    >
                      {sortedPhotos.map((p) => (
                        <option key={`b-${p.id}`} value={p.id}>
                          {p.date} — {POSE_LABELS[p.pose]} {p.weight ? `(${p.weight}kg)` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* DELTA BADGES */}
                {compareDelta && (
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-neutral-900 font-mono text-xs">
                    <div className="flex items-center space-x-2">
                      <Calendar className="w-3.5 h-3.5 text-neutral-400" />
                      <span className="text-neutral-400">Tempo decorrido:</span>
                      <strong className="text-white bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800">
                        {compareDelta.diffDays} dias
                      </strong>
                    </div>

                    {compareDelta.weightDiff !== null && (
                      <div className="flex items-center space-x-2">
                        <Scale className="w-3.5 h-3.5 text-neutral-400" />
                        <span className="text-neutral-400">Variação de peso:</span>
                        <strong className={`px-2 py-0.5 rounded border font-bold ${
                          compareDelta.weightDiff <= 0 
                            ? 'bg-neutral-900 border-neutral-700 text-white' 
                            : 'bg-neutral-900 border-neutral-700 text-white'
                        }`}>
                          {compareDelta.weightDiff > 0 ? `+${compareDelta.weightDiff}` : compareDelta.weightDiff} kg
                        </strong>
                      </div>
                    )}

                    {compareDelta.bfDiff !== null && (
                      <div className="flex items-center space-x-2">
                        <Percent className="w-3.5 h-3.5 text-neutral-400" />
                        <span className="text-neutral-400">Variação BF%:</span>
                        <strong className="text-white bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800">
                          {compareDelta.bfDiff > 0 ? `+${compareDelta.bfDiff}` : compareDelta.bfDiff}%
                        </strong>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* LADO A LADO */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Lado A */}
                {photoA && (
                  <div className="bg-neutral-950 border border-neutral-900 rounded overflow-hidden flex flex-col">
                    <div className="bg-neutral-900/60 p-3 flex items-center justify-between border-b border-neutral-900 font-mono text-xs">
                      <div>
                        <span className="text-neutral-400 uppercase text-[10px] tracking-wider block">Marco 1 (Antes)</span>
                        <strong className="text-white">{formatDisplayDate(photoA.date)}</strong> ({photoA.date})
                      </div>
                      <div className="text-right">
                        <span className="bg-black border border-neutral-800 text-neutral-300 px-2 py-0.5 rounded text-[10px]">
                          {POSE_LABELS[photoA.pose]}
                        </span>
                        {photoA.weight && (
                          <span className="text-white font-bold ml-2 text-xs">{photoA.weight} kg</span>
                        )}
                      </div>
                    </div>
                    <div className="bg-black flex items-center justify-center p-2 min-h-[380px]">
                      <img
                        src={photoA.imageData}
                        alt="Foto Antes"
                        className="max-h-[500px] w-auto object-contain rounded"
                      />
                    </div>
                    {photoA.notes && (
                      <div className="p-3 border-t border-neutral-900 font-mono text-xs text-neutral-400 bg-neutral-950/80">
                        "{photoA.notes}"
                      </div>
                    )}
                  </div>
                )}

                {/* Lado B */}
                {photoB && (
                  <div className="bg-neutral-950 border border-neutral-900 rounded overflow-hidden flex flex-col">
                    <div className="bg-neutral-900/60 p-3 flex items-center justify-between border-b border-neutral-900 font-mono text-xs">
                      <div>
                        <span className="text-neutral-400 uppercase text-[10px] tracking-wider block">Marco 2 (Depois)</span>
                        <strong className="text-white">{formatDisplayDate(photoB.date)}</strong> ({photoB.date})
                      </div>
                      <div className="text-right">
                        <span className="bg-white text-black px-2 py-0.5 rounded text-[10px] font-bold">
                          {POSE_LABELS[photoB.pose]}
                        </span>
                        {photoB.weight && (
                          <span className="text-white font-bold ml-2 text-xs">{photoB.weight} kg</span>
                        )}
                      </div>
                    </div>
                    <div className="bg-black flex items-center justify-center p-2 min-h-[380px]">
                      <img
                        src={photoB.imageData}
                        alt="Foto Depois"
                        className="max-h-[500px] w-auto object-contain rounded"
                      />
                    </div>
                    {photoB.notes && (
                      <div className="p-3 border-t border-neutral-900 font-mono text-xs text-neutral-400 bg-neutral-950/80">
                        "{photoB.notes}"
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* ABA: GALERIA COMPLETA */}
      {subTab === 'galeria' && (
        <div className="space-y-4">
          {/* BARRA DE FILTROS */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-neutral-950 border border-neutral-900 p-3 rounded font-mono text-xs">
            <div className="flex items-center space-x-2">
              <Filter className="w-3.5 h-3.5 text-neutral-400" />
              <span className="text-neutral-400">Filtrar por Pose:</span>
              <div className="flex items-center space-x-1">
                {[
                  { id: 'todas', label: 'Todas' },
                  { id: 'frente', label: 'Frente' },
                  { id: 'costas', label: 'Costas' },
                  { id: 'lado', label: 'Lado' },
                  { id: 'livre', label: 'Livre' },
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFilterPose(f.id)}
                    className={`px-2.5 py-1 rounded text-[10px] cursor-pointer transition-all ${
                      filterPose === f.id
                        ? 'bg-white text-black font-bold'
                        : 'text-neutral-400 hover:text-white bg-black border border-neutral-800'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            <span className="text-neutral-500 text-[11px]">
              {filteredPhotos.length} {filteredPhotos.length === 1 ? 'registro' : 'registros'}
            </span>
          </div>

          {/* GRID DE FOTOS */}
          {filteredPhotos.length === 0 ? (
            <div className="bg-neutral-950 border border-neutral-900 rounded p-12 text-center font-mono text-xs text-neutral-500 space-y-3">
              <Camera className="w-8 h-8 text-neutral-700 mx-auto" />
              <p className="text-white font-bold">Nenhuma foto encontrada no álbum</p>
              <p>Adicione fotos periodicamente para acompanhar visualmente sua perda de gordura e hipertrofia.</p>
              <button
                onClick={() => setSubTab('adicionar')}
                className="bg-white text-black px-4 py-2 rounded font-mono text-xs font-bold uppercase hover:bg-neutral-200 transition-colors cursor-pointer inline-block mt-2"
              >
                + Adicionar Primeira Foto
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {filteredPhotos.map((photo) => (
                <div
                  key={photo.id}
                  onClick={() => setSelectedPhotoModal(photo)}
                  className="group bg-neutral-950 border border-neutral-900 hover:border-neutral-700 rounded overflow-hidden cursor-pointer transition-all flex flex-col relative"
                >
                  <div className="aspect-[3/4] bg-black overflow-hidden relative">
                    <img
                      src={photo.imageData}
                      alt={`Shape ${photo.date}`}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <div className="bg-white text-black p-2 rounded-full shadow-lg">
                        <Eye className="w-4 h-4" />
                      </div>
                    </div>

                    <div className="absolute top-2 left-2 bg-black/70 backdrop-blur-sm border border-neutral-800 text-white text-[10px] font-mono px-2 py-0.5 rounded">
                      {POSE_LABELS[photo.pose]}
                    </div>

                    {/* Botão de lixeira direto no card */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCardConfirmDeleteId(cardConfirmDeleteId === photo.id ? null : photo.id);
                      }}
                      className="absolute top-2 right-2 bg-black/80 hover:bg-red-950/90 border border-neutral-800 hover:border-red-800 p-1.5 rounded text-neutral-400 hover:text-red-400 transition-colors z-20 cursor-pointer shadow-md"
                      title="Excluir foto"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>

                    {/* Confirmação de exclusão no card */}
                    {cardConfirmDeleteId === photo.id && (
                      <div 
                        className="absolute inset-0 bg-black/95 z-30 p-3 flex flex-col items-center justify-center space-y-2 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Trash2 className="w-6 h-6 text-red-400" />
                        <p className="font-mono text-xs text-white font-bold">Excluir foto?</p>
                        <p className="font-mono text-[10px] text-neutral-400">{photo.date}</p>
                        <div className="flex items-center space-x-2 pt-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeletePhoto(photo.id);
                              setCardConfirmDeleteId(null);
                              if (selectedPhotoModal?.id === photo.id) setSelectedPhotoModal(null);
                              playChime();
                            }}
                            className="bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded text-xs font-mono font-bold cursor-pointer"
                          >
                            Excluir
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setCardConfirmDeleteId(null);
                            }}
                            className="border border-neutral-700 text-neutral-300 hover:text-white px-2.5 py-1 rounded text-xs font-mono cursor-pointer"
                          >
                            Não
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="p-2.5 font-mono text-xs space-y-1">
                    <div className="flex items-center justify-between text-[11px]">
                      <strong className="text-white">{photo.date}</strong>
                      {photo.weight && (
                        <span className="text-neutral-300 font-bold">{photo.weight} kg</span>
                      )}
                    </div>
                    {photo.bodyFat && (
                      <p className="text-[10px] text-neutral-500">BF: {photo.bodyFat}%</p>
                    )}
                    {photo.notes && (
                      <p className="text-[10px] text-neutral-400 line-clamp-1 truncate">
                        {photo.notes}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* MODAL DE ZOOM E DETALHES DA FOTO */}
      {selectedPhotoModal && (
        <div 
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => {
            setSelectedPhotoModal(null);
            setConfirmDeleteId(null);
          }}
        >
          <div 
            className="bg-neutral-950 border border-neutral-800 rounded-lg max-w-2xl w-full overflow-hidden shadow-2xl space-y-4 p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-neutral-900 pb-3 font-mono text-xs">
              <div>
                <strong className="text-white text-sm">
                  {formatDisplayDate(selectedPhotoModal.date)}
                </strong>{' '}
                <span className="text-neutral-500">({selectedPhotoModal.date})</span>
              </div>
              <button
                onClick={() => {
                  setSelectedPhotoModal(null);
                  setConfirmDeleteId(null);
                }}
                className="text-neutral-400 hover:text-white p-1 rounded hover:bg-neutral-900 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-black rounded flex items-center justify-center max-h-[60vh] overflow-hidden border border-neutral-900">
              <img
                src={selectedPhotoModal.imageData}
                alt="Shape Expandido"
                className="max-h-[60vh] w-auto object-contain"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 font-mono text-xs border-t border-neutral-900 pt-3">
              <div className="flex items-center space-x-3">
                <span className="bg-neutral-900 text-neutral-300 px-2.5 py-1 rounded border border-neutral-800 text-[11px]">
                  Pose: <strong className="text-white">{POSE_LABELS[selectedPhotoModal.pose]}</strong>
                </span>
                {selectedPhotoModal.weight && (
                  <span className="bg-neutral-900 text-neutral-300 px-2.5 py-1 rounded border border-neutral-800 text-[11px]">
                    Peso: <strong className="text-white">{selectedPhotoModal.weight} kg</strong>
                  </span>
                )}
                {selectedPhotoModal.bodyFat && (
                  <span className="bg-neutral-900 text-neutral-300 px-2.5 py-1 rounded border border-neutral-800 text-[11px]">
                    BF%: <strong className="text-white">{selectedPhotoModal.bodyFat}%</strong>
                  </span>
                )}
              </div>

              {confirmDeleteId === selectedPhotoModal.id ? (
                <div className="flex items-center space-x-2">
                  <span className="text-red-400 text-xs font-mono">Excluir permanentemente?</span>
                  <button
                    onClick={() => {
                      onDeletePhoto(selectedPhotoModal.id);
                      setConfirmDeleteId(null);
                      setSelectedPhotoModal(null);
                      playChime();
                    }}
                    className="bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded text-xs font-mono font-bold transition-colors cursor-pointer"
                  >
                    Sim, Excluir
                  </button>
                  <button
                    onClick={() => setConfirmDeleteId(null)}
                    className="border border-neutral-700 text-neutral-400 hover:text-white px-2.5 py-1.5 rounded text-xs font-mono transition-colors cursor-pointer"
                  >
                    Cancelar
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmDeleteId(selectedPhotoModal.id)}
                  className="text-neutral-400 hover:text-red-400 hover:bg-red-950/40 border border-transparent hover:border-red-900/60 p-2 rounded transition-colors flex items-center space-x-1.5 cursor-pointer text-xs"
                >
                  <Trash2 className="w-4 h-4 text-neutral-400" />
                  <span>Excluir Foto</span>
                </button>
              )}
            </div>

            {selectedPhotoModal.notes && (
              <div className="bg-neutral-900/50 p-3 rounded border border-neutral-900 font-mono text-xs text-neutral-300">
                <p className="text-[10px] uppercase text-neutral-500 mb-1">Notas do Registro:</p>
                <p>{selectedPhotoModal.notes}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
