import { motion } from "motion/react";

export function ProcessingScreen() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="text-center"
      >
        {/* Processing animation - rotating dots */}
        <div className="relative w-48 h-48 mx-auto mb-12">
          <motion.div
            animate={{
              rotate: 360,
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "linear",
            }}
            className="absolute inset-0"
          >
            {[...Array(8)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute w-4 h-4 rounded-full bg-[var(--state-processing)]"
                style={{
                  top: "50%",
                  left: "50%",
                  transform: `rotate(${i * 45}deg) translateY(-72px)`,
                }}
                animate={{
                  scale: [1, 1.5, 1],
                  opacity: [0.4, 1, 0.4],
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  delay: i * 0.15,
                  ease: "easeInOut",
                }}
              />
            ))}
          </motion.div>

          {/* Center glow */}
          <motion.div
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.6, 0.3],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="absolute inset-0 rounded-full bg-[var(--state-processing)] blur-2xl"
          />
        </div>

        {/* Status text */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <h2 className="text-5xl mb-4" style={{ fontFamily: 'var(--font-display)' }}>
            Translating to Braille...
          </h2>
          <p className="text-muted-foreground text-lg">This will just take a moment</p>
        </motion.div>
      </motion.div>
    </div>
  );
}
