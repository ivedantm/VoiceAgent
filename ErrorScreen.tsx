import { motion } from "motion/react";
import { AlertCircle, Volume2, Clock } from "lucide-react";

interface ErrorScreenProps {
  type: "misheard" | "timeout" | "confusion";
  message: string;
  hint: string;
}

export function ErrorScreen({ type, message, hint }: ErrorScreenProps) {
  const icons = {
    misheard: AlertCircle,
    timeout: Clock,
    confusion: Volume2,
  };

  const Icon = icons[type];

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-2xl"
      >
        {/* Error icon with gentle pulsing */}
        <motion.div
          animate={{
            scale: [1, 1.05, 1],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="relative w-40 h-40 mx-auto mb-12"
        >
          <motion.div
            animate={{
              opacity: [0.2, 0.4, 0.2],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="absolute inset-0 rounded-full bg-[var(--state-error)] blur-3xl"
          />
          <div className="relative w-40 h-40 rounded-full bg-gradient-to-br from-[var(--state-error)]/20 to-[var(--state-error)]/10 border border-[var(--state-error)]/30 flex items-center justify-center">
            <Icon className="w-20 h-20 text-[var(--state-error)]" strokeWidth={1.5} />
          </div>
        </motion.div>

        {/* Error message */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8"
        >
          <h2 className="text-4xl mb-4" style={{ fontFamily: 'var(--font-display)' }}>
            {message}
          </h2>
          <p className="text-xl text-muted-foreground">{hint}</p>
        </motion.div>

        {/* Auto-dismiss indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="mt-12"
        >
          <div className="w-64 h-1 mx-auto rounded-full bg-[var(--accent)] overflow-hidden">
            <motion.div
              initial={{ width: "0%" }}
              animate={{ width: "100%" }}
              transition={{ duration: 3, ease: "linear" }}
              className="h-full bg-[var(--state-error)]"
            />
          </div>
          <p className="text-sm text-muted-foreground mt-3">Returning to listening...</p>
        </motion.div>
      </motion.div>
    </div>
  );
}
