import React from 'react'

export interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  label?: string
  description?: string
  id?: string
  glowColor?: 'purple' | 'green' | 'blue'
  className?: string
}

export function Switch({
  checked,
  onChange,
  disabled = false,
  label,
  description,
  id,
  glowColor = 'purple',
  className = '',
}: SwitchProps) {
  const handleClick = () => {
    if (!disabled) {
      onChange(!checked)
    }
  }

  return (
    <div className={`switch-field ${disabled ? 'switch-disabled' : ''} ${className}`}>
      {(label || description) && (
        <div className="switch-text-group" onClick={handleClick}>
          {label && <span className="switch-label">{label}</span>}
          {description && <small className="switch-description">{description}</small>}
        </div>
      )}
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={handleClick}
        className={`switch-track switch-glow-${glowColor} ${checked ? 'is-checked' : 'is-unchecked'}`}
      >
        <span className="switch-thumb" />
      </button>
    </div>
  )
}
