// Audio Synthesizer for focus sessions (Web Audio API)
let audioCtx: AudioContext | null = null;
let currentNoiseNode: AudioNode | null = null;
let currentGainNode: GainNode | null = null;

function getAudioContext(): AudioContext {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    audioCtx = new AudioContextClass();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

export type FocusSoundType = 'none' | 'white' | 'brown' | 'rain' | 'binaural40hz';

export function playFocusSound(type: FocusSoundType, volume: number = 0.5): void {
  stopFocusSound();
  if (type === 'none') return;

  try {
    const ctx = getAudioContext();
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(volume * 0.15, ctx.currentTime);
    gain.connect(ctx.destination);
    currentGainNode = gain;

    if (type === 'white') {
      const bufferSize = 2 * ctx.sampleRate;
      const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) {
        output[i] = Math.random() * 2 - 1;
      }
      const whiteNoise = ctx.createBufferSource();
      whiteNoise.buffer = noiseBuffer;
      whiteNoise.loop = true;
      whiteNoise.connect(gain);
      whiteNoise.start();
      currentNoiseNode = whiteNoise;
    } else if (type === 'brown') {
      const bufferSize = 2 * ctx.sampleRate;
      const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      let lastOut = 0.0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        output[i] = (lastOut + (0.02 * white)) / 1.02;
        lastOut = output[i];
        output[i] *= 3.5;
      }
      const brownNoise = ctx.createBufferSource();
      brownNoise.buffer = noiseBuffer;
      brownNoise.loop = true;
      brownNoise.connect(gain);
      brownNoise.start();
      currentNoiseNode = brownNoise;
    } else if (type === 'rain') {
      // Pink-ish filtered noise with random droplet modulation
      const bufferSize = 2 * ctx.sampleRate;
      const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      let b0 = 0, b1 = 0, b2 = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        output[i] = (b0 + b1 + b2) * 0.15;
      }
      const rainSource = ctx.createBufferSource();
      rainSource.buffer = noiseBuffer;
      rainSource.loop = true;

      // Lowpass filter
      const filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(800, ctx.currentTime);

      rainSource.connect(filter);
      filter.connect(gain);
      rainSource.start();
      currentNoiseNode = rainSource;
    } else if (type === 'binaural40hz') {
      // 40Hz difference for Gamma focus: Left 200Hz, Right 240Hz
      const merger = ctx.createChannelMerger(2);

      const oscLeft = ctx.createOscillator();
      oscLeft.type = 'sine';
      oscLeft.frequency.setValueAtTime(200, ctx.currentTime);

      const oscRight = ctx.createOscillator();
      oscRight.type = 'sine';
      oscRight.frequency.setValueAtTime(240, ctx.currentTime);

      oscLeft.connect(merger, 0, 0);
      oscRight.connect(merger, 0, 1);
      merger.connect(gain);

      oscLeft.start();
      oscRight.start();
      currentNoiseNode = oscLeft;
    }
  } catch (err) {
    console.warn('Audio synthesis failed:', err);
  }
}

export function stopFocusSound(): void {
  try {
    if (currentNoiseNode) {
      if ((currentNoiseNode as any).stop) {
        (currentNoiseNode as any).stop();
      }
      currentNoiseNode.disconnect();
      currentNoiseNode = null;
    }
    if (currentGainNode) {
      currentGainNode.disconnect();
      currentGainNode = null;
    }
  } catch {
    // ignore
  }
}

// Subtle feedback chime when habit/session is completed
export function playChime(): void {
  try {
    const ctx = getAudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5

    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch {
    // ignore
  }
}
