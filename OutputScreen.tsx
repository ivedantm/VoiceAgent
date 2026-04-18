import { motion } from "motion/react";
import { Printer, RotateCcw } from "lucide-react";

interface OutputScreenProps {
  text: string;
  braille: string;
}

export function OutputScreen({ text, braille }: OutputScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-5xl"
      >
        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="text-center mb-12"
        >
          <h2 className="text-4xl" style={{ fontFamily: 'var(--font-display)' }}>
            Translation Complete
          </h2>
        </motion.div>

        {/* Text Output Section */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8"
        >
          <div className="mb-3">
            <h3 className="text-xl opacity-60" style={{ fontFamily: 'var(--font-display)' }}>
              Text
            </h3>
          </div>
          <div className="p-8 rounded-3xl bg-gradient-to-br from-[var(--card)] to-[var(--accent)] border border-[var(--border)]">
            <p className="text-2xl leading-relaxed">{text}</p>
          </div>
        </motion.div>

        {/* Braille Output Section */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mb-12"
        >
          <div className="mb-3">
            <h3 className="text-xl opacity-60" style={{ fontFamily: 'var(--font-display)' }}>
              Braille Output
            </h3>
          </div>
          <div className="p-8 rounded-3xl bg-gradient-to-br from-[var(--card)] to-[var(--accent)] border border-[var(--state-success)]/30">
            <p className="text-5xl leading-relaxed tracking-wider" style={{ fontFamily: 'monospace' }}>
              {braille}
            </p>
          </div>
        </motion.div>

        {/* Action indicators */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="flex items-center justify-center gap-8 mb-6"
        >
          <div className="flex items-center gap-3 px-6 py-4 rounded-2xl bg-[var(--accent)] border border-[var(--state-success)]/30">
            <Printer className="w-6 h-6 text-[var(--state-success)]" strokeWidth={2} />
            <span className="text-xl opacity-80">Print</span>
          </div>

          <div className="flex items-center gap-3 px-6 py-4 rounded-2xl bg-[var(--accent)] border border-[var(--state-idle)]/30">
            <RotateCcw className="w-6 h-6 text-[var(--state-idle)]" strokeWidth={2} />
            <span className="text-xl opacity-80">Restart</span>
          </div>
        </motion.div>

        {/* Instruction */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
          className="text-center text-muted-foreground"
        >
          <p className="text-base">
            Say <span className="text-[var(--state-success)]">print</span> to continue or <span className="text-[var(--state-idle)]">restart</span>
          </p>
        </motion.div>
      </motion.div>
    </div>
  );
}
