import React, { useRef } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'

export type DockItemData = {
  id: string
  label: string
  icon: string
  onClick: () => void
  active?: boolean
  badge?: string
}

export function AnimatedDock({
  items,
}: {
  items: DockItemData[]
}) {
  const mouseX = useMotionValue(Infinity)

  return (
    <motion.div
      onMouseMove={(e) => mouseX.set(e.pageX)}
      onMouseLeave={() => mouseX.set(Infinity)}
      className="animated-dock-container"
    >
      <div className="animated-dock-bar">
        {items.map((item) => (
          <DockItem key={item.id} mouseX={mouseX} item={item} />
        ))}
      </div>
    </motion.div>
  )
}

interface DockItemProps {
  mouseX: any
  item: DockItemData
}

function DockItem({ mouseX, item }: DockItemProps) {
  const ref = useRef<HTMLButtonElement>(null)

  const distance = useTransform(mouseX, (val: number) => {
    const bounds = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 }
    return val - bounds.x - bounds.width / 2
  })

  const widthSync = useTransform(distance, [-150, 0, 150], [40, 80, 40])
  const width = useSpring(widthSync, {
    mass: 0.1,
    stiffness: 150,
    damping: 12,
  })

  const iconScale = useTransform(width, [40, 80], [1, 1.5])
  const iconSpring = useSpring(iconScale, {
    mass: 0.1,
    stiffness: 150,
    damping: 12,
  })

  return (
    <motion.button
      ref={ref}
      style={{ width }}
      type="button"
      className={`dock-item-btn${item.active ? ' is-active' : ''}`}
      onClick={item.onClick}
      title={item.label}
    >
      <motion.div
        style={{ scale: iconSpring }}
        className="dock-item-icon"
      >
        {item.icon}
      </motion.div>
      <span className="dock-item-tooltip">{item.label}</span>
      {item.badge && <span className="dock-item-badge">{item.badge}</span>}
    </motion.button>
  )
}
