const bip39 = require('bip39');
const bip32 = require('bip32');
const bitcoin = require('bitcoinjs-lib');
const ECPairFactory = require('ecpair').default;
const tinysecp = require('tiny-secp256k1');
const axios = require('axios');

const ECPair = ECPairFactory(tinysecp);
const BIP32Factory = require('bip32').default;
const bip32Instance = BIP32Factory(tinysecp);

const LTC_NETWORK = {
  messagePrefix: '\x19Litecoin Signed Message:\n',
  bech32: 'ltc',
  bip32: {
    public: 0x019da462,
    private: 0x019d9cfe,
  },
  pubKeyHash: 0x30,
  scriptHash: 0x32,
  wif: 0xb0,
};

const BLOCKCHAIR_TOKEN = process.env.BLOCKCHAIR_TOKEN;
const BASE_URL = 'https://api.blockchair.com/litecoin';

class WalletManager {
  constructor(mnemonic) {
    this.mnemonic = mnemonic;
    this.seed = bip39.mnemonicToSeedSync(mnemonic);
    this.root = bip32Instance.fromSeed(this.seed, LTC_NETWORK);
  }

  getAddress(index = 0) {
    const child = this.root.derivePath(`m/84'/2'/0'/0/${index}`);
    const { address } = bitcoin.payments.p2wpkh({
      pubkey: Buffer.from(child.publicKey),
      network: LTC_NETWORK,
    });
    return address;
  }

  getPrivateKey(index = 0) {
    const child = this.root.derivePath(`m/84'/2'/0'/0/${index}`);
    return child.toWIF();
  }

  getKeyPair(index = 0) {
    const child = this.root.derivePath(`m/84'/2'/0'/0/${index}`);
    return ECPair.fromWIF(child.toWIF(), LTC_NETWORK);
  }

  async getUTXOs(address) {
    try {
      const response = await axios.get(
        `${BASE_URL}/dashboards/address/${address}?key=${BLOCKCHAIR_TOKEN}`
      );
      const data = response.data.data[address];
      
      if (!data.utxo || data.utxo.length === 0) {
        return [];
      }

      return data.utxo.map(utxo => ({
        txid: utxo.transaction_hash,
        vout: utxo.index,
        value: parseInt(utxo.value),
        scriptPubKey: utxo.script_hex || this.getScriptPubKey(address)
      }));
    } catch (error) {
      console.error('Get UTXOs error:', error.message);
      return [];
    }
  }

  getScriptPubKey(address) {
    // Generate scriptPubKey for the address
    const { output } = bitcoin.payments.p2wpkh({
      hash: bitcoin.address.fromBech32(address).data,
      network: LTC_NETWORK,
    });
    return output.toString('hex');
  }

  async getBalance(index = 0) {
    const address = this.getAddress(index);
    try {
      const response = await axios.get(
        `${BASE_URL}/dashboards/address/${address}?key=${BLOCKCHAIR_TOKEN}`
      );
      const data = response.data.data[address];
      return data.address.balance / 100000000;
    } catch (error) {
      console.error('Get balance error:', error.message);
      return 0;
    }
  }

  async sendLTC(toAddress, amountLTC, fromIndex = 0) {
    const fromAddress = this.getAddress(fromIndex);
    const amountSatoshi = Math.floor(amountLTC * 100000000);
    
    console.log(`Sending ${amountLTC} LTC (${amountSatoshi} satoshi) from ${fromAddress} to ${toAddress}`);
    
    const utxos = await this.getUTXOs(fromAddress);
    console.log(`Found ${utxos.length} UTXOs`);
    
    if (utxos.length === 0) {
      throw new Error('No UTXOs found - wallet is empty');
    }

    const totalAvailable = utxos.reduce((sum, utxo) => sum + utxo.value, 0);
    const fee = 10000;
    
    console.log(`Total available: ${totalAvailable}, Amount: ${amountSatoshi}, Fee: ${fee}`);
    
    if (totalAvailable < amountSatoshi + fee) {
      throw new Error(`Insufficient balance. Have: ${(totalAvailable/100000000).toFixed(8)} LTC, Need: ${((amountSatoshi + fee)/100000000).toFixed(8)} LTC`);
    }

    const psbt = new bitcoin.Psbt({ network: LTC_NETWORK });
    const keyPair = this.getKeyPair(fromIndex);
    
    let inputSum = 0;
    for (const utxo of utxos) {
      console.log(`Adding input: ${utxo.txid}:${utxo.vout} - ${utxo.value} satoshi`);
      
      // Get raw transaction for nonWitnessUtxo
      const txHex = await this.getTransactionHex(utxo.txid);
      
      psbt.addInput({
        hash: utxo.txid,
        index: utxo.vout,
        nonWitnessUtxo: Buffer.from(txHex, 'hex'),
        witnessUtxo: {
          script: Buffer.from(utxo.scriptPubKey, 'hex'),
          value: utxo.value,
        },
      });
      inputSum += utxo.value;
    }

    // Add recipient output
    psbt.addOutput({
      address: toAddress,
      value: amountSatoshi,
    });

    // Add change output
    const change = inputSum - amountSatoshi - fee;
    if (change > 546) {
      psbt.addOutput({
        address: fromAddress,
        value: change,
      });
      console.log(`Change: ${change} satoshi to ${fromAddress}`);
    }

    // Sign all inputs
    for (let i = 0; i < utxos.length; i++) {
      try {
        psbt.signInput(i, keyPair);
        console.log(`Signed input ${i}`);
      } catch (e) {
        console.error(`Failed to sign input ${i}:`, e.message);
        throw e;
      }
    }

    psbt.finalizeAllInputs();
    const txHex = psbt.extractTransaction().toHex();
    console.log(`Transaction built, size: ${txHex.length / 2} bytes`);

    const txid = await this.broadcastTransaction(txHex);
    return txid;
  }

  async sendAllLTC(toAddress, fromIndex = 0) {
    const fromAddress = this.getAddress(fromIndex);
    const utxos = await this.getUTXOs(fromAddress);
    
    if (utxos.length === 0) {
      throw new Error('No UTXOs found - wallet is empty');
    }

    const totalAvailable = utxos.reduce((sum, utxo) => sum + utxo.value, 0);
    const fee = 10000;
    const amountToSend = totalAvailable - fee;

    if (amountToSend <= 0) {
      throw new Error('Insufficient balance to cover fees');
    }

    return this.sendLTC(toAddress, amountToSend / 100000000, fromIndex);
  }

  async getTransactionHex(txid) {
    try {
      const response = await axios.get(
        `${BASE_URL}/raw/transaction/${txid}?key=${BLOCKCHAIR_TOKEN}`
      );
      return response.data.data[txid].raw_transaction;
    } catch (error) {
      console.error('Get TX hex error:', error.message);
      throw error;
    }
  }

  async broadcastTransaction(txHex) {
    try {
      const response = await axios.post(
        `${BASE_URL}/push/transaction?key=${BLOCKCHAIR_TOKEN}`,
        { data: txHex }
      );
      return response.data.data.transaction_hash;
    } catch (error) {
      console.error('Broadcast error:', error.response?.data || error.message);
      throw new Error(`Broadcast failed: ${error.response?.data?.error || error.message}`);
    }
  }
}

module.exports = new WalletManager(process.env.MNEMONIC);
