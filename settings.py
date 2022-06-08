from pytezos.crypto.key import Key

SHELL = 'https://mainnet.api.tez.ie/'
KEY = Key.from_encoded_key(key="edsk...")

DRY_RUN = True
PRICE_THRESHOLD = 1.005
TARGET_COLLATERAL_RATIO = 3.0
THRESHOLD_RATIO = 2.1

ENGINE_ADDRESS = "KT1FFE2LC5JpVakVjHm5mM36QVp2p3ZzH4hH"
BAKER = "tz1MJx9vhaNRSimcuXPK2rW4fLccQnDAnVKJ"


#FARM_ADDRESS = "KT1JFsKh3Wcnd4tKzF6EwugwTVGj3XfGPfeZ" # UUSD/USDTZ LP
FARM_ADDRESS = "KT1HaWDWv7XPsZ54JbDquXV6YgyazQr9Jkp3" # UUSD/kUSD LP
#FARM_ADDRESS = "KT1TkNadQ9Cw5ZNRyS4t9SKmUbmAMkqY8bkV" # UUSD/wUSDC LP