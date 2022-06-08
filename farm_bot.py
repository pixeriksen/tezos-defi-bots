from bot import Bot
from fa1_token_bot import FA1TokenBot
from fa2_token_bot import FA2TokenBot
from flat_cfmm_bot import FlatCFMMBot

class YouvesFlatLPFarmBot(Bot):
    def __init__(self, farm_contract_address, token1_decimals, token2_decimals, shell, key):
        super().__init__(shell, key)
        self.farm_contract = self.pytezos_cli.contract(farm_contract_address)

        self.token_bot = FA1TokenBot(farm_contract_address, self.farm_contract.storage()['stake_token_address'], shell, key, 18)
        
        self.flat_cfmm_bot = FlatCFMMBot(self.token_bot.token_contract.storage['admin'](), token1_decimals, token2_decimals, shell, key)
        
    def get_own_stake(self):
        try:
            stake = self.farm_contract.storage['stakes'][self.pytezos_cli.key.public_key_hash()]()
            return stake['stake'], stake['age_timestamp']/self.farm_contract.storage['max_release_period']()
        except Exception as e:
            return 0, 0

    def deposit_all(self):
        if self.token_bot.get_balance() >= 0.0001:
            return self.deposit(self.token_bot.get_balance())
        else:
            return []

    def deposit(self, token_amount):
        operations = []
        operations.extend(self.token_bot.add_operator())
        operations.append(self.farm_contract.deposit(int(token_amount*.999999*10**self.token_bot.token_decimals)))
        return operations

    def withdraw(self):
        return [self.farm_contract.withdraw()]

    def claim(self):
        return [self.farm_contract.claim()]