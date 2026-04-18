import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { IdleScreen } from "./components/IdleScreen";
import { ListeningScreen } from "./components/ListeningScreen";
import { ConfirmationScreen } from "./components/ConfirmationScreen";
import { ProcessingScreen } from "./components/ProcessingScreen";
import { OutputScreen } from "./components/OutputScreen";
import { PrintingScreen } from "./components/PrintingScreen";
import { ErrorScreen } from "./components/ErrorScreen";

type AppState =
  | "idle"
  | "listening"
  | "confirmation"
  | "processing"
  | "output"
  | "printing"
  | "printing-complete"
  | "error";

type ErrorType = "misheard" | "timeout" | "confusion";

// Mock text-to-braille converter (simplified)
function convertToBraille(text: string): string {
  // This is a very simplified mock - real Braille conversion is much more complex
  const brailleMap: { [key: string]: string } = {
    a: "⠁", b: "⠃", c: "⠉", d: "⠙", e: "⠑", f: "⠋", g: "⠛", h: "⠓",
    i: "⠊", j: "⠚", k: "⠅", l: "⠇", m: "⠍", n: "⠝", o: "⠕", p: "⠏",
    q: "⠟", r: "⠗", s: "⠎", t: "⠞", u: "⠥", v: "⠧", w: "⠺", x: "⠭",
    y: "⠽", z: "⠵", " ": "⠀",
  };

  return text
    .toLowerCase()
    .split("")
    .map((char) => brailleMap[char] || char)
    .join("");
}

export default function App() {
  const [state, setState] = useState<AppState>("idle");
  const [transcription, setTranscription] = useState("");
  const [capturedText, setCapturedText] = useState("");
  const [brailleOutput, setBrailleOutput] = useState("");
  const [errorType, setErrorType] = useState<ErrorType>("misheard");

  // Demo: Simulate voice command detection with keyboard
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Demo controls (hidden from user, for testing)
      if (e.key === "1" && state === "idle") {
        // Simulate "Hi Sparky"
        setState("listening");
        setTranscription("");
      } else if (e.key === "2" && state === "listening") {
        // Simulate dictation
        const mockTexts = [
          "Hello world",
          "Please print this message",
          "Meeting at three PM",
          "Remember to call mom",
        ];
        const randomText = mockTexts[Math.floor(Math.random() * mockTexts.length)];
        setTranscription(randomText);

        setTimeout(() => {
          setCapturedText(randomText);
          setState("confirmation");
        }, 1500);
      } else if (e.key === "3" && state === "confirmation") {
        // Simulate "confirm"
        setState("processing");

        setTimeout(() => {
          const braille = convertToBraille(capturedText);
          setBrailleOutput(braille);
          setState("output");
        }, 2000);
      } else if (e.key === "4" && state === "confirmation") {
        // Simulate "retry"
        setState("listening");
        setTranscription("");
      } else if (e.key === "5" && state === "output") {
        // Simulate "print"
        setState("printing");

        setTimeout(() => {
          setState("printing-complete");
        }, 3000);
      } else if (e.key === "6" && state === "output") {
        // Simulate "restart"
        setState("idle");
        setTranscription("");
        setCapturedText("");
        setBrailleOutput("");
      } else if (e.key === "7" && (state === "printing-complete" || state === "idle")) {
        // Simulate "new note"
        setState("idle");
        setTranscription("");
        setCapturedText("");
        setBrailleOutput("");
      } else if (e.key === "e") {
        // Simulate error
        const errors: ErrorType[] = ["misheard", "timeout", "confusion"];
        setErrorType(errors[Math.floor(Math.random() * errors.length)]);
        setState("error");

        setTimeout(() => {
          setState("listening");
        }, 3000);
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [state, capturedText]);

  // Auto-demo mode: cycle through states automatically
  useEffect(() => {
    let timeout: NodeJS.Timeout;

    const runDemo = () => {
      switch (state) {
        case "idle":
          timeout = setTimeout(() => setState("listening"), 3000);
          break;
        case "listening":
          timeout = setTimeout(() => {
            const mockText = "Hello world";
            setTranscription(mockText);
            setTimeout(() => {
              setCapturedText(mockText);
              setState("confirmation");
            }, 1000);
          }, 2000);
          break;
        case "confirmation":
          timeout = setTimeout(() => setState("processing"), 3000);
          break;
        case "processing":
          timeout = setTimeout(() => {
            const braille = convertToBraille(capturedText);
            setBrailleOutput(braille);
            setState("output");
          }, 2000);
          break;
        case "output":
          timeout = setTimeout(() => setState("printing"), 4000);
          break;
        case "printing":
          timeout = setTimeout(() => setState("printing-complete"), 3000);
          break;
        case "printing-complete":
          timeout = setTimeout(() => {
            setState("idle");
            setTranscription("");
            setCapturedText("");
            setBrailleOutput("");
          }, 3000);
          break;
      }
    };

    runDemo();
    return () => clearTimeout(timeout);
  }, [state, capturedText]);

  const errorMessages = {
    misheard: {
      message: "Sorry, I didn't catch that",
      hint: "Please try again",
    },
    timeout: {
      message: "No input detected",
      hint: "Say Hi Sparky to restart",
    },
    confusion: {
      message: "I'm not sure what you mean",
      hint: "Please say confirm or retry",
    },
  };

  return (
    <div className="min-h-screen bg-background text-foreground overflow-hidden">
      <AnimatePresence mode="wait">
        {state === "idle" && (
          <motion.div
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
          >
            <IdleScreen />
          </motion.div>
        )}

        {state === "listening" && (
          <motion.div
            key="listening"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ListeningScreen transcription={transcription} />
          </motion.div>
        )}

        {state === "confirmation" && (
          <motion.div
            key="confirmation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ConfirmationScreen text={capturedText} />
          </motion.div>
        )}

        {state === "processing" && (
          <motion.div
            key="processing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ProcessingScreen />
          </motion.div>
        )}

        {state === "output" && (
          <motion.div
            key="output"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <OutputScreen text={capturedText} braille={brailleOutput} />
          </motion.div>
        )}

        {state === "printing" && (
          <motion.div
            key="printing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <PrintingScreen isComplete={false} />
          </motion.div>
        )}

        {state === "printing-complete" && (
          <motion.div
            key="printing-complete"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <PrintingScreen isComplete={true} />
          </motion.div>
        )}

        {state === "error" && (
          <motion.div
            key="error"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ErrorScreen
              type={errorType}
              message={errorMessages[errorType].message}
              hint={errorMessages[errorType].hint}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Demo instructions overlay (small, unobtrusive) */}
      <div className="fixed bottom-6 right-6 px-4 py-3 rounded-2xl bg-[var(--card)] border border-[var(--border)] text-xs text-muted-foreground max-w-xs opacity-50 hover:opacity-100 transition-opacity">
        <p className="mb-1 font-medium">Demo Controls:</p>
        <p>Auto-cycling through states...</p>
        <p className="text-[10px] mt-2 opacity-60">
          Manual: 1=wake, 2=speak, 3=confirm, 4=retry, 5=print, 6=restart, e=error
        </p>
      </div>
    </div>
  );
}
