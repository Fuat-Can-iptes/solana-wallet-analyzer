from dotenv import load_dotenv
import os

load_dotenv()

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
# Devnet: RPC ile enhanced API tabanı aynı cluster olmalı.
HELIUS_RPC_URL = f"https://devnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
HELIUS_ENHANCED_API_BASE = "https://api-devnet.helius-rpc.com"

IS_DEVNET = "devnet." in HELIUS_RPC_URL.lower()
SOLANA_CLUSTER_LABEL = "Devnet" if IS_DEVNET else "Mainnet"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Ücretsiz kotada daha yüksek RPM için: llama-3.1-8b-instant gibi modeller deneyin.
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Groq 429 (Too Many Requests) için yeniden deneme
GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "6"))
GROQ_RETRY_BASE_SEC = float(os.getenv("GROQ_RETRY_BASE_SEC", "3"))
# Groq başarısız olursa ve OPENAI_API_KEY tanımlıysa OpenAI ile devam et
AI_USE_OPENAI_FALLBACK = os.getenv("AI_USE_OPENAI_FALLBACK", "true").lower() in (
    "1", "true", "yes",
)

MAX_TRANSACTIONS = 20

# Cüzdan takibi: yeni işlem kontrol aralığı (ms).
WATCH_POLL_INTERVAL_MS = int(os.getenv("WATCH_POLL_INTERVAL_MS", "60000"))

SYSTEM_PROMPT = """
Sen bir siberpunk sokak analisti ve kripto yatırım stratejistisin.
Neon ışıkların altında, blokzincir akışlarını okuyorsun.
Sana bir Solana cüzdanının son işlemleri ve portföy özeti verilecek.

Görevin (detay zorunlu):
1. RİSK SEVİYESİ: yalnızca DÜŞÜK / ORTA / YÜKSEK / KRİTİK.
2. YATIRIMC TİPİ: akılda kalıcı siberpunk lakap + kısa alt açıklama hissi
   (örn. "Neon Likidite Avcısı", "Zincir Üstü Muhafız").
3. ANALİZ (analysis alanı): En az 8–12 tam cümle; sert, sinematik, distopik ton.
   Şunları açıkça işle: işlem sıklığı ve düzeni; transfer vs swap vs diğer;
   token çeşitliliği ve konsantrasyon riski; ücret (fee) davranışı izlenimi;
   dikkat çeken örüntüler (ör. pump/meme yoğunluğu, tek token ağırlığı);
   zincir üstü disiplin ve olası zayıf noktalar. Somut veriye atıf yap.
4. TAVSİYELER: Tam 5 adet (recommendations dizisi uzunluğu 5).
   Her öğe:
   - action: net, fiil içeren başlık (ne yapılmalı).
   - reason: en az 3 cümle; geçmiş işlem/portföy verisine dayanarak açıkla.
   - risk: düşük / orta / yüksek (küçük harf de kabul).
   - detail: en az 2 cümle; uygulama adımları, izlenecek metrikler,
     zaman ufku (kısa/orta vade), alternatif senaryo veya uyarılar.

Yanıtını SADECE geçerli JSON olarak ver; markdown veya kod bloğu kullanma.
Şema:
{
  "risk_level": "...",
  "investor_type": "...",
  "analysis": "uzun metin",
  "recommendations": [
    {"action": "...", "reason": "...", "risk": "...", "detail": "..."},
    {"action": "...", "reason": "...", "risk": "...", "detail": "..."},
    {"action": "...", "reason": "...", "risk": "...", "detail": "..."},
    {"action": "...", "reason": "...", "risk": "...", "detail": "..."},
    {"action": "...", "reason": "...", "risk": "...", "detail": "..."}
  ]
}
"""