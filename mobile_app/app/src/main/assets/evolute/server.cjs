var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// server.ts
var import_express = __toESM(require("express"), 1);
var import_path = __toESM(require("path"), 1);
var import_genai = require("@google/genai");
var import_dotenv = __toESM(require("dotenv"), 1);
var import_fs = __toESM(require("fs"), 1);
import_dotenv.default.config();
var app = (0, import_express.default)();
var PORT = 3e3;
app.use(import_express.default.json({ limit: "5mb" }));
var geminiClient = null;
function getGeminiClient() {
  if (!geminiClient) {
    const key = process.env.GEMINI_API_KEY;
    if (key) {
      geminiClient = new import_genai.GoogleGenAI({ apiKey: key });
    }
  }
  return geminiClient;
}
var DATA_DIR = import_path.default.join(process.cwd(), "data");
var DB_FILE = import_path.default.join(DATA_DIR, "lifeos_db.json");
if (!import_fs.default.existsSync(DATA_DIR)) {
  import_fs.default.mkdirSync(DATA_DIR, { recursive: true });
}
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", time: (/* @__PURE__ */ new Date()).toISOString() });
});
app.get("/api/sync", (req, res) => {
  try {
    if (!import_fs.default.existsSync(DB_FILE)) {
      return res.json({ data: null, updatedAt: 0 });
    }
    const content = import_fs.default.readFileSync(DB_FILE, "utf-8");
    const parsed = JSON.parse(content);
    res.json(parsed);
  } catch (err) {
    console.error("Erro ao ler /api/sync:", err.message);
    res.status(500).json({ error: "Falha ao ler dados de sincroniza\xE7\xE3o." });
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
    import_fs.default.writeFileSync(DB_FILE, JSON.stringify(payload, null, 2), "utf-8");
    res.json({ success: true, updatedAt: payload.updatedAt });
  } catch (err) {
    console.error("Erro ao gravar /api/sync:", err.message);
    res.status(500).json({ error: "Falha ao persistir dados." });
  }
});
app.post("/api/ai/chat", async (req, res) => {
  const { prompt, systemPrompt, keys, baseUrl, model } = req.body;
  if (!prompt) {
    return res.status(400).json({ error: "Prompt is required." });
  }
  const sysPrompt = systemPrompt || "Voc\xEA \xE9 o Mentor Est\xF3ico do Life OS. Seja radicalmente honesto, direto, minimalista e focado em disciplina, foco e supera\xE7\xE3o. N\xE3o use desculpas.";
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
          continue;
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
      } catch (err) {
        console.warn(`Erro na chave Oxxy #${i + 1}:`, err.message);
      }
    }
  }
  try {
    const ai = getGeminiClient();
    if (ai) {
      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: `${sysPrompt}

Usu\xE1rio:
${prompt}`
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
  } catch (geminiErr) {
    console.error("Gemini API error:", geminiErr.message);
  }
  return res.status(500).json({
    error: "N\xE3o foi poss\xEDvel gerar a resposta. Verifique suas chaves de API nas Configura\xE7\xF5es.",
    success: false
  });
});
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa"
    });
    app.use(vite.middlewares);
  } else {
    const distPath = import_path.default.join(process.cwd(), "dist");
    app.use(import_express.default.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(import_path.default.join(distPath, "index.html"));
    });
  }
  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Life OS Server running on http://0.0.0.0:${PORT}`);
  });
}
startServer();
//# sourceMappingURL=server.cjs.map
