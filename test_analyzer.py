from core.solana_fetcher import SolanaDataFetcher
from core.ai_analyzer import AIAnalyzer

fetcher = SolanaDataFetcher()
analyzer = AIAnalyzer()

# Devnet: işlem görmüş bir adres kullan (Phantom Devnet + faucet).
TEST_WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

print("1. Veri çekiliyor...")
txs = fetcher.get_clean_transactions(TEST_WALLET)
print(f"   {len(txs)} işlem alındı.")

print("2. AI analizine gönderiliyor...")
result = analyzer.analyze(TEST_WALLET, txs)

print("\n===== SONUÇ =====")
print(f"Risk Seviyesi : {result.get('risk_level')}")
print(f"Yatırımcı Tipi: {result.get('investor_type')}")
print(f"Analiz        : {result.get('analysis')}")