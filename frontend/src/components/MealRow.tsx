import { motion, useMotionValue, useReducedMotion, useTransform } from 'motion/react'
import { CloudUpload, Pencil, Trash2 } from 'lucide-react'
import { fmt, fmtSmart } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { Meal } from '@/lib/types'
import { MacroInline } from '@/ui/MacroBar'

interface Props {
  meal: Meal
  onOpen: (meal: Meal) => void
  onDelete: (meal: Meal) => void
}

const THRESHOLD = 84

/** Fila de comida: toca para ver el detalle, desliza a la izquierda para borrar o a la derecha para editar. */
export function MealRow({ meal, onOpen, onDelete }: Props) {
  const x = useMotionValue(0)
  const reduce = useReducedMotion()
  const deleteOpacity = useTransform(x, [-THRESHOLD, -24, 0], [1, 0.4, 0])
  const editOpacity = useTransform(x, [0, 24, THRESHOLD], [0, 0.4, 1])
  const deleteScale = useTransform(x, [-THRESHOLD * 1.4, -THRESHOLD, 0], [1.15, 1, 0.7])
  const editScale = useTransform(x, [0, THRESHOLD, THRESHOLD * 1.4], [0.7, 1, 1.15])

  return (
    <motion.li
      layout={!reduce}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, marginTop: 0, transition: { duration: 0.22 } }}
      transition={{ type: 'spring', stiffness: 420, damping: 36 }}
      className="relative overflow-hidden rounded-md"
    >
      <div className="absolute inset-0 flex items-center justify-between rounded-md" aria-hidden>
        <motion.div style={{ opacity: editOpacity }} className="flex h-full flex-1 items-center bg-info-soft pl-5">
          <motion.span style={{ scale: editScale }}>
            <Pencil className="size-5 text-info-text" />
          </motion.span>
        </motion.div>
        <motion.div style={{ opacity: deleteOpacity }} className="flex h-full flex-1 items-center justify-end bg-danger-soft pr-5">
          <motion.span style={{ scale: deleteScale }}>
            <Trash2 className="size-5 text-danger-text" />
          </motion.span>
        </motion.div>
      </div>
      <motion.button
        type="button"
        style={{ x }}
        drag={reduce ? false : 'x'}
        dragDirectionLock
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.55}
        dragSnapToOrigin
        onDragEnd={(_, info) => {
          if (info.offset.x < -THRESHOLD) {
            haptic('warning')
            onDelete(meal)
          } else if (info.offset.x > THRESHOLD) {
            haptic('select')
            onOpen(meal)
          }
        }}
        onTap={() => onOpen(meal)}
        onKeyDown={(event) => {
          if (event.key === 'Delete' || event.key === 'Backspace') onDelete(meal)
        }}
        aria-label={`${meal.name}, ${fmt(meal.kcal)} kilocalorías. Abrir detalle`}
        className="relative flex min-h-[60px] w-full items-center gap-3 rounded-md border border-border bg-surface px-3.5 py-2.5 text-left"
      >
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[15px] font-medium text-text">
            <span className="truncate">{meal.name}</span>
            {meal.servings !== 1 && (
              <span className="shrink-0 rounded-full bg-surface-2 px-1.5 py-0.5 text-[11px] font-semibold text-text-2" data-num>
                ×{fmtSmart(meal.servings, 2)}
              </span>
            )}
            {meal.pending && (
              <CloudUpload className="size-3.5 shrink-0 text-warn-text" aria-label="Pendiente de sincronizar" />
            )}
          </p>
          <MacroInline macros={meal} className="mt-1" />
        </div>
        <p className="shrink-0 text-right text-[16px] font-semibold text-text" data-num>
          {fmt(meal.kcal)}
          <span className="ml-1 text-[12px] font-medium text-text-3">kcal</span>
        </p>
      </motion.button>
    </motion.li>
  )
}
