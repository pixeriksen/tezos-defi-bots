from pytezos import pytezos
from settings import *
import time
import traceback

from farm_bot import YouvesFlatLPFarmBot
from fa2_token_bot import FA2TokenBot

ADDRESS_CALBLACK_CONTRACT = "KT1UAuApZKc1UrbKL27xa5B6XWxUgahLZpnX%set_address"
NAT_CALLBACK_CONTRACT = "KT1UAuApZKc1UrbKL27xa5B6XWxUgahLZpnX%set_nat"
MIN_BALANCE_THRESHOLD = 0.01

farm_bot = YouvesFlatLPFarmBot(FARM_ADDRESS, 12, 18, SHELL, KEY)
pytezos_cli = pytezos.using(shell=SHELL, key=KEY)

def log(message):
    print(f"[{int(time.time())}:{pytezos_cli.key.public_key_hash()}] {message}")

engine = pytezos_cli.contract(ENGINE_ADDRESS)
target_price_oracle = pytezos_cli.contract(engine.storage['target_price_oracle']())
token1_bot = FA2TokenBot(ENGINE_ADDRESS, engine.storage['token_contract'](), engine.storage['token_id'](), SHELL, KEY)
last_now = pytezos_cli.now()

while True:
    time.sleep(1)
    try:
        if last_now == pytezos_cli.now():
            continue
    
        last_now = pytezos_cli.now()
        try:
            vault_context = engine.storage['vault_contexts'][pytezos_cli.key.public_key_hash()]()
            log(f"your vault address is {vault_context['address']}")
        except:
            log(f"no vault found, creating vault...")
            try:
                engine.create_vault(baker=BAKER, contract_address_callback=ADDRESS_CALBLACK_CONTRACT).send()
            except:
                engine.create_vault(True).send() # this is a token
            continue

        target_price = int(list(
            map(lambda operation: operation['parameters']['value']['int'], 
                filter(lambda operation: operation['destination'] in NAT_CALLBACK_CONTRACT, target_price_oracle.get_price(NAT_CALLBACK_CONTRACT).run_operation().operations)
            )
        )[0])
        
        log(f"target price: {target_price}")
        log(f"your vault balance: {vault_context['balance']}")

        minted = vault_context['minted']*engine.storage['compound_interest_rate']()/10**12 
        log(f"your vault minted: {minted}")

        max_mintable = vault_context['balance']*10**12//TARGET_COLLATERAL_RATIO//target_price
        emergency_mintable = vault_context['balance']*10**12//THRESHOLD_RATIO//target_price
        log(f"max mintable {max_mintable}")
        mintable = max_mintable*.99 - minted
        burnable = minted - emergency_mintable
        
        operations = []
        if mintable > 10**9:
            log(f"additional mintable: {mintable}")
            if farm_bot.flat_cfmm_bot.get_price() < PRICE_THRESHOLD:
                continue
            minting_fee = mintable*2**-6
            minted = mintable-minting_fee
            operations.append(engine.mint(int(mintable)))
        elif burnable > 10**9:
            log(f"required to burn: {burnable}")
            operations.extend(token1_bot.add_operator())
            if burnable <=  farm_bot.flat_cfmm_bot.normalised_to_raw_token1(token1_bot.get_balance()):
                log("has enough balance to burn")                
            elif burnable <= farm_bot.flat_cfmm_bot.normalised_to_raw_token1(farm_bot.flat_cfmm_bot.token1_bot.get_balance() + farm_bot.flat_cfmm_bot.get_token1_out(farm_bot.flat_cfmm_bot.token2_bot.get_balance())):
                log("has enough balance after swap to burn")   
                operations.extend(farm_bot.flat_cfmm_bot.swap_token2(farm_bot.flat_cfmm_bot.token2_bot.get_balance()))
            else:
                log("needs to unwind farm to get enough balance to burn")   
                stake = farm_bot.get_own_stake()[0]
                operations.extend(farm_bot.withdraw())
                operations.extend(farm_bot.flat_cfmm_bot.remove_liquidity(stake))
            operations.append(engine.burn(int(burnable)))            
        elif farm_bot.flat_cfmm_bot.token1_bot.get_balance() > MIN_BALANCE_THRESHOLD or farm_bot.flat_cfmm_bot.token2_bot.get_balance() > MIN_BALANCE_THRESHOLD:
            log(f"providing liquidity")
            operations.extend(farm_bot.flat_cfmm_bot.add_max_liquidity())
        else:
            log(f"farming if possible")
            operations.extend(farm_bot.deposit_all())
        if len(operations) > 0:
            if DRY_RUN:
                print("START DRYRUN")
                pytezos_cli.bulk(*operations).autofill().sign().run_operation()
                print("END   DRYRUN")
            else:
                pytezos_cli.bulk(*operations).send(min_confirmations=1)
    except Exception as e:
        traceback.print_exc()
        log(f"something went wrong: {e}")