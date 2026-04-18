import { motion } from "motion/react";

export function IdleScreen() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="text-center"
      >
        {/* Breathing pulse indicator */}
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="w-32 h-32 mx-auto mb-12 rounded-full bg-gradient-to-br from-[var(--state-idle)] to-[var(--state-listening)] opacity-50 blur-3xl"
        />

        {/* Logo/System Name */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.6 }}
          className="mb-16"
        >
          <h1 className="text-8xl tracking-tight mb-4" style={{ fontFamily: 'var(--font-display)' }}>
            Sparky
          </h1>
          <div className="w-16 h-1 mx-auto rounded-full bg-gradient-to-r from-transparent via-[var(--state-idle)] to-transparent" />
        </motion.div>

        {/* Main instruction */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.6 }}
          className="mb-8"
        >
          <p className="text-3xl opacity-90 mb-2" style={{ fontFamily: 'var(--font-display)' }}>
            Say <span className="text-[var(--state-idle)]">Hi Sparky</span> to begin
          </p>
        </motion.div>

        {/* Subtle hint */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.6 }}
          className="text-muted-foreground"
        >
          <p className="text-sm">Voice control enabled</p>
        </motion.div>
      </motion.div>
    </div>
  );
}
