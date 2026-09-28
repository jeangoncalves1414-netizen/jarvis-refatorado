import { ApiSettings } from '../types';

export interface AiResponse {
  success: boolean;
  text: string;
  usedProvider?: string;
  note?: string;
  error?: string;
}

export async function askAiCoach(
  prompt: string, 
  settings: ApiSettings,
  customSystemPrompt?: string
): Promise<AiResponse> {
  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt,
        systemPrompt: customSystemPrompt || settings.systemPrompt,
        keys: settings.oxxyKeys,
        baseUrl: settings.baseUrl,
        model: settings.model
      })
    });

    const data = await res.json();
    if (!res.ok) {
      return {
        success: false,
        text: data.error || 'Erro ao conectar à API.',
        error: data.error
      };
    }

    return {
      success: true,
      text: data.text,
      usedProvider: data.usedProvider,
      note: data.note
    };
  } catch (err: any) {
    return {
      success: false,
      text: `Erro de conexão: ${err.message}. Verifique sua conexão e configurações.`,
      error: err.message
    };
  }
}
