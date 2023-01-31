#! /bin/bash
set -e
brownie networks modify mainnet host=$WEB3_PROVIDER explorer=$EXPLORER
brownie run tbtc-minting --network mainnet -r
