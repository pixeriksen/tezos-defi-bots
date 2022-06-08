from bot import Bot


class FA2TokenBot(Bot):
    def __init__(self, operator_contract, token_contract_address, token_id, shell, key, token_decimals=12):
        super().__init__(shell, key)
        self.token_contract = self.pytezos_cli.contract(token_contract_address)
        self.token_id = token_id
        self.operator_contract = operator_contract
        self.token_decimals = token_decimals
        self.token_metadata = self.token_contract.storage['token_metadata'][self.token_id]()
        
    def add_operator(self):
        try:
            self.token_contract.storage['operators'][(self.pytezos_cli.key.public_key_hash(), self.operator_contract, self.token_id)]()
            return []
        except:
            return [self.token_contract.update_operators([
                {"add_operator":
                    {"owner":self.pytezos_cli.key.public_key_hash(),
                    "operator":self.operator_contract, 
                    "token_id":self.token_id}
                }
            ])]

    def remove_operator(self):
        try:
            self.token_contract.storage['operators'][(self.pytezos_cli.key.public_key_hash(), self.operator_contract, self.token_id)]()
            return [self.token_contract.update_operators([
                {"remove_operator":
                    {"owner":self.pytezos_cli.key.public_key_hash(),
                    "operator":self.operator_contract, 
                    "token_id":self.token_id}
                }
            ])]
        except:
            return []

    def get_balance(self):
        response = self.token_contract.balance_of(requests=[{'owner': self.pytezos_cli.key.public_key_hash(), 'token_id':self.token_id}], callback=None).callback_view()[0]
        if type(response) is dict:
            response = list(response.values())
        return response[1]/10**self.token_decimals           