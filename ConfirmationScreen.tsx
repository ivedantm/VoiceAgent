import { motion } from "motion/react";
import { CheckCircle2, RotateCcw } from "lucide-react";

interface ConfirmationScreenProps {
  text: string;
}

export function ConfirmationScreen({ text }: ConfirmationScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-4xl w-full"
      >
        {/* Prompt */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8"
        >
          <h2 className="text-4xl mb-4" style={{ fontFamily: 'var(--font-display)' }}>
            Did you say:
          </h2>
        </motion.div>

        {/* Captured text display */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="mb-12 p-10 rounded-3xl bg-gradient-to-br from-[var(--card)] to-[var(--accent)] border border-[var(--border)]"
        >
          <p className="text-3xl leading-relaxed">{text}</p>
        </motion.div>

        {/* Options visual indicators */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="flex items-center justify-center gap-12 mb-8"
        >
          <div className="flex items-center gap-3 px-6 py-4 rounded-2xl bg-[var(--accent)] border border-[var(--state-success)]/30">
            <CheckCircle2 className="w-6 h-6 text-[var(--state-success)]" strokeWidth={2} />
            <span className="text-xl opacity-80">Confirm</span>
          </div>

          <div className="flex items-center gap-3 px-6 py-4 rounded-2xl bg-[var(--accent)] border border-[var(--state-idle)]/30">
            <RotateCcw className="w-6 h-6 text-[var(--state-idle)]" strokeWidth={2} />
            <span className="text-xl opacity-80">Retry</span>
          </div>
        </motion.div>

        {/* Instruction */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-muted-foreground"
        >
          <p className="text-base">Say <span className="text-[var(--state-success)]">confirm</span> or <span className="text-[var(--state-idle)]">retry</span></p>
        </motion.div>
      </motion.div>
    </div>
  );
}
