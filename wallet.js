const bip39 = require('bip39');
const bip32 = require('bip32');
const bitcoin = require('bitcoinjs-lib');
const ECPairFactory = require('ecpair').default;
const tinysecp = require('tiny-secp256k1');

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
}

module.exports = new WalletManager(process.env.MNEMONIC);
