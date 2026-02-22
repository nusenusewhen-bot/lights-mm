const axios = require('axios');

const BLOCKCHAIR_TOKEN = process.env.BLOCKCHAIR_TOKEN;
const BASE_URL = 'https://api.blockchair.com/litecoin';

class BlockchainAPI {
  async getAddressInfo(address) {
    try {
      const response = await axios.get(
        `${BASE_URL}/dashboards/address/${address}?key=${BLOCKCHAIR_TOKEN}`
      );
      return response.data.data[address];
    } catch (error) {
      console.error('Blockchair API error:', error.message);
      throw error;
    }
  }

  async getTransaction(txHash) {
    try {
      const response = await axios.get(
        `${BASE_URL}/dashboards/transaction/${txHash}?key=${BLOCKCHAIR_TOKEN}`
      );
      return response.data.data[txHash];
    } catch (error) {
      console.error('Blockchair TX error:', error.message);
      throw error;
    }
  }

  async getAddressTransactions(address) {
    try {
      const response = await axios.get(
        `${BASE_URL}/dashboards/address/${address}?transaction_details=true&key=${BLOCKCHAIR_TOKEN}`
      );
      return response.data.data[address].transactions || [];
    } catch (error) {
      console.error('Blockchair TX list error:', error.message);
      return [];
    }
  }

  async getLtcPriceUSD() {
    try {
      const response = await axios.get(
        'https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd'
      );
      return response.data.litecoin.usd;
    } catch (error) {
      console.error('Price fetch error:', error.message);
      return 85; // fallback price
    }
  }

  async checkIncomingTransaction(address, expectedAmountLTC) {
    try {
      const txs = await this.getAddressTransactions(address);
      
      for (const tx of txs) {
        // Check outputs to our address
        for (const output of tx.outputs || []) {
          if (output.recipient === address && output.value > 0) {
            const amountLTC = output.value / 100000000;
            const tolerance = 0.0001; // Small tolerance for fees
            
            if (Math.abs(amountLTC - expectedAmountLTC) < tolerance || amountLTC >= expectedAmountLTC * 0.95) {
              return {
                found: true,
                txHash: tx.hash,
                amount: amountLTC,
                confirmations: tx.block_id ? 1 : 0,
                confirmed: tx.block_id !== null
              };
            }
          }
        }
      }
      
      return { found: false };
    } catch (error) {
      console.error('Check incoming error:', error.message);
      return { found: false };
    }
  }

  async isTransactionConfirmed(txHash) {
    try {
      const tx = await this.getTransaction(txHash);
      return tx && tx.transaction && tx.transaction.block_id !== null;
    } catch (error) {
      return false;
    }
  }
}

module.exports = new BlockchainAPI();
