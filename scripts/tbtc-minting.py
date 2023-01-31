import os
import json
import telebot
import logging
import sys
from hexbytes import HexBytes
from time import sleep
from brownie.network.event import _decode_logs, _add_deployment_topics
from brownie import web3
from brownie import chain
from web3.middleware import filter
web3.middleware_onion.add(filter.local_filter_middleware)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("tbtc-minting")

def main():
    telegram_bot_key = os.environ.get('TG_BOT_KEY')
    bot = telebot.TeleBot(telegram_bot_key)

    minter_address = "0xe54Fb47Da51fbBd5aCea5D4f8a8D34ae310DA4fB"
    tbtc_address   = "0x9C070027cdC9dc8F82416B2e5314E11DFb4FE3CD"
    tbtc_abi = json.load(open('tbtc-abi.json'))
    # smol hack to let brownie parse the event names
    _add_deployment_topics(tbtc_address, tbtc_abi)
    topics = [
        # topic0: ["OptimisticMintingFinalized", "OptimisticMintingRequested"]
        ["0x2cffebf26d639426e79514d100febae8b2c63e700e5dc0fa6c88a12963350636", "0x36f39c606d55d7dd2a05b8c4e41e9a6ca8c501cea10009c1762f6826a146e055"],
        # topic1: yearn minter address
        "0x000000000000000000000000e54fb47da51fbbd5acea5d4f8a8d34ae310da4fb"
    ]

    from_block = int(os.getenv("FROM_BLOCK", chain.height))
    while True:
        f = web3.eth.filter({"address": tbtc_address, "fromBlock": from_block, "topics": topics})
        logs = f.get_all_entries()
        for i, e in enumerate(_decode_logs(logs)):
            log = logs[i]
            txn_hash = log.transactionHash.hex()
            block = log.blockNumber
            balance = web3.eth.getBalance(minter_address, block_identifier=block)
            eth_balance = web3.fromWei(balance, "ether")
            tbtc_amount = 0
            funding_txn_hash = None
            if e.name == "OptimisticMintingRequested":
                tbtc_amount = web3.fromWei(e["amount"], "ether")
                funding_txn_hash = _convert_funding_tx_hash(e["fundingTxHash"])
            elif e.name == "OptimisticMintingFinalized":
                tbtc_amount = web3.fromWei(e["optimisticMintingDebt"], "ether")
            else:
              raise ValueError(f"Found event with name: {e.name}")

            _send_message(bot, e.name, txn_hash, block, tbtc_amount, eth_balance, funding_txn_hash)
        sleep(5)
        from_block = chain.height

def _send_message(bot, event_name, txn_hash, block, tbtc_amount, eth_balance, funding_txn_hash = None):
    tbtc_amount = float(round(tbtc_amount, 5))
    if tbtc_amount < 0.49999:
        icon = "🐟"
    elif tbtc_amount >= 0.5 and tbtc_amount < 4.99999:
        icon = "🐠"
    elif tbtc_amount >= 5 and tbtc_amount < 49.99999:
        icon = "🐋"
    elif tbtc_amount >= 50:
        icon = "🐳"
    else:
        icon = "✨"

    msg = f'{icon} *yearn <-> tBTC optimistic minting detected!*\n\n'
    msg += f'Type   : {event_name}\n'
    msg += f'Amount : {tbtc_amount} tBTC\n'
    msg += f'Balance: {float(round(eth_balance, 6))} ETH\n'
    msg += f'Block  : {block}\n'
    if funding_txn_hash:
        msg += f'\n🔗 [View on Blockstream](https://blockstream.info/tx/{funding_txn_hash})'
    msg += f'\n🔗 [View on Etherscan](https://etherscan.io/tx/{txn_hash})'
    logger.info(msg)
    chat_id = os.environ.get("TG_CHAT_ID")
    bot.send_message(chat_id, msg, parse_mode="markdown", disable_web_page_preview = True)

def _convert_funding_tx_hash(funding_txn_hash):
    h = HexBytes(funding_txn_hash)
    ba = bytearray(bytes(h))
    ba.reverse()
    return ba.hex()

