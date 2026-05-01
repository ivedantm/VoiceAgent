import { useEffect, useState, useCallback, useRef } from 'react';
import { Room, RoomEvent, ConnectionState, Track } from 'livekit-client';
import AgentStatus from '../components/AgentStatus';
import BrailleDisplay from '../components/BrailleDisplay';
import WaveformViz from '../components/WaveformViz';
import GradeToggle from '../components/GradeToggle';
import { api } from '../api/client';
import './LiveSession.css';

export default function LiveSession() {
  const [connectionState, setConnectionState] = useState('disconnected');
  const [agentState, setAgentState] = useState('idle');
  const [brailleOutput, setBrailleOutput] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [grade, setGrade] = useState(1);
  const [transcript, setTranscript] = useState([]);
  const [roomInfo, setRoomInfo] = useState(null);
  const [error, setError] = useState(null);

  const roomRef = useRef(null);
  const transcriptEndRef = useRef(null);
  const audioContainerRef = useRef(null);
  // Track seen segment IDs to avoid duplicates
  const seenSegmentsRef = useRef(new Set());

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const addTranscript = useCallback((role, text) => {
    setTranscript(prev => [...prev, { role, text, ts: new Date() }]);
  }, []);

  const connect = useCallback(async () => {
    setConnectionState('connecting');
    setError(null);
    seenSegmentsRef.current.clear();
    try {
      const tokenData = await api.getToken();
      setRoomInfo(tokenData);

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });
      roomRef.current = room;

      // ── Data channel: braille output from agent ──────────────
      room.on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
        const text = new TextDecoder().decode(payload);
        if (topic === 'braille_output') {
          setBrailleOutput(text);
          addTranscript('agent', `⠿ Braille: ${text}`);
        }
      });

      // ── Participant events ───────────────────────────────────
      room.on(RoomEvent.ParticipantConnected, (participant) => {
        addTranscript('system', `${participant.identity} joined`);
      });

      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        addTranscript('system', `${participant.identity} left`);
      });

      // ── AUDIO PLAYBACK: attach agent audio tracks ────────────
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          const audioEl = track.attach();
          audioEl.id = `audio-${participant.identity}-${track.sid}`;
          audioContainerRef.current?.appendChild(audioEl);
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
        track.detach().forEach((el) => el.remove());
      });

      // ── Connection state ─────────────────────────────────────
      room.on(RoomEvent.ConnectionStateChanged, (state) => {
        if (state === ConnectionState.Disconnected) {
          setConnectionState('disconnected');
          setAgentState('idle');
        }
      });

      // ── Transcriptions (deduped by segment ID) ───────────────
      room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        for (const seg of segments) {
          // Only process FINAL segments to avoid duplicates
          if (!seg.final) continue;

          const segId = seg.id;
          // Skip if we've already seen this final segment
          if (seenSegmentsRef.current.has(segId)) continue;
          seenSegmentsRef.current.add(segId);

          const text = seg.text?.trim();
          if (!text) continue;

          // Determine if this is from the agent or user
          const identity = participant?.identity || '';
          const isAgent = !identity.startsWith('user-');

          if (isAgent) {
            addTranscript('agent', text);

            // Detect agent state from responses
            const lower = text.toLowerCase();
            if (lower.includes('start speaking to translate')) {
              setAgentState('listening');
            } else if (lower.includes('is that all') || lower.includes('done when')) {
              setAgentState('accumulating');
            } else if (lower.includes('is this correct')) {
              setAgentState('confirming');
            } else if (lower.includes('what part is wrong')) {
              setAgentState('correcting');
            } else if (lower.includes('going to sleep') || lower.includes('wake me up')) {
              setAgentState('idle');
            } else if (lower.includes('go ahead, continue')) {
              setAgentState('listening');
            }

            // Extract braille from agent TTS output
            const brailleMatch = text.match(/Translated to Braille:\s*(.+)/i);
            if (brailleMatch) {
              setBrailleOutput(brailleMatch[1].trim());
            }
          } else {
            addTranscript('user', text);
            setOriginalText(text);
          }
        }
      });

      // ── Connect to room ──────────────────────────────────────
      await room.connect(tokenData.livekit_url, tokenData.token);

      // Enable microphone
      await room.localParticipant.setMicrophoneEnabled(true);

      setConnectionState('connected');
      addTranscript('system', `Connected to room "${tokenData.room}". Agent Sage-210 dispatched. Say "Hi Sparky" to activate.`);

    } catch (err) {
      console.error('Connection error:', err);
      setError(err.message || 'Failed to connect');
      setConnectionState('disconnected');
    }
  }, [addTranscript]);

  const disconnect = useCallback(async () => {
    try {
      if (roomRef.current) {
        await roomRef.current.disconnect();
        roomRef.current = null;
      }
    } catch {
      // ignore
    }
    setConnectionState('disconnected');
    setAgentState('idle');
    setRoomInfo(null);
    seenSegmentsRef.current.clear();
    // Clean up audio elements
    if (audioContainerRef.current) {
      audioContainerRef.current.innerHTML = '';
    }
    addTranscript('system', 'Disconnected from room.');
  }, [addTranscript]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
      }
    };
  }, []);

  return (
    <div className="live-session page-enter" id="live-session-page">
      {/* Hidden container for agent audio playback */}
      <div ref={audioContainerRef} style={{ display: 'none' }} />
      {/* Header */}
      <div className="live-session-header">
        <div>
          <h1 className="live-session-title">Live Session</h1>
          <p className="text-secondary text-sm">
            Real-time speech to Braille translation
          </p>
        </div>
        <div className="live-session-header-actions">
          <AgentStatus state={agentState} />
          {connectionState === 'disconnected' ? (
            <button className="btn btn-primary" onClick={connect} id="connect-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
              Connect
            </button>
          ) : connectionState === 'connecting' ? (
            <button className="btn btn-ghost" disabled>
              Connecting...
            </button>
          ) : (
            <button className="btn btn-ghost" onClick={disconnect} id="disconnect-btn" style={{ borderColor: 'rgba(239,68,68,0.3)', color: 'var(--color-error)' }}>
              Disconnect
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="live-session-error fade-in">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" x2="9" y1="9" y2="15" />
            <line x1="9" x2="15" y1="9" y2="15" />
          </svg>
          {error}
        </div>
      )}

      {/* Main content */}
      <div className="live-session-grid">
        {/* Left: Waveform + Braille output */}
        <div className="live-session-main">
          {/* Waveform */}
          <div className="live-session-waveform glass-card">
            <div className="live-session-waveform-header">
              <span className="text-sm font-semibold text-muted">AUDIO INPUT</span>
              <div className="live-session-mic-indicator">
                <span className={`status-dot ${connectionState === 'connected' ? 'status-dot--online' : 'status-dot--offline'}`} />
                <span className="text-sm text-secondary">
                  {connectionState === 'connected' ? 'Microphone Active' : 'Microphone Off'}
                </span>
              </div>
            </div>
            <WaveformViz isActive={connectionState === 'connected' && agentState !== 'idle'} />
          </div>

          {/* Braille output */}
          <BrailleDisplay
            braille={brailleOutput}
            originalText={originalText}
          />

          {/* Grade toggle */}
          <div className="live-session-grade glass-card">
            <span className="text-sm font-semibold text-muted" style={{ marginBottom: 'var(--space-sm)', display: 'block' }}>
              BRAILLE GRADE
            </span>
            <GradeToggle grade={grade} onChange={setGrade} />
          </div>
        </div>

        {/* Right: Transcript/Chat log */}
        <div className="live-session-sidebar">
          <div className="live-session-transcript glass-card">
            <div className="live-session-transcript-header">
              <span className="text-sm font-semibold text-muted">TRANSCRIPT</span>
              {roomInfo && (
                <span className="badge badge-accent text-xs">
                  {roomInfo.room}
                </span>
              )}
            </div>
            <div className="live-session-transcript-log" id="transcript-log">
              {transcript.length === 0 ? (
                <div className="empty-state" style={{ padding: 'var(--space-xl)' }}>
                  <p className="text-sm text-muted">
                    Connect to start a session...
                  </p>
                </div>
              ) : (
                <>
                  {transcript.map((entry, i) => (
                    <div
                      key={i}
                      className={`transcript-entry transcript-entry--${entry.role} fade-in`}
                    >
                      <span className="transcript-entry-role">
                        {entry.role === 'user' ? '👤' : entry.role === 'agent' ? '🤖' : 'ℹ️'}
                      </span>
                      <span className="transcript-entry-text">{entry.text}</span>
                      <span className="transcript-entry-time">
                        {entry.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                    </div>
                  ))}
                  <div ref={transcriptEndRef} />
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
