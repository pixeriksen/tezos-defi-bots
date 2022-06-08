from bot import Bot
from fa1_token_bot import FA1TokenBot
from fa2_token_bot import FA2TokenBot
import time

FEE = 0.9985
SLIPPAGE = .9999 # .01% slippage allowed
BLOCKTIME = 60
MIN_BALANCE_THRESHOLD = 0.01

def util(x, y):
  return (
      (x+y)**8-(x-y)**8,
      8*((x-y)**7+(x+y)**7)
  )


def newton(x, y, dx, dy, u, iteration_count):
  if (iteration_count==0):
    return dy
  else:
    new_u, new_du_dy = util(x+dx, y-dy)
    new_dy = dy+(new_u-u)/new_du_dy
    iteration_count -= 1
    return newton(x, y, dx, new_dy, u, iteration_count)


class FlatCFMMBot(Bot):

    def __init__(self, dex_contract_address, token1_decimals, token2_decimals, shell, key):
        super().__init__(shell, key)
        self.dex_contract = self.pytezos_cli.contract(dex_contract_address)
        self.token1_decimals = token1_decimals
        self.token2_decimals = token2_decimals
        self.fee = FEE
        try:
            self.token1_bot = FA2TokenBot(dex_contract_address, self.dex_contract.storage()['tokenAddress'], self.dex_contract.storage()['tokenId'], shell, key, token1_decimals)
        except:
            self.token1_bot = FA1TokenBot(dex_contract_address, self.dex_contract.storage()['tokenAddress'], shell, key, token1_decimals)
        try:
            self.token2_bot = FA2TokenBot(dex_contract_address, self.dex_contract.storage()['cashAddress'], self.dex_contract.storage()['cashId'], shell, key, token2_decimals)
        except:
            self.token2_bot = FA1TokenBot(dex_contract_address, self.dex_contract.storage()['cashAddress'], shell, key, token2_decimals)
        self.liquidity_token_bot = FA1TokenBot(dex_contract_address, self.dex_contract.storage()['lqtAddress'], shell, key, 0)

    def token_pool_initialiser(self, token1_pool=0, token2_pool=0):
        if token1_pool == 0:
            token1_pool = self.get_token1_pool()
        if token2_pool == 0:
            token2_pool = self.get_token2_pool()
        return token1_pool, token2_pool

    def get_token1_pool(self):
        return self.raw_to_normalised_token1(self.dex_contract.storage()['tokenPool'])
    
    def get_token2_pool(self):
        return self.raw_to_normalised_token2(self.dex_contract.storage()['cashPool'])

    def get_token1_out(self, token2_to_swap, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        x = token2_pool
        y = token1_pool
        u, _ = util(x, y)
        return SLIPPAGE * newton(x, y, token2_to_swap*self.fee, 0, u, 5)
        
    def get_token2_out(self, token1_to_swap, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        x = token1_pool
        y = token2_pool
        u, _ = util(x, y)
        return SLIPPAGE * newton(x, y, token1_to_swap*self.fee, 0, u, 5)

    def get_price(self, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        x = token2_pool
        y = token1_pool
        num = (x + y) ** 7 + (x - y) ** 7
        den = (x + y) ** 7 - (x - y) ** 7
        return num/den

    def swap_token1(self, token1_to_swap, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        expected_out = self.get_token2_out(token1_to_swap, token1_pool, token2_pool)
        operations = []
        operations.extend(self.token1_bot.add_operator())
        operations.append(self.dex_contract.tokenToCash(to=self.pytezos_cli.key.public_key_hash(), tokensSold=self.normalised_to_raw_token1(token1_to_swap), minCashBought=self.normalised_to_raw_token2(expected_out), deadline=int(time.time())+BLOCKTIME))
        return operations
    
    def swap_token2(self, token2_to_swap, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        expected_out = self.get_token1_out(token2_to_swap, token1_pool, token2_pool)
        operations = []
        operations.extend(self.token2_bot.add_operator())
        operations.append(self.dex_contract.cashToToken(to=self.pytezos_cli.key.public_key_hash(), minTokensBought=self.normalised_to_raw_token1(expected_out), cashSold=self.normalised_to_raw_token2(token2_to_swap), deadline=int(time.time())+BLOCKTIME))
        return operations
    
    def get_expected_token1_amount(self, liquidity_token_amount, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        token1, token2 = self.get_expected_token_amounts(liquidity_token_amount)
        return token1 + self.get_token1_out(token2, token1_pool-token1, token2_pool-token2)

    def get_expected_token2_amount(self, liquidity_token_amount, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        token1, token2 = self.get_expected_token_amounts(liquidity_token_amount)
        return token2 + self.get_token2_out(token1, token1_pool-token1, token2_pool-token2)

    def get_expected_token_amounts(self, liquidity_token_amount, token1_pool=0, token2_pool=0):
        token1_pool, token2_pool = self.token_pool_initialiser(token1_pool, token2_pool)
        max_token1 = token1_pool * (liquidity_token_amount/self.dex_contract.storage['lqtTotal']())
        max_token2 = token2_pool * (liquidity_token_amount/self.dex_contract.storage['lqtTotal']())
        return max_token1, max_token2

    def add_max_liquidity(self):
        amm_ratio = self.get_token1_pool()/self.get_token2_pool()
        operations = []
        if self.token1_bot.get_balance() <= MIN_BALANCE_THRESHOLD and self.token2_bot.get_balance() > MIN_BALANCE_THRESHOLD:
            operations.extend(self.add_token2_liquidity(self.token2_bot.get_balance()))
        elif self.token2_bot.get_balance() <= MIN_BALANCE_THRESHOLD and self.token1_bot.get_balance() > MIN_BALANCE_THRESHOLD:
            operations.extend(self.add_token1_liquidity(self.token1_bot.get_balance()))
        elif self.token1_bot.get_balance() <= MIN_BALANCE_THRESHOLD and self.token2_bot.get_balance() <= MIN_BALANCE_THRESHOLD:
            pass
        else:
            balance_ratio = self.token1_bot.get_balance()/self.token2_bot.get_balance()
            if amm_ratio > balance_ratio:
                print("bigger")
                usable_token2_balance = self.token1_bot.get_balance() * amm_ratio
                print(f"am: {amm_ratio}")
                print(f"token1_balance: {self.token1_bot.get_balance()}")
                print(f"usable_balance: {usable_token2_balance}")
                operations.extend(self.add_liquidity(self.token1_bot.get_balance(), usable_token2_balance))
                operations.extend(self.add_token2_liquidity(self.token2_bot.get_balance() - usable_token2_balance))
            elif amm_ratio < balance_ratio:
                print("smaller")
                usable_token1_balance = self.token2_bot.get_balance() / amm_ratio
                operations.extend(self.add_liquidity(usable_token1_balance, self.token2_bot.get_balance()))
                operations.extend(self.add_token1_liquidity(self.token1_bot.get_balance() - usable_token1_balance))
            else: # perfect balance
                operations.extend(self.add_liquidity(self.token1_bot.get_balance(), self.token2_bot.get_balance()))
        return operations

    def add_liquidity(self, token1_amount, token2_amount):
        raw_token2_amount = self.normalised_to_raw_token2(token2_amount)
        raw_token1_amount = self.normalised_to_raw_token1(token1_amount)
        min_liquidity_minted = int(self.dex_contract.storage['lqtTotal']() * (token2_amount/self.get_token2_pool()))
        operations = []
        operations.extend(self.token1_bot.add_operator())
        operations.extend(self.token2_bot.add_operator())
        operations.append(self.dex_contract.addLiquidity(owner=self.pytezos_cli.key.public_key_hash(), minLqtMinted=int(min_liquidity_minted*SLIPPAGE), maxTokensDeposited=int(raw_token1_amount/SLIPPAGE), cashDeposited=raw_token2_amount, deadline=int(time.time())+BLOCKTIME))
        return operations

    def remove_liquidity(self, liquidity_token_amount):
        max_token1, max_token2 = self.get_expected_token_amounts(liquidity_token_amount)
        return [self.dex_contract.removeLiquidity(to=self.pytezos_cli.key.public_key_hash(), lqtBurned=int(liquidity_token_amount), minCashWithdrawn=self.normalised_to_raw_token2(max_token2*SLIPPAGE), minTokensWithdrawn=self.normalised_to_raw_token1(max_token1*SLIPPAGE), deadline=int(time.time())+BLOCKTIME)]
    
    def remove_liquidity_to_token1(self, liquidity_token_amount):
        token1, token2 = self.get_expected_token_amounts(liquidity_token_amount)
        operations = []
        operations.extend(self.remove_liquidity(liquidity_token_amount))
        operations.extend(self.swap_token2(token2, self.get_token1_pool()-token1, self.get_token2_pool()-token2))
        return operations

    def remove_liquidity_to_token2(self, liquidity_token_amount):
        token1, token2 = self.get_expected_token_amounts(liquidity_token_amount)
        operations = []
        operations.extend(self.remove_liquidity(liquidity_token_amount))
        operations.extend(self.swap_token1(token1, self.get_token1_pool()-token1, self.get_token2_pool()-token2))
        return operations

    def add_token1_liquidity(self, token1_amount):
        amm_ratio = self.get_token1_pool()/self.get_token2_pool()
        swap_ratio = amm_ratio*self.get_price()*self.fee/(amm_ratio*self.fee*self.get_price()+1)
        token2_out = self.get_token2_out((1-swap_ratio)*token1_amount)
        operations = []
        operations.extend(self.swap_token1((1-swap_ratio)*token1_amount))
        operations.extend(self.add_liquidity(token1_amount*swap_ratio, token2_out))
        return operations

    def add_token2_liquidity(self, token2_amount):
        amm_ratio = self.get_token2_pool()/self.get_token1_pool()
        swap_ratio = amm_ratio*(1/self.get_price())*self.fee/(amm_ratio*self.fee*(1/self.get_price())+1)
        token1_out = self.get_token1_out((1-swap_ratio)*token2_amount)
        operations = []
        operations.extend(self.swap_token2((1-swap_ratio)*token2_amount))
        operations.extend(self.add_liquidity(token1_out, token2_amount*swap_ratio*SLIPPAGE))
        return operations

    def raw_to_normalised_token(self, raw_token, token_decimals):
        return raw_token/10**token_decimals

    def normalised_to_raw_token(self, normalised_token, token_decimals):
        return int(normalised_token*10**token_decimals)

    def raw_to_normalised_token2(self, raw_token):
        return self.raw_to_normalised_token(raw_token, self.token2_decimals)

    def normalised_to_raw_token2(self, normalised_token):
        return self.normalised_to_raw_token(normalised_token, self.token2_decimals)

    def raw_to_normalised_token1(self, raw_token):
        return self.raw_to_normalised_token(raw_token, self.token1_decimals)

    def normalised_to_raw_token1(self, normalised_token):
        return self.normalised_to_raw_token(normalised_token, self.token1_decimals)