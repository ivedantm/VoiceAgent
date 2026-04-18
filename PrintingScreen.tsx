import { motion } from "motion/react";
import { CheckCircle2 } from "lucide-react";

interface PrintingScreenProps {
  isComplete?: boolean;
}

export function PrintingScreen({ isComplete = false }: PrintingScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="text-center"
      >
        {!isComplete ? (
          <>
            {/* Printing animation - paper with lines */}
            <div className="relative w-64 h-64 mx-auto mb-12">
              {/* Animated paper stack */}
              {[...Array(3)].map((_, i) => (
                <motion.div
                  key={i}
                  initial={{ y: 0, opacity: 0 }}
                  animate={{
                    y: [-20, 100],
                    opacity: [0, 1, 1, 0],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    delay: i * 0.6,
                    ease: "easeInOut",
                  }}
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-56 rounded-2xl bg-gradient-to-br from-[var(--card)] to-[var(--accent)] border border-[var(--border)]"
                >
                  <div className="p-6 space-y-3">
                    {[...Array(5)].map((_, j) => (
                      <div
                        key={j}
                        className="h-2 bg-[var(--state-processing)] rounded-full opacity-40"
                        style={{ width: `${80 - j * 10}%` }}
                      />
                    ))}
                  </div>
                </motion.div>
              ))}

              {/* Glow effect */}
              <motion.div
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.2, 0.4, 0.2],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
                className="absolute inset-0 rounded-full bg-[var(--state-processing)] blur-3xl"
              />
            </div>

            {/* Status text */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <h2 className="text-5xl mb-4" style={{ fontFamily: 'var(--font-display)' }}>
                Printing...
              </h2>
              <p className="text-muted-foreground text-lg">Preparing your Braille document</p>
            </motion.div>
          </>
        ) : (
          <>
            {/* Success state */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", duration: 0.6, bounce: 0.4 }}
              className="relative w-48 h-48 mx-auto mb-12"
            >
              <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1.5, opacity: 0 }}
                transition={{ duration: 1, ease: "easeOut" }}
                className="absolute inset-0 rounded-full bg-[var(--state-success)]"
              />
              <div className="relative w-48 h-48 rounded-full bg-gradient-to-br from-[var(--state-success)] to-[var(--state-idle)] flex items-center justify-center">
                <CheckCircle2 className="w-24 h-24 text-background" strokeWidth={2} />
              </div>
            </motion.div>

            {/* Complete message */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mb-8"
            >
              <h2 className="text-5xl mb-4 text-[var(--state-success)]" style={{ fontFamily: 'var(--font-display)' }}>
                Printing Complete
              </h2>
            </motion.div>

            {/* Instruction */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="text-muted-foreground"
            >
              <p className="text-base">Say <span className="text-[var(--state-idle)]">new note</span> to begin again</p>
            </motion.div>
          </>
        )}
      </motion.div>
    </div>
  );
}
