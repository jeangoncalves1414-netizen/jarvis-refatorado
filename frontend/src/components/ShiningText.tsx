import React from 'react'

interface ShiningTextProps {
  text: string
  className?: string
}

export function ShiningText({ text, className = '' }: ShiningTextProps) {
  return (
    <span className={`shining-text ${className}`}>
      {text}
    </span>
  )
}
