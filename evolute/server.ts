import express from "express";
import path from "path";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json({ limit: "5mb" }));

// Lazy Gemini client
let geminiClient: GoogleGenAI | null = null;
function getGeminiClient() {
  if (!geminiClient) {
    const key = process.env.GEMINI_API_KEY;
    if (key) {
      geminiClient = new GoogleGenAI({ apiKey: key });
    }
  }
  return geminiClient;
}

import fs from "fs";

const DATA_DIR = path.join(process.cwd(), "data");
const DB_FILE = path.join(DATA_DIR, "lifeos_db.json");

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Health check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", time: new Date().toISOString() });
});

// Sincronização Local PC <-> Celular
app.get("/api/sync", (req, res) => {
  try {
    if (!fs.existsSync(DB_FILE)) {
      return res.json({ data: null, updatedAt: 0 });
    }
    const content = fs.readFileSync(DB_FILE, "utf-8");
    const parsed = JSON.parse(content);
    res.json(parsed);
  } catch (err: any) {
    console.error("Erro ao ler /api/sync:", err.message);
    res.status(500).json({ error: "Falha ao ler dados de sincronização." });
  }
});

app.post("/api/sync", (req, res) => {
  try {
    const { data, updatedAt } = req.body;
    if (!data) {
      return res.status(400).json({ error: "Payload data ausente." });
    }
    const payload = {
      data,
      updatedAt: updatedAt || Date.now()
    };
    fs.writeFileSync(DB_FILE, JSON.stringify(payload, null, 2), "utf-8");
    res.json({ success: true, updatedAt: payload.updatedAt });
  } catch (err: any) {
    console.error("Erro ao gravar /api/sync:", err.message);
    res.status(500).json({ error: "Falha ao persistir dados." });
  }
});

// AI analysis route with Oxxy/OpenAI key rotation & Gemini fallback
app.post("/api/ai/chat", async (req, res) => {
  const { prompt, systemPrompt, keys, baseUrl, model } = req.body;

  if (!prompt) {
    return res.status(400).json({ error: "Prompt is required." });
  }

  const sysPrompt = systemPrompt || 
    "Você é o Mentor Estóico do Life OS. Seja radicalmente honesto, direto, minimalista e focado em disciplina, foco e superação. Não use desculpas.";

  // 1. Try Oxxy/OpenAI compatible keys if provided
  if (Array.isArray(keys) && keys.length > 0) {
    const effectiveBaseUrl = (baseUrl || "https://api.openai.com/v1").replace(/\/+$/, "");
    const targetModel = model || "gpt-4o-mini";

    for (let i = 0; i < keys.length; i++) {
      const currentKey = keys[i]?.trim();
      if (!currentKey) continue;

      try {
        const response = await fetch(`${effectiveBaseUrl}/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${currentKey}`
          },
          body: JSON.stringify({
            model: targetModel,
            messages: [
              { role: "system", content: sysPrompt },
              { role: "user", content: prompt }
            ],
            temperature: 0.4
          })
        });

        if (!response.ok) {
          const errText = await response.text();
          console.warn(`Chave Oxxy #${i + 1} falhou [${response.status}]: ${errText.slice(0, 100)}`);
          continue; // Rotate to next key
        }

        const data = await response.json();
        const text = data.choices?.[0]?.message?.content;
        if (text) {
          return res.json({
            success: true,
            text,
            usedProvider: "oxxy",
            keyIndexUsed: i,
            totalKeys: keys.length
          });
        }
      } catch (err: any) {
        console.warn(`Erro na chave Oxxy #${i + 1}:`, err.message);
        // Continue to next key
      }
    }
  }

  // 2. Fallback to server-side Gemini if Oxxy keys not configured or failed
  try {
    const ai = getGeminiClient();
    if (ai) {
      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: `${sysPrompt}\n\nUsuário:\n${prompt}`
      });

      if (response.text) {
        return res.json({
          success: true,
          text: response.text,
          usedProvider: "gemini_fallback",
          note: keys && keys.length > 0 ? "As chaves Oxxy falharam ou expiraram, executado via Gemini." : "Executado via Gemini nativo."
        });
      }
    }
  } catch (geminiErr: any) {
    console.error("Gemini API error:", geminiErr.message);
  }

  // If both failed
  return res.status(500).json({
    error: "Não foi possível gerar a resposta. Verifique suas chaves de API nas Configurações.",
    success: false
  });
});

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Life OS Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
