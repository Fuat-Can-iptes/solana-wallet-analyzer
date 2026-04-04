from core.solana_fetcher import SolanaDataFetcher

fetcher = SolanaDataFetcher()

# Devnet: Phantom'ı Devnet'e alıp kendi adresini veya musluktan SOL alan bir adresi kullan.
TEST_WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

txs = fetcher.get_clean_transactions(TEST_WALLET)

print(f"Çekilen işlem sayısı: {len(txs)}")
for tx in txs[:3]:
    print(tx)