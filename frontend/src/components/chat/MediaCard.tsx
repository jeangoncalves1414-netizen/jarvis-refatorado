import React, { useState, useEffect } from 'react'
import { Maximize2, FolderOpen, Image as ImageIcon, Film, X, Check, AlertCircle, Loader2 } from 'lucide-react'

export type MediaViewPayload = {
  type: 'image' | 'video'
  url: string
  path?: string
  title?: string
}

export type MediaCardProps = {
  media: MediaViewPayload
}

export function MediaCard({ media }: MediaCardProps) {
  const [isLightboxOpen, setIsLightboxOpen] = useState(false)
  const [revealStatus, setRevealStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [revealError, setRevealError] = useState<string>('')

  const isVideo = media.type === 'video'
  const displayTitle = media.title || (isVideo ? 'Vídeo Jarvis' : 'Imagem Gerada')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isLightboxOpen) {
        setIsLightboxOpen(false)
      }
    }
    if (isLightboxOpen) {
      window.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isLightboxOpen])

  const handleReveal = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    if (!media.path) return

    setRevealStatus('loading')
    setRevealError('')
    try {
      const res = await fetch('/api/media/reveal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: media.path }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok && data.ok) {
        setRevealStatus('success')
        setTimeout(() => setRevealStatus('idle'), 3000)
      } else {
        setRevealStatus('error')
        setRevealError(data.error || 'Erro ao revelar no Explorer')
        setTimeout(() => setRevealStatus('idle'), 4000)
      }
    } catch {
      setRevealStatus('error')
      setRevealError('Erro de conexão ao servidor')
      setTimeout(() => setRevealStatus('idle'), 4000)
    }
  }

  return (
    <>
      <div className="mc-card">
        {/* Header */}
        <div className="mc-header">
          <div className="mc-header-left">
            <span className="mc-type-icon">
              {isVideo ? <Film size={15} /> : <ImageIcon size={15} />}
            </span>
            <span className="mc-title" title={displayTitle}>
              {displayTitle}
            </span>
          </div>
          <span className="mc-badge">{isVideo ? 'VÍDEO' : 'IMAGEM'}</span>
        </div>

        {/* Media Preview Area */}
        <div className="mc-preview-area">
          {isVideo ? (
            <div className="mc-video-wrapper">
              <video
                src={media.url}
                controls
                preload="metadata"
                playsInline
                className="mc-video-player"
              />
            </div>
          ) : (
            <div
              className="mc-image-wrapper"
              onClick={() => setIsLightboxOpen(true)}
              title="Clique para ver em tela cheia"
            >
              <img
                src={media.url}
                alt={displayTitle}
                className="mc-image-preview"
                loading="lazy"
              />
              <div className="mc-image-overlay">
                <Maximize2 size={18} />
                <span>Ampliar</span>
              </div>
            </div>
          )}
        </div>

        {/* Actions Bar */}
        <div className="mc-footer">
          <button
            type="button"
            className="mc-btn mc-btn-primary"
            onClick={() => setIsLightboxOpen(true)}
            title="Abrir em Tela Cheia"
          >
            <Maximize2 size={13} />
            <span>Ver em Tela Cheia</span>
          </button>

          {media.path && (
            <button
              type="button"
              className={`mc-btn mc-btn-secondary ${revealStatus !== 'idle' ? `is-${revealStatus}` : ''}`}
              onClick={handleReveal}
              disabled={revealStatus === 'loading'}
              title={`Abrir na Pasta: ${media.path}`}
            >
              {revealStatus === 'loading' && <Loader2 size={13} className="mc-spin" />}
              {revealStatus === 'success' && <Check size={13} className="mc-success-icon" />}
              {revealStatus === 'error' && <AlertCircle size={13} className="mc-error-icon" />}
              {revealStatus === 'idle' && <FolderOpen size={13} />}

              <span>
                {revealStatus === 'loading' && 'Abrindo…'}
                {revealStatus === 'success' && 'Pasta Aberta!'}
                {revealStatus === 'error' && (revealError || 'Erro')}
                {revealStatus === 'idle' && 'Local do Arquivo'}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Lightbox Modal */}
      {isLightboxOpen && (
        <div
          className="mc-lightbox-backdrop"
          onClick={() => setIsLightboxOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="mc-lightbox-content" onClick={(e) => e.stopPropagation()}>
            {/* Lightbox Header */}
            <div className="mc-lightbox-header">
              <div className="mc-lightbox-title-wrap">
                <span className="mc-type-icon">
                  {isVideo ? <Film size={17} /> : <ImageIcon size={17} />}
                </span>
                <span className="mc-lightbox-title">{displayTitle}</span>
              </div>

              <div className="mc-lightbox-actions">
                {media.path && (
                  <button
                    type="button"
                    className={`mc-btn mc-btn-secondary ${revealStatus !== 'idle' ? `is-${revealStatus}` : ''}`}
                    onClick={handleReveal}
                    disabled={revealStatus === 'loading'}
                    title={`Abrir na Pasta: ${media.path}`}
                  >
                    {revealStatus === 'loading' && <Loader2 size={13} className="mc-spin" />}
                    {revealStatus === 'success' && <Check size={13} className="mc-success-icon" />}
                    {revealStatus === 'error' && <AlertCircle size={13} className="mc-error-icon" />}
                    {revealStatus === 'idle' && <FolderOpen size={13} />}
                    <span>
                      {revealStatus === 'loading' && 'Abrindo…'}
                      {revealStatus === 'success' && 'Pasta Aberta!'}
                      {revealStatus === 'error' && (revealError || 'Erro')}
                      {revealStatus === 'idle' && 'Abrir na Pasta'}
                    </span>
                  </button>
                )}

                <button
                  type="button"
                  className="mc-lightbox-close-btn"
                  onClick={() => setIsLightboxOpen(false)}
                  title="Fechar (Esc)"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Lightbox Media Body */}
            <div className="mc-lightbox-body">
              {isVideo ? (
                <video
                  src={media.url}
                  controls
                  autoPlay
                  playsInline
                  className="mc-lightbox-video"
                />
              ) : (
                <img
                  src={media.url}
                  alt={displayTitle}
                  className="mc-lightbox-image"
                />
              )}
            </div>

            {/* Lightbox Footer info if path available */}
            {media.path && (
              <div className="mc-lightbox-footer">
                <span className="mc-lightbox-path">{media.path}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
