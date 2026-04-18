import { motion } from "motion/react";
import { Mic } from "lucide-react";

interface ListeningScreenProps {
  transcription?: string;
}

export function ListeningScreen({ transcription = "" }: ListeningScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-3xl w-full"
      >
        {/* Microphone icon with glow */}
        <motion.div
          animate={{
            scale: [1, 1.05, 1],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="relative mb-12"
        >
          <motion.div
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.5, 0.3],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="absolute inset-0 w-48 h-48 mx-auto rounded-full bg-[var(--state-listening)] blur-3xl"
          />
          <div className="relative w-48 h-48 mx-auto rounded-full bg-gradient-to-br from-[var(--state-listening)] to-[var(--state-idle)] flex items-center justify-center">
            <Mic className="w-24 h-24 text-background" strokeWidth={1.5} />
          </div>
        </motion.div>

        {/* Waveform animation */}
        <div className="flex items-center justify-center gap-2 mb-12 h-24">
          {[...Array(12)].map((_, i) => (
            <motion.div
              key={i}
              animate={{
                height: ["20%", "100%", "20%"],
              }}
              transition={{
                duration: 1.2,
                repeat: Infinity,
                delay: i * 0.1,
                ease: "easeInOut",
              }}
              className="w-2 bg-[var(--state-listening)] rounded-full"
              style={{ minHeight: "8px" }}
            />
          ))}
        </div>

        {/* Status text */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8"
        >
          <h2 className="text-5xl mb-6" style={{ fontFamily: 'var(--font-display)' }}>
            Listening...
          </h2>
        </motion.div>

        {/* Live transcription */}
        {transcription && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-12 p-6 rounded-3xl bg-[var(--card)] border border-[var(--border)]"
          >
            <p className="text-xl opacity-80">{transcription}</p>
          </motion.div>
        )}

        {/* Hint */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="text-muted-foreground"
        >
          <p className="text-sm">Say 'stop' when finished</p>
        </motion.div>
      </motion.div>
    </div>
  );
}
