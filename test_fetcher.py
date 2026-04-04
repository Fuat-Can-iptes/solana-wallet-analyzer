from core.solana_fetcher import SolanaDataFetcher

fetcher = SolanaDataFetcher()

# Aktif bir Solana cüzdanı (Phantom'ın resmi adresi)
TEST_WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

txs = fetcher.get_clean_transactions(TEST_WALLET)

print(f"Çekilen işlem sayısı: {len(txs)}")
for tx in txs[:3]:
    print(tx)